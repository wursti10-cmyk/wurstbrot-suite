import assert from "node:assert/strict";
import {readFile} from "node:fs/promises";
import {performance} from "node:perf_hooks";
import test from "node:test";

import {calculate, validateDatabase} from "../apps/web/solver.mjs";
import {
  BRANCH_ORDER,
  KNOWN_PARTIAL_VEHICLE_IDS,
  availableTrees,
  buildVisualTreeHighlight,
  buildVisualTreeLayout,
  renderTreeMarkup,
} from "../apps/web/visual-tree.mjs";

const root = new URL("../", import.meta.url);
const database = validateDatabase(JSON.parse(await readFile(
  new URL("data/samples/WT_Database_2.57.1.67.json", root), "utf8",
)));
const partialDossier = JSON.parse(await readFile(
  new URL("accuracy/research/partial_folder_cases_2.57.1.67.json", root), "utf8",
));

async function allLayouts() {
  const trees = [...availableTrees(database).keys()].sort();
  return Promise.all(trees.map(async key => {
    const [countryId, branchId] = key.split("/");
    return buildVisualTreeLayout(database, {countryId, branchId});
  }));
}

test("productive renderer projects and renders all 44 trees deterministically", async () => {
  const started = performance.now();
  const layouts = await allLayouts();
  assert.equal(layouts.length, 44);
  assert.equal(layouts.reduce((sum, layout) => sum + layout.nodes.length, 0), 2232);

  const renderedIds = [];
  for (const layout of layouts) {
    const repeated = await buildVisualTreeLayout(database, {
      countryId: layout.country_id,
      branchId: layout.branch_id,
    });
    assert.equal(repeated.fingerprint, layout.fingerprint);
    assert.deepEqual(repeated.nodes, layout.nodes);
    const markup = renderTreeMarkup(layout);
    assert.equal((markup.match(/data-vehicle-id=/g) || []).length, layout.nodes.length);
    assert.equal((markup.match(/class="tree-rank"/g) || []).length, layout.ranks.length);
    assert.doesNotMatch(markup, /undefined|NaN/);
    renderedIds.push(...layout.nodes.map(node => node.vehicle_id));
  }
  assert.equal(new Set(renderedIds).size, 2232);
  assert.ok(performance.now() - started < 15000, "all trees render within a practical CI budget");
});

test("renderer keeps ranks, columns, folders and authoritative edges exact", async () => {
  const byId = new Map(database.vehicles.map(vehicle => [vehicle.id, vehicle]));
  for (const layout of await allLayouts()) {
    const nodeIds = new Set(layout.nodes.map(node => node.vehicle_id));
    for (const node of layout.nodes) {
      const source = byId.get(node.vehicle_id);
      assert.equal(node.country_id, source.countryId);
      assert.equal(node.branch_id, source.branchId);
      assert.equal(node.rank, source.rank);
      assert.equal(node.column, source.column);
      assert.equal(node.order, source.order);
      assert.equal(node.group_id, source.group || null);
      assert.equal(node.group_index, source.groupIndex || 0);
      assert.equal(node.rp, source.rp);
      assert.equal(node.sl, source.sl);
    }
    const expectedEdges = Object.entries(database.predecessors || {})
      .filter(([target, source]) => source && nodeIds.has(target) && nodeIds.has(source))
      .map(([target, source]) => `${source}->${target}`)
      .sort();
    const actualEdges = layout.edges
      .map(edge => `${edge.source_vehicle_id}->${edge.target_vehicle_id}`)
      .sort();
    assert.deepEqual(actualEdges, expectedEdges);
    for (const folder of layout.folders) {
      assert.deepEqual(
        folder.present_member_ids,
        (database.groups[folder.group_id] || []).filter(vehicleId => nodeIds.has(vehicleId)),
      );
    }
  }
});

test("nation and tree switching covers 44 trees and six unavailable combinations", async () => {
  const countries = [...new Set(database.vehicles.map(vehicle => vehicle.countryId))].sort();
  assert.equal(countries.length, 10);
  assert.deepEqual(BRANCH_ORDER, ["army", "aviation", "helicopters", "boats", "ships"]);
  let available = 0;
  let unavailable = 0;
  for (const countryId of countries) {
    for (const branchId of BRANCH_ORDER) {
      const layout = await buildVisualTreeLayout(database, {countryId, branchId});
      if (layout) available += 1;
      else {
        unavailable += 1;
        assert.match(renderTreeMarkup(layout), /Nicht verfügbar/);
      }
    }
  }
  assert.equal(available, 44);
  assert.equal(unavailable, 6);
});

test("all 14 known partial vehicles remain visibly unresolved", async () => {
  const expected = partialDossier.caseEvidence.map(item => item.target_vehicle_id).sort();
  assert.equal(partialDossier.caseCount, 14);
  assert.deepEqual([...KNOWN_PARTIAL_VEHICLE_IDS].sort(), expected);
  const layouts = await allLayouts();
  for (const vehicleId of expected) {
    const layout = layouts.find(item => item.nodes.some(node => node.vehicle_id === vehicleId));
    assert.ok(layout, vehicleId);
    const markup = renderTreeMarkup(layout);
    const card = markup.match(new RegExp(
      `<article class="([^"]+)" data-vehicle-id="${vehicleId.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}"`,
    ));
    assert.ok(card, vehicleId);
    assert.match(card[1], /partial-unresolved/);
  }
});

test("A/B demonstration consumes exactly the unchanged Legacy solver result", async () => {
  const layout = await buildVisualTreeLayout(database, {
    countryId: "country_germany",
    branchId: "army",
  });
  const result = calculate(database, {
    startId: "germ_pzkpfw_VI_ausf_h1_tiger",
    targetId: "germ_leopard_2a7v",
    progress: {vehicles: {}, ownedGe: 0, convertibleRp: null},
    slDiscount: 0,
    optimizeFor: "ge",
  });
  const highlight = await buildVisualTreeHighlight(layout, result, {
    userResultSource: "legacy",
    calculationStatus: "complete",
  });
  const highlighted = Object.entries(highlight.node_states)
    .filter(([, states]) => states.some(state => state.startsWith("required_")))
    .map(([vehicleId]) => vehicleId)
    .sort();
  assert.deepEqual(highlighted, [...result.requiredVehicleIds].sort());
  assert.equal(highlight.start_vehicle_id, result.startVehicleId);
  assert.equal(highlight.target_vehicle_id, result.targetVehicleId);
  assert.equal(highlight.user_result_source, "legacy");
  assert.equal(highlight.complete, true);
  const authoritativeEdges = new Set(layout.edges.map(
    edge => `${edge.source_vehicle_id}->${edge.target_vehicle_id}`,
  ));
  for (const edgeId of highlight.required_edge_ids) assert.ok(authoritativeEdges.has(edgeId));
  const markup = renderTreeMarkup(layout, highlight);
  assert.match(markup, /start-a/);
  assert.match(markup, /target-b/);
  assert.match(markup, /required-direct-path/);
});

test("production view is isolated from solver logic and copied game assets", async () => {
  const html = await readFile(new URL("apps/web/index.html", root), "utf8");
  const renderer = await readFile(new URL("apps/web/visual-tree.mjs", root), "utf8");
  const app = await readFile(new URL("apps/web/app.js", root), "utf8");
  assert.match(html, /Rechner/);
  assert.match(html, /Forschungsbaum/);
  assert.match(html, /tree-country/);
  assert.match(html, /tree-branch/);
  assert.doesNotMatch(renderer, /from\s+["'][^"']*solver|function\s+(solve|calculate)\b/);
  assert.doesNotMatch(renderer, /warthunder\.com|wiki\.warthunder\.com|<img\b/i);
  assert.match(app, /buildVisualTreeLayout/);
  assert.match(app, /buildVisualTreeHighlight/);
});
