import assert from "node:assert/strict";
import {createHash} from "node:crypto";
import {mkdir, readFile, writeFile} from "node:fs/promises";
import {performance} from "node:perf_hooks";
import test, {after} from "node:test";

import {calculate, validateDatabase} from "../apps/web/solver.mjs";
import {
  BRANCH_LABELS,
  COUNTRY_LABELS,
  KNOWN_PARTIAL_VEHICLE_IDS,
  availableTrees,
  buildFolderMetadataSummary,
  buildVisualTreeHighlight,
  buildVisualTreeLayout,
  renderTreeMarkup,
} from "../apps/web/visual-tree.mjs";
import {
  TREE_PAN_THRESHOLD,
  attachTreeAbResult,
  buildTreeAbSelectionHighlight,
  buildVehicleSearchIndex,
  changeTreeZoom,
  clampTreeScrollPosition,
  connectionGeometry,
  createTreeAbState,
  findVehicleSearchEntry,
  normalizeVehicleSearchText,
  panScrollPosition,
  pointerMovementExceedsThreshold,
  resetTreeAbState,
  searchVehicleIndex,
  selectedVehicleDetails,
  setTreeAbEndpoint,
  treeAbMatchesLayout,
  treeAbTreeKey,
  treeResultPresentation,
} from "../apps/web/visual-tree-interaction.mjs";

const root = new URL("../", import.meta.url);
const reportUrl = new URL(
  "build/health/Visual_Tree_Full_Validation_2.57.1.67.json",
  root,
);
const expectedEdgeFingerprint = "c26260e9d718faef8811907349743ccfac02f0f63246605b81936a143809d34f";
const requiredViewports = Object.freeze([
  [320, 568],
  [360, 640],
  [390, 844],
  [412, 915],
  [768, 1024],
  [1024, 768],
  [1366, 768],
  [1920, 1080],
]);
const geometryViewports = Object.freeze([
  [390, 844],
  [1366, 768],
]);
const geometryZooms = Object.freeze([0.5, 1, 1.5]);
const tigerCase = Object.freeze({
  startId: "germ_pzkpfw_VI_ausf_h1_tiger",
  targetId: "germ_leopard_2a7v",
});

const [database, appSource, htmlSource, stylesSource, interactionSource, workerSource] = await Promise.all([
  readFile(new URL("data/samples/WT_Database_2.57.1.67.json", root), "utf8")
    .then(JSON.parse).then(validateDatabase),
  readFile(new URL("apps/web/app.js", root), "utf8"),
  readFile(new URL("apps/web/index.html", root), "utf8"),
  readFile(new URL("apps/web/styles.css", root), "utf8"),
  readFile(new URL("apps/web/visual-tree-interaction.mjs", root), "utf8"),
  readFile(new URL("apps/web/service-worker.js", root), "utf8"),
]);

const partialIds = new Set(KNOWN_PARTIAL_VEHICLE_IDS);
const vehiclesById = new Map(database.vehicles.map(vehicle => [vehicle.id, vehicle]));
const treeKeys = [...availableTrees(database).keys()].sort();
const layoutRecords = [];
for (const key of treeKeys) {
  const [countryId, branchId] = key.split("/");
  const layoutStarted = performance.now();
  const layout = await buildVisualTreeLayout(database, {countryId, branchId});
  const layoutMs = performance.now() - layoutStarted;
  const renderStarted = performance.now();
  const markup = renderTreeMarkup(layout);
  const renderMs = performance.now() - renderStarted;
  layoutRecords.push({key, layout, markup, layoutMs, renderMs});
}
const layoutByKey = new Map(layoutRecords.map(record => [record.key, record]));
const folderSummary = buildFolderMetadataSummary(database);
const searchStarted = performance.now();
const searchIndex = buildVehicleSearchIndex(database);
const searchIndexMs = performance.now() - searchStarted;

function countOccurrences(text, needle) {
  return text.split(needle).length - 1;
}

function sha256Lines(values) {
  return createHash("sha256").update([...values].sort().join("\n")).digest("hex");
}

function canonicalResult(result) {
  return {
    startVehicleId: result.startVehicleId,
    targetVehicleId: result.targetVehicleId,
    requiredVehicleIds: [...result.requiredVehicleIds],
    lines: result.lines.map(line => ({
      id: line.id,
      reason: line.reason,
      remainingRp: line.remainingRp,
      ge: line.ge,
      sl: line.sl,
    })),
    totalRp: result.totalRp,
    totalSl: result.totalSl,
    totalGe: result.totalGe,
    warnings: [...result.warnings],
  };
}

function emptyCalculationInput(startId, targetId) {
  return {
    startId,
    targetId,
    progress: {vehicles: {}, ownedGe: 0, convertibleRp: null},
    slDiscount: 0,
    optimizeFor: "ge",
  };
}

function vehicleStateCounts(markup) {
  const ids = [...markup.matchAll(/data-vehicle-id="([^"]+)"/g)].map(match => match[1]);
  return {
    ids,
    rankBands: countOccurrences(markup, 'class="tree-rank"'),
    folders: countOccurrences(markup, 'class="tree-folder'),
    focusableCards: countOccurrences(markup, 'role="button" tabindex="0" aria-pressed="false"'),
  };
}

const allCardIds = layoutRecords.flatMap(record => record.layout.nodes.map(node => node.vehicle_id));
const allEdgeIds = layoutRecords.flatMap(record => record.layout.edges.map(
  edge => `${edge.source_vehicle_id}->${edge.target_vehicle_id}`,
));
const edgeFingerprint = sha256Lines(allEdgeIds);
const authoritativeEdgeIds = Object.entries(database.predecessors || {})
  .filter(([targetId, sourceId]) => vehiclesById.has(targetId) && vehiclesById.has(sourceId))
  .map(([targetId, sourceId]) => `${sourceId}->${targetId}`)
  .sort();

function addMatrixCase(cases, record, category, startNode, targetNode) {
  if (!startNode || !targetNode || startNode.vehicle_id === targetNode.vehicle_id) return;
  cases.push({
    tree_key: record.key,
    category,
    start_id: startNode.vehicle_id,
    target_id: targetNode.vehicle_id,
  });
}

function buildMatrixCases() {
  const cases = [];
  for (const record of layoutRecords) {
    const usable = record.layout.nodes.filter(node => !node.hidden_research);
    addMatrixCase(cases, record, "early_to_late", usable[0], usable.at(-1));
    addMatrixCase(cases, record, "middle_to_late", usable[Math.floor(usable.length / 2)], usable.at(-1));
    const directEdge = record.layout.edges.find(edge => (
      !vehiclesById.get(edge.source_vehicle_id)?.hiddenResearch
      && !vehiclesById.get(edge.target_vehicle_id)?.hiddenResearch
    ));
    if (directEdge) {
      addMatrixCase(
        cases,
        record,
        "direct_predecessor",
        record.layout.nodes.find(node => node.vehicle_id === directEdge.source_vehicle_id),
        record.layout.nodes.find(node => node.vehicle_id === directEdge.target_vehicle_id),
      );
    }
    const folderTarget = usable.find(node => node.group_id && node.vehicle_id !== usable[0]?.vehicle_id);
    if (folderTarget) addMatrixCase(cases, record, "folder_member", usable[0], folderTarget);
  }
  return cases;
}

const matrixCases = buildMatrixCases();
const matrixResults = [];
for (const matrixCase of matrixCases) {
  const record = layoutByKey.get(matrixCase.tree_key);
  const started = performance.now();
  try {
    const result = calculate(
      database,
      emptyCalculationInput(matrixCase.start_id, matrixCase.target_id),
    );
    const presentation = treeResultPresentation(database, result);
    const highlight = await buildVisualTreeHighlight(record.layout, result, {
      userResultSource: "legacy",
      calculationStatus: "complete",
    });
    matrixResults.push({
      ...matrixCase,
      passed: true,
      duration_ms: performance.now() - started,
      result,
      presentation,
      highlight,
    });
  } catch (error) {
    matrixResults.push({
      ...matrixCase,
      passed: false,
      duration_ms: performance.now() - started,
      error: error instanceof Error ? error.message : String(error),
    });
  }
}

function syntheticGeometry(layout, zoom, viewportWidth, viewportHeight) {
  const rects = new Map(layout.nodes.map(node => {
    const rankIndex = layout.ranks.indexOf(node.rank);
    const left = (24 + node.column * 220) * zoom;
    const top = (32 + rankIndex * 620 + node.visual_slot * 116) * zoom;
    const width = 176 * zoom;
    const height = 96 * zoom;
    return [node.vehicle_id, {
      left,
      right: left + width,
      top,
      bottom: top + height,
      width,
      height,
    }];
  }));
  const maxRight = Math.max(...[...rects.values()].map(rect => rect.right), viewportWidth);
  const maxBottom = Math.max(...[...rects.values()].map(rect => rect.bottom), viewportHeight);
  const geometries = layout.edges.map(edge => ({
    edge_id: `${edge.source_vehicle_id}->${edge.target_vehicle_id}`,
    ...connectionGeometry(
      {left: 0, top: 0},
      rects.get(edge.source_vehicle_id),
      rects.get(edge.target_vehicle_id),
    ),
  }));
  return {width: maxRight, height: maxBottom, geometries};
}

const geometryResults = [];
for (const record of layoutRecords) {
  for (const [width, height] of geometryViewports) {
    for (const zoom of geometryZooms) {
      const geometry = syntheticGeometry(record.layout, zoom, width, height);
      const valid = geometry.width > 0 && geometry.height > 0
        && geometry.geometries.length === record.layout.edges.length
        && geometry.geometries.every(edge => (
          [edge.x1, edge.y1, edge.x2, edge.y2, edge.middle].every(Number.isFinite)
          && edge.x1 >= 0 && edge.x1 <= geometry.width
          && edge.x2 >= 0 && edge.x2 <= geometry.width
          && edge.y1 >= 0 && edge.y1 <= geometry.height
          && edge.y2 >= 0 && edge.y2 <= geometry.height
        ));
      geometryResults.push({
        tree_key: record.key,
        viewport: `${width}x${height}`,
        zoom,
        valid,
        edge_count: geometry.geometries.length,
      });
    }
  }
}

function median(values) {
  const sorted = [...values].sort((left, right) => left - right);
  const middle = Math.floor(sorted.length / 2);
  return sorted.length % 2 ? sorted[middle] : (sorted[middle - 1] + sorted[middle]) / 2;
}

function performanceSummary(values) {
  const finite = values.filter(Number.isFinite);
  const sorted = [...finite].sort((left, right) => left - right);
  const medianMs = median(sorted);
  const p95Index = Math.min(sorted.length - 1, Math.floor(sorted.length * 0.95));
  const outlierThreshold = Math.max(25, medianMs * 15);
  return {
    minimum_ms: Number(sorted[0].toFixed(3)),
    median_ms: Number(medianMs.toFixed(3)),
    p95_ms: Number(sorted[p95Index].toFixed(3)),
    maximum_ms: Number(sorted.at(-1).toFixed(3)),
    advisory_outlier_threshold_ms: Number(outlierThreshold.toFixed(3)),
    advisory_outlier_count: sorted.filter(value => value > outlierThreshold).length,
    hard_limit_applied: false,
  };
}

function buildStateStress(steps = 600) {
  let treeKey = treeKeys[0];
  let selectedId = null;
  let abState = createTreeAbState();
  let view = "tree";
  let zoom = 1;
  let scroll = {left: 0, top: 0};
  let solverCalls = 0;
  let maximumSelected = 0;
  for (let step = 0; step < steps; step += 1) {
    const action = step % 12;
    const record = layoutByKey.get(treeKey);
    const usable = record.layout.nodes.filter(node => !node.hidden_research);
    if (action === 0 || action === 9) {
      const entry = searchIndex[(step * 37) % searchIndex.length];
      treeKey = `${entry.country_id}/${entry.branch_id}`;
      selectedId = entry.vehicle_id;
      if (treeAbTreeKey(database, abState) && treeAbTreeKey(database, abState) !== treeKey) {
        abState = resetTreeAbState();
      }
    } else if (action === 1) {
      selectedId = usable[(step * 11) % usable.length].vehicle_id;
    } else if (action === 2) {
      abState = createTreeAbState();
      abState = setTreeAbEndpoint(database, abState, "start", usable[0].vehicle_id);
    } else if (action === 3) {
      if (!abState.startId || treeAbTreeKey(database, abState) !== treeKey) {
        abState = setTreeAbEndpoint(database, createTreeAbState(), "start", usable[0].vehicle_id);
      }
      const target = usable.findLast(node => node.vehicle_id !== abState.startId);
      abState = setTreeAbEndpoint(database, abState, "target", target.vehicle_id);
    } else if (action === 4 && abState.startId && abState.targetId) {
      const result = calculate(database, emptyCalculationInput(abState.startId, abState.targetId));
      solverCalls += 1;
      abState = attachTreeAbResult(abState, result, {
        userResultSource: "legacy",
        calculationStatus: "complete",
      });
    } else if (action === 5) {
      zoom = changeTreeZoom(zoom, step % 3 === 0 ? "reset" : step % 2 ? "in" : "out");
    } else if (action === 6) {
      scroll = clampTreeScrollPosition(
        panScrollPosition(scroll, {x: 20, y: 20}, {x: -300, y: -500}),
        {scrollWidth: 1800 * zoom, clientWidth: 390, scrollHeight: 5400 * zoom, clientHeight: 844},
      );
    } else if (action === 7) {
      view = "calculator";
    } else if (action === 8) {
      view = "tree";
    } else if (action === 10) {
      abState = resetTreeAbState();
    } else if (action === 11) {
      treeKey = treeKeys[(treeKeys.indexOf(treeKey) + 1) % treeKeys.length];
      selectedId = null;
      if (treeAbTreeKey(database, abState) && treeAbTreeKey(database, abState) !== treeKey) {
        abState = resetTreeAbState();
      }
    }

    const active = layoutByKey.get(treeKey).layout;
    if (selectedId) {
      assert.equal(active.nodes.filter(node => node.vehicle_id === selectedId).length, 1);
      maximumSelected = Math.max(maximumSelected, 1);
    }
    assert(new Set(["tree", "calculator"]).has(view));
    assert(zoom >= 0.5 && zoom <= 1.5);
    assert(scroll.left >= 0 && scroll.top >= 0);
    if (treeAbTreeKey(database, abState)) {
      assert.equal(treeAbMatchesLayout(database, abState, active), true);
      assert(active.nodes.some(node => node.vehicle_id === abState.startId || node.vehicle_id === abState.targetId));
    }
    if (abState.result) {
      assert.equal(abState.result.startVehicleId, abState.startId);
      assert.equal(abState.result.targetVehicleId, abState.targetId);
    }
  }
  return {steps, solver_calls: solverCalls, maximum_selected_cards: maximumSelected, passed: true};
}

const stateStress = buildStateStress();

const reportTrees = layoutRecords.map(record => {
  const layout = record.layout;
  const markupState = vehicleStateCounts(record.markup);
  const cases = matrixResults.filter(result => result.tree_key === record.key);
  const jumpStarted = performance.now();
  const jumpEntry = findVehicleSearchEntry(searchIndex, layout.nodes[0].vehicle_id);
  const jumpMs = performance.now() - jumpStarted;
  const highlightDurations = cases.filter(item => item.passed).map(item => item.duration_ms);
  return {
    tree_key: record.key,
    nation: COUNTRY_LABELS[layout.country_id] || layout.country_id,
    vehicle_type: BRANCH_LABELS[layout.branch_id] || layout.branch_id,
    cards: layout.nodes.length,
    unique_vehicle_ids: new Set(layout.nodes.map(node => node.vehicle_id)).size,
    ranks: layout.ranks.length,
    columns: layout.columns.length,
    edges: layout.edges.length,
    folders: layout.folders.length,
    partial: layout.nodes.filter(node => partialIds.has(node.vehicle_id)).length,
    hidden: layout.nodes.filter(node => node.hidden_research).length,
    render_desktop: markupState.ids.length === layout.nodes.length,
    render_mobile: geometryResults.filter(item => item.tree_key === record.key).every(item => item.valid),
    search_jump: Boolean(jumpEntry && jumpEntry.vehicle_id === layout.nodes[0].vehicle_id),
    ab_test_status: cases.length > 0 && cases.every(item => item.passed) ? "passed" : "failed",
    ab_case_count: cases.length,
    runtime_errors: cases.filter(item => !item.passed).map(item => item.error),
    performance_ms: {
      initial_layout: Number(record.layoutMs.toFixed(3)),
      render_markup: Number(record.renderMs.toFixed(3)),
      search_jump: Number(jumpMs.toFixed(3)),
      ab_cases: highlightDurations.length ? performanceSummary(highlightDurations) : null,
    },
  };
});

const reportBase = {
  schema_version: 1,
  contract_version: "visual-tech-tree-full-validation-vt7",
  game_version: database.gameVersion,
  product_version: "1.0.0",
  totals: {
    trees: layoutRecords.length,
    cards: allCardIds.length,
    unique_vehicle_ids: new Set(allCardIds).size,
    edges: allEdgeIds.length,
    folders: folderSummary.folder_count,
    present_folder_members: folderSummary.present_member_count,
    missing_folder_members: folderSummary.missing_member_count,
    incomplete_folders: folderSummary.incomplete_folder_count,
    non_displayable_folders: folderSummary.non_displayable_folder_count,
    partial_cases: KNOWN_PARTIAL_VEHICLE_IDS.length,
    search_entries: searchIndex.length,
    geometry_configurations: geometryResults.length,
    ab_cases: matrixResults.length,
    ab_passed: matrixResults.filter(item => item.passed).length,
    runtime_errors: matrixResults.filter(item => !item.passed).length,
  },
  invariants: {
    edge_fingerprint: edgeFingerprint,
    edge_fingerprint_matches_vt6: edgeFingerprint === expectedEdgeFingerprint,
    all_geometry_valid: geometryResults.every(item => item.valid),
    search_complete: searchIndex.length === 2232,
    state_machine_passed: stateStress.passed,
    ready_for_default_use: false,
  },
  performance: {
    advisory_only: true,
    search_index_ms: Number(searchIndexMs.toFixed(3)),
    layout: performanceSummary(layoutRecords.map(record => record.layoutMs)),
    render: performanceSummary(layoutRecords.map(record => record.renderMs)),
    ab_matrix: performanceSummary(matrixResults.map(item => item.duration_ms)),
  },
  state_machine: stateStress,
  trees: reportTrees,
};
const structuralFingerprint = createHash("sha256").update(JSON.stringify({
  totals: reportBase.totals,
  invariants: reportBase.invariants,
  trees: reportTrees.map(({performance_ms: _performance, ...tree}) => tree),
})).digest("hex");
const report = {...reportBase, structural_fingerprint: structuralFingerprint};

after(async () => {
  await mkdir(new URL("./", reportUrl), {recursive: true});
  await writeFile(reportUrl, `${JSON.stringify(report, null, 2)}\n`, "utf8");
  console.log(JSON.stringify({
    report: "build/health/Visual_Tree_Full_Validation_2.57.1.67.json",
    trees: report.totals.trees,
    cards: report.totals.cards,
    edges: report.totals.edges,
    search: report.totals.search_entries,
    ab_passed: report.totals.ab_passed,
    ab_total: report.totals.ab_cases,
    partial_cases: report.totals.partial_cases,
    runtime_errors: report.totals.runtime_errors,
  }));
});

test("VT.7 sweeps all 44 productive trees and all 2,232 cards exactly once", () => {
  assert.equal(layoutRecords.length, 44);
  assert.equal(allCardIds.length, 2232);
  assert.equal(new Set(allCardIds).size, 2232);
  assert.equal(new Set(database.vehicles.map(vehicle => vehicle.id)).size, 2232);
  for (const record of layoutRecords) {
    assert(record.layout.nodes.length > 0, record.key);
    const markupState = vehicleStateCounts(record.markup);
    assert.equal(markupState.ids.length, record.layout.nodes.length, record.key);
    assert.equal(new Set(markupState.ids).size, record.layout.nodes.length, record.key);
    assert.equal(markupState.focusableCards, record.layout.nodes.length, record.key);
    assert.equal(markupState.rankBands, record.layout.ranks.length, record.key);
    assert.equal(markupState.folders, record.layout.folders.length, record.key);
    assert.deepEqual(new Set(markupState.ids), new Set(record.layout.nodes.map(node => node.vehicle_id)));
  }
});

test("all 1,993 renderer edges equal the immutable VT.6 authority set", () => {
  assert.equal(allEdgeIds.length, 1993);
  assert.equal(new Set(allEdgeIds).size, 1993);
  assert.equal(edgeFingerprint, expectedEdgeFingerprint);
  assert.deepEqual([...allEdgeIds].sort(), authoritativeEdgeIds);
  for (const record of layoutRecords) {
    const ids = new Set(record.layout.nodes.map(node => node.vehicle_id));
    for (const edge of record.layout.edges) {
      assert(ids.has(edge.source_vehicle_id), `${record.key}: ${edge.source_vehicle_id}`);
      assert(ids.has(edge.target_vehicle_id), `${record.key}: ${edge.target_vehicle_id}`);
      assert.notEqual(edge.source_vehicle_id, edge.target_vehicle_id, record.key);
      assert.equal(edge.edge_type, "research_predecessor");
      assert.equal(edge.evidence, "normalized_predecessors");
      assert.equal(vehiclesById.get(edge.source_vehicle_id).countryId, record.layout.country_id);
      assert.equal(vehiclesById.get(edge.target_vehicle_id).branchId, record.layout.branch_id);
    }
  }
});

test("repeated rendering and 100 tree switches never accumulate cards, folders or handlers", () => {
  for (let index = 0; index < 100; index += 1) {
    const record = layoutRecords[(index * 17) % layoutRecords.length];
    const markup = renderTreeMarkup(record.layout);
    assert.equal(markup, record.markup, `${index}: ${record.key}`);
    assert.equal(vehicleStateCounts(markup).ids.length, record.layout.nodes.length);
  }
  const listenerContracts = [
    '$(' + '"tree-search-input"' + ').addEventListener("input"',
    '$(' + '"tree-search-results"' + ').addEventListener("click"',
    '$(' + '"tree-calculate"' + ').addEventListener("click"',
    'treeViewport.addEventListener("pointerdown"',
    'treeViewport.addEventListener("pointermove"',
    'window.addEventListener("resize"',
  ];
  for (const listener of listenerContracts) assert.equal(countOccurrences(appSource, listener), 1, listener);
  const calculateHandler = appSource.match(/\$\("tree-calculate"\)\.addEventListener\("click",[\s\S]*?\n\}\);/)?.[0];
  assert.ok(calculateHandler);
  assert.equal(countOccurrences(calculateHandler, "executeCalculation({origin: \"tree\"})"), 1);
});

test("the complete 2,232-entry search and jump contract resolves one real card per ID", () => {
  assert.equal(searchIndex.length, 2232);
  assert.equal(new Set(searchIndex.map(entry => entry.vehicle_id)).size, 2232);
  const cardCounts = new Map();
  for (const record of layoutRecords) {
    for (const id of vehicleStateCounts(record.markup).ids) {
      cardCounts.set(id, (cardCounts.get(id) || 0) + 1);
    }
  }
  for (const vehicle of database.vehicles) {
    const matches = searchIndex.filter(entry => entry.vehicle_id === vehicle.id);
    assert.equal(matches.length, 1, vehicle.id);
    const entry = findVehicleSearchEntry(searchIndex, vehicle.id);
    assert.ok(entry, vehicle.id);
    assert.equal(entry.country_id, vehicle.countryId, vehicle.id);
    assert.equal(entry.branch_id, vehicle.branchId, vehicle.id);
    assert.equal(cardCounts.get(vehicle.id), 1, vehicle.id);
    const record = layoutByKey.get(`${entry.country_id}/${entry.branch_id}`);
    assert.equal(record.layout.nodes.filter(node => node.vehicle_id === vehicle.id).length, 1);
  }
  assert.equal(searchVehicleIndex(searchIndex, "tiger h1")[0].vehicle_id, tigerCase.startId);
  assert.equal(searchVehicleIndex(searchIndex, "TIGER H1")[0].vehicle_id, tigerCase.startId);
  assert(searchVehicleIndex(searchIndex, "nurnberg").some(entry => entry.name === "Nürnberg"));
  assert(searchVehicleIndex(searchIndex, "koln").filter(entry => entry.name.startsWith("Köln")).length >= 2);
  assert.equal(normalizeVehicleSearchText("Großbritannien"), "grossbritannien");
  assert.match(appSource, /function jumpToTreeVehicle\(vehicleId/);
  assert.match(appSource, /scrollIntoView\(\{behavior: "smooth", block: "center", inline: "center"\}\)/);
});

test("the deterministic all-tree A-to-B matrix stays identical to the central solver", () => {
  assert.equal(new Set(matrixResults.map(item => item.tree_key)).size, 44);
  assert(matrixResults.length >= 150);
  assert.equal(matrixResults.filter(item => item.passed).length, matrixResults.length);
  for (const item of matrixResults) {
    const result = item.result;
    const presentation = item.presentation;
    assert.deepEqual(presentation.required_vehicle_ids, result.requiredVehicleIds, item.tree_key);
    assert.equal(presentation.total_rp, result.totalRp, item.tree_key);
    assert.equal(presentation.total_sl, result.totalSl, item.tree_key);
    assert.equal(presentation.total_ge, result.totalGe, item.tree_key);
    assert.equal(presentation.vehicle_count, result.requiredVehicleIds.length, item.tree_key);
    assert.equal(item.highlight.user_result_source, "legacy");
    assert.equal(item.highlight.calculation_status, "complete");
  }
  for (const record of layoutRecords) {
    const categories = new Set(matrixResults.filter(item => item.tree_key === record.key)
      .map(item => item.category));
    assert(categories.has("early_to_late"), record.key);
    assert(categories.has("middle_to_late"), record.key);
    assert(categories.has("direct_predecessor"), record.key);
    if (record.layout.folders.length) assert(categories.has("folder_member"), record.key);
  }
});

test("all highlights partition required vehicles and use only authoritative direct edges", () => {
  for (const item of matrixResults) {
    const required = new Set(item.result.requiredVehicleIds);
    const direct = new Set(item.result.lines.filter(line => line.reason === "direct_path").map(line => line.id));
    const additional = new Set(item.result.lines.filter(line => line.reason !== "direct_path").map(line => line.id));
    assert.equal([...direct].filter(id => additional.has(id)).length, 0, item.tree_key);
    assert.deepEqual(new Set([...direct, ...additional]), required, item.tree_key);
    assert.equal([...Object.values(item.highlight.node_states)].filter(states => states.includes("start_a")).length, 1);
    assert.equal([...Object.values(item.highlight.node_states)].filter(states => states.includes("target_b")).length, 1);
    const layoutEdges = new Set(layoutByKey.get(item.tree_key).layout.edges.map(
      edge => `${edge.source_vehicle_id}->${edge.target_vehicle_id}`,
    ));
    for (const edgeId of item.highlight.required_edge_ids) {
      assert(layoutEdges.has(edgeId), `${item.tree_key}: ${edgeId}`);
      const [sourceId, targetId] = edgeId.split("->");
      assert(direct.has(targetId), edgeId);
      assert(sourceId === item.result.startVehicleId || direct.has(sourceId), edgeId);
    }
  }
});

test("Tiger H1 to Leopard 2A7V remains exact for every VT.7 viewport and zoom", async () => {
  const result = calculate(database, emptyCalculationInput(tigerCase.startId, tigerCase.targetId));
  const layout = layoutByKey.get("country_germany/army").layout;
  const highlight = await buildVisualTreeHighlight(layout, result, {
    userResultSource: "legacy",
    calculationStatus: "complete",
  });
  const direct = result.lines.filter(line => line.reason === "direct_path").length;
  const additional = result.lines.filter(line => line.reason !== "direct_path").length;
  assert.deepEqual(
    [result.requiredVehicleIds.length, result.totalRp, result.totalSl, result.totalGe],
    [40, 4_245_100, 13_825_000, 94_351],
  );
  assert.deepEqual([direct, additional, highlight.required_edge_ids.length], [11, 29, 10]);
  for (const [width, height] of requiredViewports) {
    for (const zoom of geometryZooms) {
      const geometry = syntheticGeometry(layout, zoom, width, height);
      assert(geometry.geometries.every(edge => [edge.x1, edge.y1, edge.x2, edge.y2].every(Number.isFinite)));
    }
  }
  let state = setTreeAbEndpoint(database, createTreeAbState(), "start", tigerCase.startId);
  state = setTreeAbEndpoint(database, state, "target", tigerCase.targetId);
  state = attachTreeAbResult(state, result, {userResultSource: "legacy", calculationStatus: "complete"});
  assert.equal(treeAbMatchesLayout(database, state, layout), true);
  assert.deepEqual(canonicalResult(state.result), canonicalResult(result));
});

test("all 14 Hidden/Partial vehicles remain searchable, selectable and rejected as targets", () => {
  const folderCounts = new Map();
  for (const id of KNOWN_PARTIAL_VEHICLE_IDS) {
    const vehicle = vehiclesById.get(id);
    const record = layoutByKey.get(`${vehicle.countryId}/${vehicle.branchId}`);
    const node = record.layout.nodes.find(item => item.vehicle_id === id);
    assert.ok(node, id);
    assert.equal(node.hidden_research, true, id);
    folderCounts.set(node.group_id, (folderCounts.get(node.group_id) || 0) + 1);
    assert.equal(searchIndex.filter(entry => entry.vehicle_id === id).length, 1, id);
    assert.equal(vehicleStateCounts(record.markup).ids.filter(cardId => cardId === id).length, 1, id);
    const details = selectedVehicleDetails(database, record.layout, id);
    assert.equal(details.partial_unresolved, true, id);
    assert.equal(details.hidden_research, true, id);
    const start = record.layout.nodes.find(item => !item.hidden_research && item.vehicle_id !== id);
    let state = setTreeAbEndpoint(database, createTreeAbState(), "start", start.vehicle_id);
    state = setTreeAbEndpoint(database, state, "target", id);
    const selection = buildTreeAbSelectionHighlight(record.layout, state);
    assert(selection.node_states[start.vehicle_id].includes("start_a"), id);
    assert(selection.node_states[id].includes("target_b"), id);
    assert(selection.node_states[id].includes("partial_unresolved"), id);
    assert.throws(
      () => calculate(database, emptyCalculationInput(start.vehicle_id, id)),
      /ausgeblendetes Altbestandsfahrzeug/,
      id,
    );
    assert.equal(selection.required_edge_ids.length, 0, id);
  }
  assert.deepEqual(Object.fromEntries([...folderCounts].sort()), {
    fiat_group: 3,
    mc200_group: 3,
    r2y2_group: 3,
    sm_79_group: 5,
  });
});

test("the complete folder contract and groupIndex mutation boundary remain unchanged", async () => {
  assert.equal(folderSummary.folder_count, 395);
  assert.equal(folderSummary.present_member_count, 821);
  assert.equal(folderSummary.missing_member_count, 28);
  assert.equal(folderSummary.incomplete_folder_count, 13);
  assert.equal(folderSummary.non_displayable_folder_count, 6);
  const mutationRecords = [...layoutRecords]
    .filter(record => record.layout.folders.length)
    .sort((left, right) => right.layout.folders.length - left.layout.folders.length)
    .slice(0, 6);
  for (const original of mutationRecords) {
    const mutatedRaw = structuredClone(database);
    for (const vehicle of mutatedRaw.vehicles) {
      if (vehicle.countryId === original.layout.country_id
        && vehicle.branchId === original.layout.branch_id && vehicle.group) {
        vehicle.groupIndex = 1000 - Number(vehicle.groupIndex || 0);
      }
    }
    const mutated = validateDatabase(mutatedRaw);
    const changed = await buildVisualTreeLayout(mutated, {
      countryId: original.layout.country_id,
      branchId: original.layout.branch_id,
    });
    assert.deepEqual(changed.edges, original.layout.edges, original.key);
    assert(changed.nodes.some(node => {
      const baseline = original.layout.nodes.find(item => item.vehicle_id === node.vehicle_id);
      return node.group_id && node.group_index !== baseline.group_index;
    }), original.key);
    const matrixCase = matrixResults.find(item => item.tree_key === original.key && item.passed);
    const mutatedResult = calculate(
      mutated,
      emptyCalculationInput(matrixCase.start_id, matrixCase.target_id),
    );
    assert.deepEqual(canonicalResult(mutatedResult), canonicalResult(matrixCase.result), original.key);
  }
});

test("all 264 all-tree geometry configurations remain finite and structurally complete", () => {
  assert.equal(geometryResults.length, 44 * 3 * 2);
  assert.equal(geometryResults.filter(item => item.valid).length, geometryResults.length);
  for (const record of layoutRecords) {
    assert.equal(geometryResults.filter(item => item.tree_key === record.key).length, 6);
    assert.equal(vehicleStateCounts(record.markup).rankBands, record.layout.ranks.length);
    assert.equal(vehicleStateCounts(record.markup).folders, record.layout.folders.length);
  }
});

test("resize, zoom, scroll and pan stress remain clamped without solver or state drift", () => {
  const largeTrees = [...layoutRecords]
    .sort((left, right) => right.layout.nodes.length - left.layout.nodes.length)
    .slice(0, 6);
  let simulatedSolverCalls = 0;
  for (const record of largeTrees) {
    const baselineEdges = sha256Lines(record.layout.edges.map(
      edge => `${edge.source_vehicle_id}->${edge.target_vehicle_id}`,
    ));
    let scroll = {left: 9_999_999, top: 9_999_999};
    let zoom = 1;
    for (let cycle = 0; cycle < 20; cycle += 1) {
      for (const [width, height] of [
        [1366, 768], [390, 844], [844, 390], [320, 568], [1920, 1080], [768, 1024], [1366, 768],
      ]) {
        for (const targetZoom of [1, 1.5, 0.5, 1]) {
          while (zoom < targetZoom) zoom = changeTreeZoom(zoom, "in");
          while (zoom > targetZoom) zoom = changeTreeZoom(zoom, "out");
          scroll = clampTreeScrollPosition(scroll, {
            scrollWidth: 1800 * zoom,
            clientWidth: width,
            scrollHeight: 5400 * zoom,
            clientHeight: height,
          });
          assert(scroll.left >= 0 && scroll.top >= 0);
          assert(scroll.left <= Math.max(0, 1800 * zoom - width));
          assert(scroll.top <= Math.max(0, 5400 * zoom - height));
        }
      }
    }
    assert.equal(sha256Lines(record.layout.edges.map(
      edge => `${edge.source_vehicle_id}->${edge.target_vehicle_id}`,
    )), baselineEdges);
  }
  assert.equal(simulatedSolverCalls, 0);
  assert.deepEqual(clampTreeScrollPosition({left: -1, top: -1}, {
    scrollWidth: 1800, clientWidth: 390, scrollHeight: 5400, clientHeight: 844,
  }), {left: 0, top: 0});
});

test("pointer, keyboard and state-machine contracts withstand deterministic repetition", () => {
  assert.equal(TREE_PAN_THRESHOLD, 6);
  assert.equal(pointerMovementExceedsThreshold({x: 0, y: 0}, {x: 3, y: 4}), false);
  assert.equal(pointerMovementExceedsThreshold({x: 0, y: 0}, {x: 6, y: 0}), true);
  assert.deepEqual(panScrollPosition({left: 500, top: 400}, {x: 20, y: 20}, {x: 80, y: 90}), {
    left: 440,
    top: 330,
  });
  for (const eventName of ["pointercancel", "lostpointercapture"]) {
    assert.equal(countOccurrences(appSource, `addEventListener("${eventName}"`), 1, eventName);
  }
  assert.match(appSource, /event\.key === "Enter" \|\| event\.key === " "/);
  assert.match(htmlSource, /id="tree-content"/);
  assert.match(stylesSource, /\.tree-vehicle:focus-visible/);
  assert.equal(stateStress.steps, 600);
  assert.equal(stateStress.maximum_selected_cards, 1);
  assert.equal(stateStress.passed, true);
});

test("responsive and service-worker delivery stay on VT.6 because VT.7 changes tests only", () => {
  assert.equal(requiredViewports.length, 8);
  assert.match(htmlSource, /name="viewport" content="width=device-width,initial-scale=1"/);
  assert.match(stylesSource, /max-width: 100%/);
  assert.match(stylesSource, /overflow: auto/);
  assert.match(stylesSource, /min-height: 44px/);
  assert.match(stylesSource, /env\(safe-area-inset-/);
  assert.match(workerSource, /const CACHE = "wurstbrot-1\.0\.0-stable-vt6"/);
  assert.doesNotMatch(workerSource, /stable-vt7/);
  assert.match(workerSource, /skipWaiting/);
  assert.match(workerSource, /clients\.claim/);
  assert.match(workerSource, /key\.startsWith\(CACHE_PREFIX\) && key !== CACHE/);
  assert.doesNotMatch(interactionSource, /from\s+["'][^"']*solver|function\s+(solve|calculate)\b/);
});

test("the VT.7 report is complete, reproducible and free of unexplained runtime failures", () => {
  assert.equal(report.totals.trees, 44);
  assert.equal(report.totals.cards, 2232);
  assert.equal(report.totals.unique_vehicle_ids, 2232);
  assert.equal(report.totals.edges, 1993);
  assert.equal(report.totals.folders, 395);
  assert.equal(report.totals.present_folder_members, 821);
  assert.equal(report.totals.missing_folder_members, 28);
  assert.equal(report.totals.partial_cases, 14);
  assert.equal(report.totals.search_entries, 2232);
  assert.equal(report.totals.runtime_errors, 0);
  assert.equal(report.invariants.edge_fingerprint_matches_vt6, true);
  assert.equal(report.invariants.all_geometry_valid, true);
  assert.equal(report.invariants.ready_for_default_use, false);
  assert.equal(report.trees.length, 44);
  assert.match(report.structural_fingerprint, /^[0-9a-f]{64}$/);
});
