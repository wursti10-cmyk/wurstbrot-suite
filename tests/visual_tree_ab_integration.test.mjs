import assert from "node:assert/strict";
import {readFile} from "node:fs/promises";
import {performance} from "node:perf_hooks";
import test from "node:test";

import {calculate, validateDatabase} from "../apps/web/solver.mjs";
import {
  KNOWN_PARTIAL_VEHICLE_IDS,
  buildVisualTreeHighlight,
  buildVisualTreeLayout,
  renderTreeMarkup,
} from "../apps/web/visual-tree.mjs";
import {
  attachTreeAbResult,
  buildTreeAbSelectionHighlight,
  buildVehicleSearchIndex,
  changeTreeZoom,
  createTreeAbState,
  findVehicleSearchEntry,
  panScrollPosition,
  resetTreeAbState,
  searchVehicleIndex,
  setTreeAbEndpoint,
  treeAbMatchesLayout,
  treeAbTreeKey,
  treeResultPresentation,
} from "../apps/web/visual-tree-interaction.mjs";

const root = new URL("../", import.meta.url);
const database = validateDatabase(JSON.parse(await readFile(
  new URL("data/samples/WT_Database_2.57.1.67.json", root), "utf8",
)));
const prototype = JSON.parse(await readFile(
  new URL("apps/visual-tech-tree-prototype/germany-army.json", root), "utf8",
));
const START_ID = "germ_pzkpfw_VI_ausf_h1_tiger";
const TARGET_ID = "germ_leopard_2a7v";

function referenceResult() {
  return calculate(database, {
    startId: START_ID,
    targetId: TARGET_ID,
    progress: {vehicles: {}, ownedGe: 0, convertibleRp: null},
    slDiscount: 0,
    optimizeFor: "ge",
  });
}

test("A/B selection is explicit, replaceable and resettable without route inference", async () => {
  const layout = await buildVisualTreeLayout(database, {
    countryId: "country_germany",
    branchId: "army",
  });
  const empty = createTreeAbState();
  const withStart = setTreeAbEndpoint(database, empty, "start", START_ID);
  const withBoth = setTreeAbEndpoint(database, withStart, "target", TARGET_ID);
  assert.deepEqual(empty, resetTreeAbState(), "endpoint updates do not mutate the source state");
  assert.equal(withBoth.startId, START_ID);
  assert.equal(withBoth.targetId, TARGET_ID);
  assert.equal(treeAbTreeKey(database, withBoth), "country_germany/army");
  assert.equal(treeAbMatchesLayout(database, withBoth, layout), true);

  const selection = buildTreeAbSelectionHighlight(layout, withBoth);
  assert(selection.node_states[START_ID].includes("start_a"));
  assert(selection.node_states[TARGET_ID].includes("target_b"));
  assert.deepEqual(selection.required_edge_ids, []);
  assert.equal(selection.user_result_source, null);
  assert.equal(selection.complete, false);
  const markup = renderTreeMarkup(layout, selection);
  assert.equal(markup.match(/\bstart-a\b/g)?.length, 1);
  assert.equal(markup.match(/\btarget-b\b/g)?.length, 1);
  assert.match(markup, /A · Start/);
  assert.match(markup, /B · Ziel/);
});

test("cross-tree endpoint rejection is clear and preserves the valid state", () => {
  const usaTarget = database.vehicles.find(vehicle => vehicle.countryId === "country_usa"
    && vehicle.branchId === "aviation" && !vehicle.hiddenResearch);
  const valid = setTreeAbEndpoint(database, createTreeAbState(), "start", START_ID);
  assert.throws(
    () => setTreeAbEndpoint(database, valid, "target", usaTarget.id),
    /selben Forschungsbaum/,
  );
  assert.equal(valid.startId, START_ID);
  assert.equal(valid.targetId, null);
  assert.equal(valid.result, null);
});

test("A and B can each be replaced inside the same authoritative tree", () => {
  let state = setTreeAbEndpoint(database, createTreeAbState(), "start", START_ID);
  state = setTreeAbEndpoint(database, state, "target", TARGET_ID);
  state = setTreeAbEndpoint(database, state, "start", "germ_pzkpfw_V_ausf_d_panther");
  assert.equal(state.startId, "germ_pzkpfw_V_ausf_d_panther");
  assert.equal(state.targetId, TARGET_ID);
  state = setTreeAbEndpoint(database, state, "target", "germ_leopard_2a5");
  assert.equal(state.startId, "germ_pzkpfw_V_ausf_d_panther");
  assert.equal(state.targetId, "germ_leopard_2a5");
  assert.equal(state.result, null);
});

test("global VT.3 search results can feed A and B without a manual tree lookup", () => {
  const index = buildVehicleSearchIndex(database);
  const tiger = searchVehicleIndex(index, "tiger h1").find(entry => entry.vehicle_id === START_ID);
  const leopard = searchVehicleIndex(index, "leopard 2a7v")
    .find(entry => entry.vehicle_id === TARGET_ID);
  assert.equal(findVehicleSearchEntry(index, tiger.vehicle_id).branch_id, "army");
  assert.equal(findVehicleSearchEntry(index, leopard.vehicle_id).country_id, "country_germany");
  let state = setTreeAbEndpoint(database, createTreeAbState(), "start", tiger.vehicle_id);
  state = setTreeAbEndpoint(database, state, "target", leopard.vehicle_id);
  assert.equal(treeAbTreeKey(database, state), "country_germany/army");
});

test("the existing browser solver remains the sole truth for route and totals", () => {
  const result = referenceResult();
  const presentation = treeResultPresentation(database, result);
  const golden = prototype.solverSummary;
  assert.deepEqual(result.requiredVehicleIds, golden.requiredVehicleIds);
  assert.deepEqual(
    Object.fromEntries(result.lines.map(line => [line.id, line.reason])),
    golden.requiredVehicleReasons,
  );
  assert.equal(result.totalRp, golden.totalRP);
  assert.equal(result.totalSl, golden.totalSL);
  assert.equal(result.totalGe, golden.totalGE);
  assert.equal(presentation.vehicle_count, result.requiredVehicleIds.length);
  assert.deepEqual(
    new Set([...presentation.direct_vehicle_ids, ...presentation.additional_vehicle_ids]),
    new Set(result.lines.map(line => line.id)),
  );
  assert.equal(presentation.calculation_status, "complete");
});

test("solver highlight uses only solver vehicles and authoritative layout edges", async () => {
  const result = referenceResult();
  const layout = await buildVisualTreeLayout(database, {
    countryId: "country_germany",
    branchId: "army",
  });
  let state = setTreeAbEndpoint(database, createTreeAbState(), "start", START_ID);
  state = setTreeAbEndpoint(database, state, "target", TARGET_ID);
  state = attachTreeAbResult(state, result, {
    userResultSource: "legacy",
    calculationStatus: "complete",
    fallbackReason: null,
  });
  const highlight = await buildVisualTreeHighlight(layout, state.result, {
    userResultSource: state.userResultSource,
    calculationStatus: state.calculationStatus,
    fallbackReason: state.fallbackReason,
  });
  const direct = new Set(result.lines
    .filter(line => line.reason === "direct_path").map(line => line.id));
  const additional = new Set(result.lines
    .filter(line => line.reason !== "direct_path").map(line => line.id));
  const highlightedDirect = new Set(Object.entries(highlight.node_states)
    .filter(([, states]) => states.includes("required_direct_path")).map(([id]) => id));
  const highlightedAdditional = new Set(Object.entries(highlight.node_states)
    .filter(([, states]) => states.includes("required_rank_unlock")).map(([id]) => id));
  assert.deepEqual(highlightedDirect, direct);
  assert.deepEqual(highlightedAdditional, additional);
  const authoritativeEdges = new Set(layout.edges.map(
    edge => `${edge.source_vehicle_id}->${edge.target_vehicle_id}`,
  ));
  assert(highlight.required_edge_ids.every(edgeId => authoritativeEdges.has(edgeId)));
  assert.equal(highlight.user_result_source, "legacy");
  assert.equal(highlight.fallback_reason, null);
  assert.equal(highlight.complete, true);
});

test("known hidden-folder vehicles remain visibly partial without invented totals", async () => {
  const partialId = KNOWN_PARTIAL_VEHICLE_IDS[0];
  const vehicle = database.vehicles.find(item => item.id === partialId);
  const layout = await buildVisualTreeLayout(database, {
    countryId: vehicle.countryId,
    branchId: vehicle.branchId,
  });
  const syntheticDisplayInput = {
    startVehicleId: null,
    targetVehicleId: partialId,
    requiredVehicleIds: [partialId],
    lines: [{id: partialId, reason: "direct_path"}],
    totalRp: vehicle.rp,
    totalSl: vehicle.sl,
    totalGe: 0,
  };
  const presentation = treeResultPresentation(database, syntheticDisplayInput);
  assert.equal(presentation.calculation_status, "partial");
  assert.deepEqual(presentation.partial_vehicle_ids, [partialId]);
  const highlight = await buildVisualTreeHighlight(layout, syntheticDisplayInput, {
    userResultSource: "legacy",
    calculationStatus: "partial",
    fallbackReason: "legacy_partial_fallback",
    unresolvedVehicleIds: presentation.partial_vehicle_ids,
  });
  assert(highlight.node_states[partialId].includes("partial_unresolved"));
  assert.equal(highlight.complete, false);
  assert.equal(highlight.user_result_source, "legacy");
  assert.equal(highlight.fallback_reason, "legacy_partial_fallback");
});

test("VT.4 production wiring shares one calculation pipeline and has accessible controls", async () => {
  const html = await readFile(new URL("apps/web/index.html", root), "utf8");
  const app = await readFile(new URL("apps/web/app.js", root), "utf8");
  const interaction = await readFile(
    new URL("apps/web/visual-tree-interaction.mjs", root), "utf8",
  );
  const styles = await readFile(new URL("apps/web/styles.css", root), "utf8");
  for (const id of [
    "tree-set-start", "tree-set-target", "tree-calculate", "tree-reset",
    "tree-details-calculator", "tree-ab-message", "tree-result-summary",
  ]) assert.match(html, new RegExp(`id="${id}"`), id);
  assert.match(html, /role="status" aria-live="polite"/);
  assert.equal(app.match(/calculate\(database,/g)?.length, 1, "one existing solver call site");
  assert.match(app, /executeCalculation\(\{origin: "tree"\}\)/);
  assert.match(app, /executeCalculation\(\{origin: "calculator"\}\)/);
  assert.match(app, /syncCalculatorFromTreeState/);
  assert.match(app, /if \(!treeActive\)[\s\S]*syncCalculatorFromTreeState\(\)/);
  assert.match(app, /A\/B-Auswahl wegen Forschungsbaumwechsel zurückgesetzt/);
  assert.match(app, /changed && treeAbState\.result[\s\S]*A\/B-Ergebnis wegen Forschungsbaumwechsel zurückgesetzt/);
  assert.match(app, /fallbackReason: presentation\.calculation_status === "partial"/);
  assert.doesNotMatch(interaction, /from\s+["'][^"']*solver|function\s+(solve|calculate)\b/);
  assert.doesNotMatch(app, /treeDemoResult|Solver-Demonstration/);
  assert.match(styles, /\.visual-tree\.has-highlight[^{]*\.not-required/);
  assert.doesNotMatch(styles, /\.not-required[^}]*display:\s*none/);
});

test("route state remains independent of card selection, zoom and pan transforms", () => {
  let state = setTreeAbEndpoint(database, createTreeAbState(), "start", START_ID);
  state = setTreeAbEndpoint(database, state, "target", TARGET_ID);
  state = attachTreeAbResult(state, referenceResult(), {
    userResultSource: "legacy",
    calculationStatus: "complete",
  });
  const before = state;
  assert.equal(changeTreeZoom(1, "in"), 1.1);
  assert.deepEqual(
    panScrollPosition({left: 100, top: 80}, {x: 50, y: 50}, {x: 30, y: 20}),
    {left: 120, top: 110},
  );
  assert.equal(state, before);
  assert.equal(state.result.targetVehicleId, TARGET_ID);
});

test("A/B presentation stays responsive across representative land, air and naval trees", async () => {
  const started = performance.now();
  for (const [countryId, branchId] of [
    ["country_germany", "army"],
    ["country_germany", "aviation"],
    ["country_usa", "aviation"],
    ["country_germany", "ships"],
  ]) {
    const layout = await buildVisualTreeLayout(database, {countryId, branchId});
    const [start, target] = [layout.nodes[0], layout.nodes.at(-1)];
    let state = setTreeAbEndpoint(database, createTreeAbState(), "start", start.vehicle_id);
    state = setTreeAbEndpoint(database, state, "target", target.vehicle_id);
    const highlight = buildTreeAbSelectionHighlight(layout, state);
    const markup = renderTreeMarkup(layout, highlight);
    assert.equal(highlight.start_vehicle_id, start.vehicle_id);
    assert.equal(highlight.target_vehicle_id, target.vehicle_id);
    assert.match(markup, /A · Start/);
    assert.match(markup, /B · Ziel/);
  }
  assert.ok(performance.now() - started < 15000, "representative VT.4 rendering stays within CI budget");
});
