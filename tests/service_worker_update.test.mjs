import assert from "node:assert/strict";
import {readFile} from "node:fs/promises";
import test from "node:test";
import vm from "node:vm";

const workerSource = await readFile(new URL("../apps/web/service-worker.js", import.meta.url), "utf8");
const CURRENT_CACHE = "wurstbrot-1.0.0-stable-vt5";

function createWorker({cacheNames = [], clients = [], failPrecache = false, cacheHit = null} = {}) {
  const handlers = new Map();
  const storedCaches = new Set(cacheNames);
  const deletedCaches = [];
  const addedAssets = [];
  const freshRequests = [];
  const calls = {claim: 0, matchAll: 0, skipWaiting: 0, network: 0};
  const windows = clients.map(url => ({
    url,
    navigations: [],
    async navigate(target) {
      this.navigations.push(target);
      return new Promise(() => {});
    },
  }));
  const self = {
    location: {href: "https://example.test/wurstbrot-suite/service-worker.js"},
    addEventListener(type, handler) {
      handlers.set(type, handler);
    },
    async skipWaiting() {
      calls.skipWaiting += 1;
    },
    clients: {
      async claim() {
        calls.claim += 1;
      },
      async matchAll(options) {
        calls.matchAll += 1;
        assert.equal(options.type, "window");
        assert.equal(options.includeUncontrolled, true);
        return windows;
      },
    },
  };
  const caches = {
    async open(name) {
      storedCaches.add(name);
      return {
        async put(request) {
          addedAssets.push(String(request));
        },
      };
    },
    async keys() {
      return [...storedCaches];
    },
    async delete(name) {
      deletedCaches.push(name);
      return storedCaches.delete(name);
    },
    async match() {
      return cacheHit;
    },
  };
  const context = {
    Promise,
    caches,
    fetch: async (request, options) => {
      calls.network += 1;
      const url = String(request);
      if (url.includes("wurstbrot-cache=")) {
        if (failPrecache) throw new Error("precache failed");
        freshRequests.push({url, options});
        return {ok: true, network: url};
      }
      return {ok: true, network: request};
    },
    self,
    URL,
  };
  vm.runInNewContext(workerSource, context, {filename: "service-worker.js"});

  async function dispatch(type, request = null) {
    const handler = handlers.get(type);
    assert.ok(handler, `${type} handler registered`);
    let lifetime;
    let response;
    const event = {
      request,
      waitUntil(promise) {
        lifetime = Promise.resolve(promise);
      },
      respondWith(promise) {
        response = Promise.resolve(promise);
      },
    };
    handler(event);
    if (lifetime) {
      await Promise.race([
        lifetime,
        new Promise((_, reject) => setTimeout(
          () => reject(new Error(`${type} lifetime deadlocked`)), 250,
        )),
      ]);
    }
    return response ? response : undefined;
  }

  return {addedAssets, calls, deletedCaches, dispatch, freshRequests, storedCaches, windows};
}

test("fresh user precaches VT.5 and activates without an unnecessary reload", async () => {
  const worker = createWorker({cacheNames: ["other-app-cache"], clients: ["https://example.test/app/"]});
  await worker.dispatch("install");
  await worker.dispatch("activate");

  assert.equal(worker.calls.skipWaiting, 1);
  assert.equal(worker.calls.claim, 1);
  assert.equal(worker.calls.matchAll, 0);
  assert.deepEqual(worker.windows[0].navigations, []);
  assert.deepEqual(worker.deletedCaches, []);
  assert(worker.storedCaches.has(CURRENT_CACHE));
  assert(worker.storedCaches.has("other-app-cache"));
  for (const required of ["index.html", "app.js", "solver.mjs", "visual-tree.mjs", "visual-tree-interaction.mjs", "styles.css"]) {
    assert(worker.addedAssets.some(url => url.endsWith(required)), required);
  }
  assert.equal(worker.freshRequests.length, worker.addedAssets.length);
  assert(worker.freshRequests.every(item => item.options.cache === "reload"));
  assert(worker.freshRequests.every(item => new URL(item.url).searchParams.get("wurstbrot-cache") === CURRENT_CACHE));
});

test("existing VT.4 user switches immediately after the complete VT.5 precache", async () => {
  const url = "https://example.test/wurstbrot-suite/";
  const worker = createWorker({
    cacheNames: ["wurstbrot-1.0.0-stable-vt4", "other-app-cache"],
    clients: [url],
  });
  await worker.dispatch("install");
  await worker.dispatch("activate");

  assert.equal(worker.calls.skipWaiting, 1);
  assert.equal(worker.calls.claim, 1);
  assert.deepEqual(worker.deletedCaches, ["wurstbrot-1.0.0-stable-vt4"]);
  assert.deepEqual(worker.windows[0].navigations, [url]);
  assert(worker.storedCaches.has(CURRENT_CACHE));
  assert(worker.storedCaches.has("other-app-cache"));
});

test("an old open tab is navigated once without blocking controller activation", async () => {
  const url = "https://example.test/wurstbrot-suite/?old-client=1";
  const worker = createWorker({cacheNames: ["wurstbrot-1.0.0-rc.2-ui-labels"], clients: [url]});
  await worker.dispatch("install");
  await worker.dispatch("activate");
  assert.deepEqual(worker.windows[0].navigations, [url]);
});

test("all open tabs are refreshed exactly once during an old-to-new update", async () => {
  const urls = [
    "https://example.test/wurstbrot-suite/",
    "https://example.test/wurstbrot-suite/?view=tree#rank-4",
  ];
  const worker = createWorker({cacheNames: ["wurstbrot-1.0.0-rc.1"], clients: urls});
  await worker.dispatch("install");
  await worker.dispatch("activate");
  assert.deepEqual(worker.windows.map(client => client.navigations), urls.map(url => [url]));
});

test("normal activation with only the current cache cannot start a reload loop", async () => {
  const url = "https://example.test/wurstbrot-suite/";
  const worker = createWorker({cacheNames: [CURRENT_CACHE, "other-app-cache"], clients: [url]});
  await worker.dispatch("activate");
  await worker.dispatch("activate");

  assert.equal(worker.calls.claim, 2);
  assert.equal(worker.calls.matchAll, 0);
  assert.deepEqual(worker.windows[0].navigations, []);
  assert.deepEqual(worker.deletedCaches, []);
  assert(worker.storedCaches.has("other-app-cache"));
});

test("failed precache does not force the incomplete worker to take over", async () => {
  const worker = createWorker({cacheNames: ["wurstbrot-1.0.0-stable"], failPrecache: true});
  await assert.rejects(worker.dispatch("install"), /precache failed/);
  assert.equal(worker.calls.skipWaiting, 0);
  assert.equal(worker.calls.claim, 0);
});

test("fetch remains cache-first and falls back to the network", async () => {
  const cached = {cached: true};
  const cacheWorker = createWorker({cacheHit: cached});
  const cacheResponse = await cacheWorker.dispatch("fetch", "asset.js");
  assert.equal(await cacheResponse, cached);
  assert.equal(cacheWorker.calls.network, 0);

  const networkWorker = createWorker();
  const networkResponse = await networkWorker.dispatch("fetch", "asset.js");
  assert.deepEqual(await networkResponse, {ok: true, network: "asset.js"});
  assert.equal(networkWorker.calls.network, 1);
});
