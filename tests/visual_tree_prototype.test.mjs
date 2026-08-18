import assert from "node:assert/strict";
import {readFile} from "node:fs/promises";
import test from "node:test";


const root = new URL("../", import.meta.url);
const prototypeRoot = new URL("apps/visual-tech-tree-prototype/", root);
const payload = JSON.parse(await readFile(new URL("germany-army.json", prototypeRoot), "utf8"));


test("prototype is isolated and contains exactly one real Germany army tree", () => {
  assert.equal(payload.prototype.status, "isolated_foundation");
  assert.equal(payload.prototype.productiveBrowserReplacement, false);
  assert.equal(payload.layout.country_id, "country_germany");
  assert.equal(payload.layout.branch_id, "army");
  assert.equal(payload.layout.nodes.length, 114);
  assert.equal(new Set(payload.layout.nodes.map(node => node.vehicle_id)).size, 114);
  assert.ok(payload.layout.nodes.every(node => node.country_id === "country_germany"));
  assert.ok(payload.layout.nodes.every(node => node.branch_id === "army"));
});


test("prototype highlight is a projection of the serialized solver result", () => {
  const highlighted = Object.entries(payload.highlight.node_states)
    .filter(([, states]) => states.some(state => state.startsWith("required_")))
    .map(([vehicleId]) => vehicleId)
    .sort();
  assert.deepEqual(highlighted, [...payload.solverSummary.requiredVehicleIds].sort());
  assert.equal(payload.highlight.user_result_source, "legacy");
  assert.equal(payload.highlight.calculation_status, "complete");
  assert.equal(payload.highlight.complete, true);

  const edges = new Set(payload.layout.edges.map(
    edge => `${edge.source_vehicle_id}->${edge.target_vehicle_id}`,
  ));
  for (const edgeId of payload.highlight.required_edge_ids) assert.ok(edges.has(edgeId));
});


test("prototype uses original text and CSS without copied game assets or a browser solver", async () => {
  const html = await readFile(new URL("index.html", prototypeRoot), "utf8");
  const app = await readFile(new URL("app.js", prototypeRoot), "utf8");
  assert.doesNotMatch(html, /<img\b/i);
  assert.doesNotMatch(html, /warthunder\.com|wiki\.warthunder\.com/i);
  assert.doesNotMatch(app, /function\s+(solve|calculate)\b|from\s+["'][^"']*solver/i);
  assert.match(html, /ISOLIERTER PROTOTYP/);
});
