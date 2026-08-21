import assert from "node:assert/strict";
import {readFile} from "node:fs/promises";
import {performance} from "node:perf_hooks";
import test from "node:test";

import {validateDatabase} from "../apps/web/solver.mjs";
import {
  KNOWN_PARTIAL_VEHICLE_IDS,
  availableTrees,
  buildVisualTreeLayout,
  renderTreeMarkup,
} from "../apps/web/visual-tree.mjs";
import {
  TREE_ZOOM_MAX,
  TREE_ZOOM_MIN,
  buildVehicleSearchIndex,
  changeTreeZoom,
  connectionGeometry,
  findVehicleSearchEntry,
  normalizeVehicleSearchText,
  panScrollPosition,
  searchVehicleIndex,
  selectedDirectEdgeIds,
  selectedVehicleDetails,
} from "../apps/web/visual-tree-interaction.mjs";

const root = new URL("../", import.meta.url);
const database = validateDatabase(JSON.parse(await readFile(
  new URL("data/samples/WT_Database_2.57.1.67.json", root), "utf8",
)));
const index = buildVehicleSearchIndex(database);

async function allLayouts() {
  return Promise.all([...availableTrees(database).keys()].sort().map(key => {
    const [countryId, branchId] = key.split("/");
    return buildVisualTreeLayout(database, {countryId, branchId});
  }));
}

test("global search indexes every vehicle with stable identity and context", () => {
  assert.equal(index.length, 2232);
  assert.equal(new Set(index.map(entry => entry.vehicle_id)).size, 2232);
  assert(index.every(entry => entry.country_label && entry.branch_label && entry.rank >= 1));
  assert.equal(findVehicleSearchEntry(index, "germ_leopard_1a5")?.name, "Leopard 1A5");
});

test("search is normalized, case-insensitive and deterministic without fuzzy matching", () => {
  assert.equal(normalizeVehicleSearchText("  Bf-109 ÄÖÜ ß  "), "bf 109 aou ss");
  const lower = searchVehicleIndex(index, "leopard 1a5");
  const upper = searchVehicleIndex(index, "LEOPARD 1A5");
  assert.deepEqual(upper, lower);
  assert.equal(lower[0].vehicle_id, "germ_leopard_1a5");
  assert.equal(searchVehicleIndex(index, "leoprad 1a5").length, 0, "no fuzzy correction");
  assert.deepEqual(
    searchVehicleIndex(index, "deutschland panzer leopard 1a5").map(item => item.vehicle_id),
    ["germ_leopard_1a5"],
  );
});

test("duplicate names remain distinguishable by nation, tree, rank and ID", () => {
  const grouped = Map.groupBy(index, entry => entry.normalized_name);
  const duplicates = [...grouped.values()].find(entries => entries.length > 1);
  assert.ok(duplicates);
  assert(duplicates.every(entry => entry.duplicate_name));
  assert.equal(new Set(duplicates.map(entry => entry.vehicle_id)).size, duplicates.length);
  const results = searchVehicleIndex(index, duplicates[0].name);
  for (const duplicate of duplicates) {
    assert(results.some(entry => entry.vehicle_id === duplicate.vehicle_id));
  }
});

test("every search result maps to exactly one existing card in its authoritative tree", async () => {
  const started = performance.now();
  const layouts = await allLayouts();
  const occurrences = new Map();
  for (const layout of layouts) {
    const markup = renderTreeMarkup(layout);
    for (const node of layout.nodes) {
      occurrences.set(node.vehicle_id, (occurrences.get(node.vehicle_id) || 0) + 1);
      const token = `data-vehicle-id="${node.vehicle_id}"`;
      assert.equal(markup.split(token).length - 1, 1, node.vehicle_id);
    }
  }
  assert.equal(layouts.length, 44);
  for (const key of [
    "country_germany/army",
    "country_germany/aviation",
    "country_usa/aviation",
    "country_germany/ships",
  ]) {
    assert(layouts.some(layout => `${layout.country_id}/${layout.branch_id}` === key), key);
  }
  assert.equal(occurrences.size, 2232);
  for (const entry of index) {
    assert.equal(occurrences.get(entry.vehicle_id), 1, entry.vehicle_id);
    const layout = layouts.find(item => item.country_id === entry.country_id
      && item.branch_id === entry.branch_id);
    assert(layout.nodes.some(node => node.vehicle_id === entry.vehicle_id));
  }
  assert.ok(performance.now() - started < 15000, "global lookup stays within the CI budget");
});

test("zoom stays controlled between 50 and 150 percent and resets exactly", () => {
  let zoom = 1;
  for (let step = 0; step < 20; step += 1) zoom = changeTreeZoom(zoom, "in");
  assert.equal(zoom, TREE_ZOOM_MAX);
  for (let step = 0; step < 30; step += 1) zoom = changeTreeZoom(zoom, "out");
  assert.equal(zoom, TREE_ZOOM_MIN);
  assert.equal(changeTreeZoom(zoom, "reset"), 1);
});

test("connection geometry scales with the same tree coordinate space", () => {
  const base = connectionGeometry(
    {left: 10, top: 20},
    {left: 30, top: 40, width: 20, bottom: 80},
    {left: 70, top: 120, width: 30, bottom: 160},
  );
  const scaled = connectionGeometry(
    {left: 20, top: 40},
    {left: 60, top: 80, width: 40, bottom: 160},
    {left: 140, top: 240, width: 60, bottom: 320},
  );
  for (const key of ["x1", "y1", "x2", "y2", "middle"]) {
    assert.equal(scaled[key], base[key] * 2, key);
  }
});

test("free-space panning is bounded and follows pointer displacement", () => {
  assert.deepEqual(
    panScrollPosition({left: 300, top: 200}, {x: 100, y: 80}, {x: 40, y: 20}),
    {left: 360, top: 260},
  );
  assert.deepEqual(
    panScrollPosition({left: 10, top: 5}, {x: 0, y: 0}, {x: 50, y: 50}),
    {left: 0, top: 0},
  );
});

test("card details and optional direct-edge highlight only expose existing data", async () => {
  const partialVehicleId = KNOWN_PARTIAL_VEHICLE_IDS[0];
  const vehicle = database.vehicles.find(item => item.id === partialVehicleId);
  const layout = await buildVisualTreeLayout(database, {
    countryId: vehicle.countryId,
    branchId: vehicle.branchId,
  });
  const details = selectedVehicleDetails(database, layout, partialVehicleId);
  assert.equal(details.vehicle_id, partialVehicleId);
  assert.equal(details.name, vehicle.name);
  assert.equal(details.rp, vehicle.rp);
  assert.equal(details.sl, vehicle.sl);
  assert.equal(details.group_id, vehicle.group || null);
  assert.equal(details.partial_unresolved, true);

  const authoritative = new Set(layout.edges.map(
    edge => `${edge.source_vehicle_id}->${edge.target_vehicle_id}`,
  ));
  const direct = selectedDirectEdgeIds(layout, partialVehicleId);
  assert(direct.every(edgeId => authoritative.has(edgeId)));
  assert(direct.every(edgeId => edgeId.startsWith(`${partialVehicleId}->`)
    || edgeId.endsWith(`->${partialVehicleId}`)));
});

test("production wiring provides exact selection, keyboard access and state reset without solver expansion", async () => {
  const html = await readFile(new URL("apps/web/index.html", root), "utf8");
  const app = await readFile(new URL("apps/web/app.js", root), "utf8");
  const interaction = await readFile(new URL("apps/web/visual-tree-interaction.mjs", root), "utf8");
  assert.match(html, /tree-search-input/);
  assert.match(html, /tree-zoom-(out|reset|in)/);
  assert.match(html, /tree-selection-details/);
  assert.match(app, /querySelectorAll\(`\[data-vehicle-id=/);
  const inputHandler = app.match(/\$\("tree-search-input"\)\.addEventListener\("input",[\s\S]*?\n\}\);/);
  assert.ok(inputHandler);
  assert.match(inputHandler[0], /renderSearchResults/);
  assert.doesNotMatch(inputHandler[0], /refreshVisualTree|buildVisualTreeLayout/);
  assert.match(app, /event\.key === "Enter" \|\| event\.key === " "/);
  assert.match(app, /refreshVisualTree\(\{resetNavigation: true\}\)/);
  assert.match(app, /refreshVisualTree\(\{selectVehicleId: selectedTreeVehicleId\}\)/);
  assert.match(app, /event\.target\.closest\("\.tree-vehicle, button, input, select, a"\)/);
  assert.doesNotMatch(interaction, /from\s+["'][^"']*solver|function\s+(solve|calculate)\b/);
  const treeView = html.slice(html.indexOf('<div id="tree-view"'));
  assert.doesNotMatch(treeView, /Von Fahrzeug A|Zu Fahrzeug B/);
});
