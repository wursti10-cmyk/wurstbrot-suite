const CACHE = "wurstbrot-1.0.0-stable-vt7";
const CACHE_PREFIX = "wurstbrot-";
const ASSETS = ["./", "index.html", "styles.css", "app.js", "solver.mjs", "visual-tree.mjs", "visual-tree-interaction.mjs", "manifest.webmanifest", "icon.svg", "../../data/samples/WT_Database_2.57.1.67.json"];
self.addEventListener("install", event => event.waitUntil((async () => {
  const cache = await caches.open(CACHE);
  await Promise.all(ASSETS.map(async asset => {
    const currentUrl = new URL(asset, self.location.href);
    const freshUrl = new URL(currentUrl);
    freshUrl.searchParams.set("wurstbrot-cache", CACHE);
    const response = await fetch(freshUrl.href, {cache: "reload"});
    if (!response.ok) throw new Error(`Precache failed: ${currentUrl}`);
    await cache.put(currentUrl.href, response);
  }));
  await self.skipWaiting();
})()));
self.addEventListener("activate", event => event.waitUntil((async () => {
  const keys = await caches.keys();
  const oldCaches = keys.filter(key => key.startsWith(CACHE_PREFIX) && key !== CACHE);
  await Promise.all(oldCaches.map(key => caches.delete(key)));
  await self.clients.claim();
  if (!oldCaches.length) return;
  const windows = await self.clients.matchAll({type: "window", includeUncontrolled: true});
  windows.forEach(client => client.navigate(client.url).catch(() => {}));
})()));
self.addEventListener("fetch", event => event.respondWith(caches.match(event.request).then(hit => hit || fetch(event.request))));
