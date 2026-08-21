import assert from "node:assert/strict";
import {readFile} from "node:fs/promises";
import {performance} from "node:perf_hooks";
import test from "node:test";

import {calculate, validateDatabase} from "../apps/web/solver.mjs";
import {
  KNOWN_PARTIAL_VEHICLE_IDS,
  availableTrees,
  buildFolderMetadataSummary,
  buildVisualTreeHighlight,
  buildVisualTreeLayout,
  renderTreeMarkup,
} from "../apps/web/visual-tree.mjs";
import {
  buildTreeAbSelectionHighlight,
  buildVehicleSearchIndex,
  changeTreeZoom,
  createTreeAbState,
  panScrollPosition,
  searchVehicleIndex,
  selectedVehicleDetails,
  setTreeAbEndpoint,
} from "../apps/web/visual-tree-interaction.mjs";

const root = new URL("../", import.meta.url);
const database = validateDatabase(JSON.parse(await readFile(
  new URL("data/samples/WT_Database_2.57.1.67.json", root),
  "utf8",
)));
const searchIndex = buildVehicleSearchIndex(database);
const partialFolderIds = Object.freeze(["fiat_group", "mc200_group", "r2y2_group", "sm_79_group"]);

async function allLayouts() {
  return Promise.all([...availableTrees(database).keys()].sort().map(async key => {
    const [countryId, branchId] = key.split("/");
    return buildVisualTreeLayout(database, {countryId, branchId});
  }));
}

test("VT.5 accounts for all folder metadata without duplicate or phantom vehicles", () => {
  const summary = buildFolderMetadataSummary(database);
  assert.equal(summary.contract_version, "visual-tech-tree-folder-ux-v1");
  assert.equal(summary.folder_count, 395);
  assert.equal(summary.present_member_count, 821);
  assert.equal(summary.missing_member_count, 28);
  assert.equal(summary.incomplete_folder_count, 13);
  assert.equal(summary.non_displayable_folder_count, 6);

  const presentIds = summary.folders.flatMap(folder => folder.present_member_ids);
  assert.equal(new Set(presentIds).size, 821, "folder members are not duplicated");
  const vehiclesById = new Map(database.vehicles.map(vehicle => [vehicle.id, vehicle]));
  for (const folder of summary.folders) {
    for (const vehicleId of folder.present_member_ids) {
      const vehicle = vehiclesById.get(vehicleId);
      assert.equal(vehicle.group, folder.group_id, vehicleId);
      assert.equal(vehicle.groupIndex, folder.declared_member_ids.indexOf(vehicleId), vehicleId);
    }
  }
  const emptyFolders = summary.folders.filter(folder => !folder.displayable);
  assert.equal(emptyFolders.flatMap(folder => folder.missing_member_ids).length, 18);
  assert(emptyFolders.every(folder => folder.present_member_ids.length === 0));
});

test("visible folders render once with member counts and incomplete-data notices", async () => {
  const layouts = await allLayouts();
  assert.equal(layouts.length, 44);
  assert.equal(layouts.flatMap(layout => layout.folders).length, 389);
  assert.equal(layouts.flatMap(layout => layout.folders)
    .reduce((total, folder) => total + folder.present_member_ids.length, 0), 821);
  assert.equal(layouts.flatMap(layout => layout.folders)
    .reduce((total, folder) => total + folder.missing_member_ids.length, 0), 10);
  assert.equal(layouts.flatMap(layout => layout.folders)
    .filter(folder => folder.missing_member_count > 0).length, 7);

  const missingIds = new Set(buildFolderMetadataSummary(database).folders
    .flatMap(folder => folder.missing_member_ids));
  for (const layout of layouts) {
    const markup = renderTreeMarkup(layout);
    for (const folder of layout.folders) {
      assert.equal(markup.split(`data-folder-id="${folder.group_id}"`).length - 1, 1);
      assert.match(markup, /data-folder-reveal="always"/);
      for (const vehicleId of folder.present_member_ids) {
        assert.equal(markup.split(`data-vehicle-id="${vehicleId}"`).length - 1, 1, vehicleId);
      }
      if (folder.missing_member_count) assert.match(markup, /Folder-Daten unvollständig/);
    }
    for (const missingId of missingIds) assert.doesNotMatch(markup, new RegExp(`data-vehicle-id="${missingId}"`));
  }
});

test("the four known hidden folder groups remain explicit partial and unresolved", async () => {
  const layouts = await allLayouts();
  const partialIds = new Set(KNOWN_PARTIAL_VEHICLE_IDS);
  assert.equal(partialIds.size, 14);
  const counts = new Map(partialFolderIds.map(groupId => [groupId, 0]));
  for (const vehicle of database.vehicles) {
    if (partialIds.has(vehicle.id)) {
      assert.equal(vehicle.hiddenResearch, true, vehicle.id);
      assert(counts.has(vehicle.group), vehicle.id);
      counts.set(vehicle.group, counts.get(vehicle.group) + 1);
    }
  }
  assert.deepEqual(Object.fromEntries(counts), {
    fiat_group: 3,
    mc200_group: 3,
    r2y2_group: 3,
    sm_79_group: 5,
  });
  for (const groupId of partialFolderIds) {
    const layout = layouts.find(item => item.folders.some(folder => folder.group_id === groupId));
    const markup = renderTreeMarkup(layout);
    const section = markup.match(new RegExp(
      `<section class="tree-folder[^>]*data-folder-id="${groupId}"[\\s\\S]*?</section>`,
    ));
    assert.ok(section, groupId);
    assert.match(section[0], /Partial \/ unresolved/);
    assert.match(section[0], /Hidden/);
  }
  const partialFolderMarkupCount = layouts.map(layout => renderTreeMarkup(layout))
    .join("").match(/class="tree-folder partial-unresolved(?: incomplete-data)?"/g)?.length || 0;
  assert.equal(partialFolderMarkupCount, 4);
});

test("folder display metadata never changes authoritative research edges", async () => {
  const original = await buildVisualTreeLayout(database, {
    countryId: "country_germany",
    branchId: "army",
  });
  const changedDisplayIndex = structuredClone(database);
  for (const vehicle of changedDisplayIndex.vehicles) vehicle.groupIndex += 1000;
  const changed = await buildVisualTreeLayout(changedDisplayIndex, {
    countryId: "country_germany",
    branchId: "army",
  });
  assert.deepEqual(changed.edges, original.edges);
  const expectedEdges = Object.entries(database.predecessors)
    .filter(([target, source]) => source
      && original.nodes.some(node => node.vehicle_id === target)
      && original.nodes.some(node => node.vehicle_id === source))
    .map(([target, source]) => `${source}->${target}`).sort();
  assert.deepEqual(original.edges.map(edge => (
    `${edge.source_vehicle_id}->${edge.target_vehicle_id}`
  )).sort(), expectedEdges);
});

test("search, A/B and solver-required folder members are always revealed", async () => {
  const partialId = KNOWN_PARTIAL_VEHICLE_IDS[0];
  const partialVehicle = database.vehicles.find(vehicle => vehicle.id === partialId);
  const searchResult = searchVehicleIndex(searchIndex, partialVehicle.name)
    .find(entry => entry.vehicle_id === partialId);
  assert.ok(searchResult);
  const partialLayout = await buildVisualTreeLayout(database, {
    countryId: partialVehicle.countryId,
    branchId: partialVehicle.branchId,
  });
  assert.match(renderTreeMarkup(partialLayout), new RegExp(
    `data-vehicle-id="${partialId}"`,
  ));

  const layout = await buildVisualTreeLayout(database, {
    countryId: "country_germany",
    branchId: "army",
  });
  const startId = "germ_pzkpfw_VI_ausf_h1_tiger";
  const targetId = "germ_leopard_2a7v";
  let state = setTreeAbEndpoint(database, createTreeAbState(), "start", startId);
  state = setTreeAbEndpoint(database, state, "target", targetId);
  const selectionMarkup = renderTreeMarkup(layout, buildTreeAbSelectionHighlight(layout, state));
  assert.match(selectionMarkup, new RegExp(`data-vehicle-id="${startId}"`));
  assert.match(selectionMarkup, new RegExp(`data-vehicle-id="${targetId}"`));

  const result = calculate(database, {
    startId,
    targetId,
    progress: {vehicles: {}, ownedGe: 0, convertibleRp: null},
    slDiscount: 0,
    optimizeFor: "ge",
  });
  const highlight = await buildVisualTreeHighlight(layout, result, {
    userResultSource: "legacy",
    calculationStatus: "complete",
  });
  const resultMarkup = renderTreeMarkup(layout, highlight);
  const requiredFolderMembers = result.requiredVehicleIds.filter(vehicleId => (
    layout.nodes.find(node => node.vehicle_id === vehicleId)?.group_id
  ));
  assert(requiredFolderMembers.length > 0);
  for (const vehicleId of requiredFolderMembers) {
    assert.match(resultMarkup, new RegExp(`data-vehicle-id="${vehicleId}"`));
  }
  assert.equal(result.requiredVehicleIds.length, 40);
  assert.equal(result.totalRp, 4_245_100);
  assert.equal(result.totalSl, 13_825_000);
  assert.equal(result.totalGe, 94_351);
  assert.equal(highlight.required_edge_ids.length, 10);
});

test("folder details distinguish grouping, missing data, hidden and partial states", async () => {
  const partialId = "sm_79_1936";
  const vehicle = database.vehicles.find(item => item.id === partialId);
  const layout = await buildVisualTreeLayout(database, {
    countryId: vehicle.countryId,
    branchId: vehicle.branchId,
  });
  const details = selectedVehicleDetails(database, layout, partialId);
  assert.equal(details.group_id, "sm_79_group");
  assert.equal(details.group_index, vehicle.groupIndex);
  assert.equal(details.folder_visible_member_count, 5);
  assert.equal(details.folder_declared_member_count, 7);
  assert.equal(details.folder_missing_member_count, 2);
  assert.equal(details.folder_data_incomplete, true);
  assert.equal(details.hidden_research, true);
  assert.equal(details.partial_unresolved, true);
});

test("representative folder-heavy trees retain zoom, pan and practical render performance", async () => {
  const started = performance.now();
  for (const [countryId, branchId] of [
    ["country_germany", "army"],
    ["country_germany", "aviation"],
    ["country_italy", "aviation"],
    ["country_japan", "aviation"],
    ["country_germany", "ships"],
  ]) {
    const layout = await buildVisualTreeLayout(database, {countryId, branchId});
    const markup = renderTreeMarkup(layout);
    assert.equal((markup.match(/data-vehicle-id=/g) || []).length, layout.nodes.length);
    assert.equal((markup.match(/data-folder-reveal="always"/g) || []).length, layout.folders.length);
  }
  assert.equal(changeTreeZoom(1, "out"), 0.9);
  assert.equal(changeTreeZoom(0.5, "out"), 0.5);
  assert.equal(changeTreeZoom(1.5, "in"), 1.5);
  assert.equal(changeTreeZoom(0.9, "reset"), 1);
  assert.deepEqual(
    panScrollPosition({left: 300, top: 200}, {x: 100, y: 80}, {x: 40, y: 20}),
    {left: 360, top: 260},
  );
  assert.ok(performance.now() - started < 15_000);
});

test("production folder UX is accessible, static and isolated from solver semantics", async () => {
  const [html, app, renderer, styles, worker] = await Promise.all([
    readFile(new URL("apps/web/index.html", root), "utf8"),
    readFile(new URL("apps/web/app.js", root), "utf8"),
    readFile(new URL("apps/web/visual-tree.mjs", root), "utf8"),
    readFile(new URL("apps/web/styles.css", root), "utf8"),
    readFile(new URL("apps/web/service-worker.js", root), "utf8"),
  ]);
  assert.match(html, /Folder gruppieren Karten und erzeugen keine Forschungsbeziehung/);
  assert.match(html, /Hidden \(Altbestand\)/);
  assert.match(app, /Folder-Position/);
  assert.match(app, /Darstellungsmetadatum/);
  assert.match(renderer, /role="group" aria-label=/);
  assert.match(renderer, /Gruppierung · keine Forschungsbeziehung/);
  assert.doesNotMatch(renderer, /aria-expanded|folder-toggle|collapse/i);
  assert.match(styles, /\.folder-data-notice/);
  assert.doesNotMatch(renderer, /from\s+["'][^"']*solver|function\s+(solve|calculate)\b/);
  assert.match(worker, /wurstbrot-1\.0\.0-stable-vt5/);
});
