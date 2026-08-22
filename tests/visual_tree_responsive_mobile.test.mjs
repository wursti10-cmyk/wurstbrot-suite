import assert from "node:assert/strict";
import {readFile} from "node:fs/promises";
import test from "node:test";

import {calculate, validateDatabase} from "../apps/web/solver.mjs";
import {buildVisualTreeHighlight, buildVisualTreeLayout} from "../apps/web/visual-tree.mjs";
import {
  TREE_PAN_THRESHOLD,
  changeTreeZoom,
  clampTreeScrollPosition,
  createTreeAbState,
  panScrollPosition,
  pointerMovementExceedsThreshold,
  setTreeAbEndpoint,
} from "../apps/web/visual-tree-interaction.mjs";

const root = new URL("../", import.meta.url);
const [database, html, styles, app, interaction, worker] = await Promise.all([
  readFile(new URL("data/samples/WT_Database_2.57.1.67.json", root), "utf8")
    .then(JSON.parse).then(validateDatabase),
  readFile(new URL("apps/web/index.html", root), "utf8"),
  readFile(new URL("apps/web/styles.css", root), "utf8"),
  readFile(new URL("apps/web/app.js", root), "utf8"),
  readFile(new URL("apps/web/visual-tree-interaction.mjs", root), "utf8"),
  readFile(new URL("apps/web/service-worker.js", root), "utf8"),
]);

const targetViewports = Object.freeze([
  [320, 568], [360, 640], [390, 844], [412, 915],
  [768, 1024], [1024, 768], [1366, 768], [1920, 1080],
]);

test("VT.6 declares one responsive surface for every required viewport and safe area", () => {
  assert.equal(targetViewports.length, 8);
  assert(targetViewports.some(([width, height]) => width < height));
  assert(targetViewports.some(([width, height]) => width > height));
  assert.match(html, /name="viewport" content="width=device-width,initial-scale=1"/);
  assert.doesNotMatch(html, /user-scalable\s*=\s*no|maximum-scale\s*=\s*1/i);
  assert.match(styles, /@media \(max-width: 900px\), \(max-height: 520px\) and \(max-width: 1024px\)/);
  assert.match(styles, /@media \(max-width: 480px\)/);
  assert.match(styles, /env\(safe-area-inset-(top|right|bottom|left)/);
  assert.match(styles, /min-height: 44px/);
});

test("320px page contract keeps overflow inside the shared tree viewport", () => {
  assert.match(styles, /body\s*\{[\s\S]*max-width: 100%/);
  assert.match(styles, /#app-main, \.app-view, \.card \{ min-width: 0; \}/);
  assert.match(styles, /\.tree-panel\s*\{[\s\S]*min-width: 0;[\s\S]*overflow: hidden/);
  assert.match(styles, /\.tree-viewport\s*\{[\s\S]*overflow: auto/);
  assert.match(styles, /\.visual-tree\s*\{[\s\S]*min-width: max\(100%, calc\(var\(--active-columns/);
  assert.match(styles, /overflow-wrap: anywhere/);
});

test("tap stays a tap until the shared pointer threshold is exceeded", () => {
  assert.equal(TREE_PAN_THRESHOLD, 6);
  assert.equal(pointerMovementExceedsThreshold({x: 10, y: 10}, {x: 13, y: 14}), false);
  assert.equal(pointerMovementExceedsThreshold({x: 10, y: 10}, {x: 16, y: 10}), true);
  assert.equal(pointerMovementExceedsThreshold({x: 10, y: 10}, {x: 100, y: 100}), true);
  assert.match(app, /event\.isPrimary/);
  assert.match(app, /event\.pointerType === "mouse"/);
  assert.match(app, /pointerMovementExceedsThreshold/);
  assert.match(app, /event\.target\.closest\("\.tree-vehicle, button, input, select, a"\)/);
  assert.match(styles, /touch-action: pan-x pan-y pinch-zoom/);
  assert.doesNotMatch(styles, /touch-action:\s*none/);
});

test("pan and resize clamping never produce negative or empty-space scroll positions", () => {
  const dragged = panScrollPosition(
    {left: 300, top: 200}, {x: 100, y: 80}, {x: 40, y: 20},
  );
  assert.deepEqual(dragged, {left: 360, top: 260});
  assert.deepEqual(
    clampTreeScrollPosition(dragged, {
      scrollWidth: 1400, clientWidth: 320, scrollHeight: 1800, clientHeight: 568,
    }),
    dragged,
  );
  assert.deepEqual(
    clampTreeScrollPosition({left: 9000, top: 9000}, {
      scrollWidth: 1400, clientWidth: 768, scrollHeight: 1800, clientHeight: 1024,
    }),
    {left: 632, top: 776},
  );
  assert.deepEqual(
    clampTreeScrollPosition({left: -10, top: -20}, {
      scrollWidth: 320, clientWidth: 390, scrollHeight: 500, clientHeight: 844,
    }),
    {left: 0, top: 0},
  );
});

test("resize and orientation refresh geometry without starting the solver", () => {
  assert.match(app, /window\.addEventListener\("resize", scheduleTreeGeometryRefresh\)/);
  assert.match(app, /window\.addEventListener\("orientationchange", scheduleTreeGeometryRefresh\)/);
  assert.match(app, /new ResizeObserver\(scheduleTreeGeometryRefresh\)/);
  const refresh = app.match(/function scheduleTreeGeometryRefresh\(\) \{[\s\S]*?\n\}/)?.[0];
  assert.ok(refresh);
  assert.match(refresh, /clampTreeViewportScroll\(\)/);
  assert.match(refresh, /drawConnections\(\)/);
  assert.doesNotMatch(refresh, /calculate|executeCalculation|refreshVisualTree/);
});

test("the shared tree state survives calculator synchronization for rejected hidden targets", () => {
  assert.match(app, /const authoritativeTreeState = treeAbState;/);
  assert.match(app, /if \(origin === "tree"\) syncCalculatorFromTreeState\(\);[\s\S]*if \(origin === "tree"\) treeAbState = authoritativeTreeState;[\s\S]*if \(!treeAbState\.targetId\)/);
});

test("mobile search, details, results and folder text keep their existing shared DOM", () => {
  assert.match(styles, /\.tree-search-results\s*\{[\s\S]*45dvh/);
  assert.match(styles, /\.tree-search-result strong, \.tree-search-result span \{ overflow-wrap: anywhere; \}/);
  assert.match(styles, /\.tree-selection dd \{ overflow-wrap: anywhere/);
  assert.match(styles, /\.tree-ab-endpoint strong\s*\{[\s\S]*overflow-wrap: anywhere/);
  assert.match(styles, /\.tree-result-summary strong, \.tree-result-summary span, \.tree-result-summary small/);
  assert.match(styles, /\.folder-semantics, \.folder-state, \.folder-data-notice/);
  for (const id of ["tree-search-input", "tree-selection-details", "tree-ab-bar", "tree-result-summary", "tree-viewport"]) {
    assert.equal(html.split(`id="${id}"`).length - 1, 1, id);
  }
});

test("Tiger route, A/B state and highlights survive every viewport and zoom contract", async () => {
  const startId = "germ_pzkpfw_VI_ausf_h1_tiger";
  const targetId = "germ_leopard_2a7v";
  let state = setTreeAbEndpoint(database, createTreeAbState(), "start", startId);
  state = setTreeAbEndpoint(database, state, "target", targetId);
  const result = calculate(database, {
    startId,
    targetId,
    progress: {vehicles: {}, ownedGe: 0, convertibleRp: null},
    slDiscount: 0,
    optimizeFor: "ge",
  });
  const layout = await buildVisualTreeLayout(database, {
    countryId: "country_germany", branchId: "army",
  });
  const highlight = await buildVisualTreeHighlight(layout, result, {
    userResultSource: "legacy", calculationStatus: "complete",
  });
  const direct = Object.values(highlight.node_states)
    .filter(states => states.includes("required_direct_path")).length;
  const additional = Object.values(highlight.node_states)
    .filter(states => states.includes("required_rank_unlock")).length;
  assert.deepEqual([result.requiredVehicleIds.length, result.totalRp, result.totalSl, result.totalGe],
    [40, 4_245_100, 13_825_000, 94_351]);
  assert.deepEqual([direct, additional, highlight.required_edge_ids.length], [11, 29, 10]);
  for (const [width, height] of targetViewports) {
    for (const zoom of [0.5, 1, 1.5]) {
      const clamped = clampTreeScrollPosition(
        {left: 5000 * zoom, top: 5000 * zoom},
        {scrollWidth: 1800 * zoom, clientWidth: width, scrollHeight: 5400 * zoom, clientHeight: height},
      );
      assert(clamped.left >= 0 && clamped.top >= 0);
      assert.equal(state.startId, startId);
      assert.equal(state.targetId, targetId);
      assert.equal(result.requiredVehicleIds.length, 40);
    }
  }
  assert.equal(changeTreeZoom(1, "out"), 0.9);
  assert.equal(changeTreeZoom(0.5, "out"), 0.5);
  assert.equal(changeTreeZoom(1.5, "in"), 1.5);
});

test("VT.6 remains one renderer, one state, one solver and advances only the web cache", () => {
  assert.doesNotMatch(app, /mobile(Tree|State|Solver|Search)|desktopTree/i);
  assert.doesNotMatch(interaction, /from\s+["'][^"']*solver|function\s+(solve|calculate)\b/);
  assert.equal((app.match(/import \{calculate, validateDatabase\} from "\.\/solver\.mjs";/g) || []).length, 1);
  assert.match(worker, /wurstbrot-1\.0\.0-stable-vt7/);
  assert.doesNotMatch(worker, /wurstbrot-1\.0\.0-stable-vt5/);
  assert.match(worker, /skipWaiting/);
  assert.match(worker, /clients\.claim/);
  assert.match(worker, /key\.startsWith\(CACHE_PREFIX\) && key !== CACHE/);
});
