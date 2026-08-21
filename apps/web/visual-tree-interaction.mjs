import {
  BRANCH_LABELS,
  COUNTRY_LABELS,
  KNOWN_PARTIAL_VEHICLE_IDS,
} from "./visual-tree.mjs";

export const TREE_ZOOM_MIN = 0.5;
export const TREE_ZOOM_MAX = 1.5;
export const TREE_ZOOM_STEP = 0.1;

const partialVehicleIds = new Set(KNOWN_PARTIAL_VEHICLE_IDS);
const collator = new Intl.Collator("de", {numeric: true, sensitivity: "base"});

function compareSearchEntries(left, right) {
  return collator.compare(left.name, right.name)
    || collator.compare(left.country_label, right.country_label)
    || collator.compare(left.branch_label, right.branch_label)
    || left.rank - right.rank
    || collator.compare(left.vehicle_id, right.vehicle_id);
}

export function normalizeVehicleSearchText(value) {
  return String(value ?? "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replaceAll("ß", "ss")
    .toLocaleLowerCase("de-DE")
    .replace(/[^\p{L}\p{N}]+/gu, " ")
    .trim()
    .replace(/\s+/g, " ");
}

export function buildVehicleSearchIndex(database) {
  const nameCounts = new Map();
  for (const vehicle of database?.vehicles || []) {
    const key = normalizeVehicleSearchText(vehicle.name || vehicle.id);
    nameCounts.set(key, (nameCounts.get(key) || 0) + 1);
  }
  return (database?.vehicles || []).map(vehicle => {
    const name = vehicle.name || vehicle.id;
    const countryLabel = COUNTRY_LABELS[vehicle.countryId] || vehicle.countryId;
    const branchLabel = BRANCH_LABELS[vehicle.branchId] || vehicle.branchId;
    const normalizedName = normalizeVehicleSearchText(name);
    return Object.freeze({
      vehicle_id: vehicle.id,
      name,
      country_id: vehicle.countryId,
      country_label: countryLabel,
      branch_id: vehicle.branchId,
      branch_label: branchLabel,
      rank: Number(vehicle.rank),
      duplicate_name: (nameCounts.get(normalizedName) || 0) > 1,
      normalized_name: normalizedName,
      search_text: normalizeVehicleSearchText(
        `${name} ${vehicle.id} ${countryLabel} ${branchLabel} Rang ${vehicle.rank}`,
      ),
    });
  }).sort(compareSearchEntries);
}

export function searchVehicleIndex(index, query, {limit = 40} = {}) {
  const normalized = normalizeVehicleSearchText(query);
  if (!normalized) return [];
  const terms = normalized.split(" ");
  return index
    .filter(entry => terms.every(term => entry.search_text.includes(term)))
    .sort((left, right) => {
      const leftStarts = left.normalized_name.startsWith(normalized) ? 0 : 1;
      const rightStarts = right.normalized_name.startsWith(normalized) ? 0 : 1;
      return leftStarts - rightStarts || compareSearchEntries(left, right);
    })
    .slice(0, limit);
}

export function findVehicleSearchEntry(index, vehicleId) {
  return index.find(entry => entry.vehicle_id === vehicleId) || null;
}

export function changeTreeZoom(current, action) {
  const value = action === "reset" ? 1
    : Number(current) + (action === "in" ? TREE_ZOOM_STEP : -TREE_ZOOM_STEP);
  return Math.min(TREE_ZOOM_MAX, Math.max(TREE_ZOOM_MIN, Math.round(value * 10) / 10));
}

export function panScrollPosition(scroll, pointerStart, pointerCurrent) {
  return {
    left: Math.max(0, scroll.left - (pointerCurrent.x - pointerStart.x)),
    top: Math.max(0, scroll.top - (pointerCurrent.y - pointerStart.y)),
  };
}

export function connectionGeometry(origin, from, to) {
  const x1 = from.left + from.width / 2 - origin.left;
  const y1 = from.bottom - origin.top;
  const x2 = to.left + to.width / 2 - origin.left;
  const y2 = to.top - origin.top;
  const middle = (y1 + y2) / 2;
  return {x1, y1, x2, y2, middle};
}

export function selectedDirectEdgeIds(layout, vehicleId) {
  if (!layout || !vehicleId) return [];
  return layout.edges
    .filter(edge => edge.source_vehicle_id === vehicleId || edge.target_vehicle_id === vehicleId)
    .map(edge => `${edge.source_vehicle_id}->${edge.target_vehicle_id}`)
    .sort();
}

export function selectedVehicleDetails(database, layout, vehicleId) {
  const vehicle = (database?.vehicles || []).find(item => item.id === vehicleId);
  const node = layout?.nodes?.find(item => item.vehicle_id === vehicleId);
  if (!vehicle || !node) return null;
  const folder = vehicle.group
    ? layout?.folders?.find(item => item.group_id === vehicle.group) || null
    : null;
  return Object.freeze({
    vehicle_id: vehicle.id,
    name: vehicle.name || vehicle.id,
    country: COUNTRY_LABELS[vehicle.countryId] || vehicle.countryId,
    branch: BRANCH_LABELS[vehicle.branchId] || vehicle.branchId,
    rank: Number(vehicle.rank),
    rp: Number(vehicle.rp || 0),
    sl: Number(vehicle.sl || 0),
    group_id: vehicle.group || null,
    group_index: vehicle.group ? Number(vehicle.groupIndex || 0) : null,
    folder_visible_member_count: folder?.visible_member_count || 0,
    folder_declared_member_count: folder?.declared_member_count || 0,
    folder_missing_member_count: folder?.missing_member_count || 0,
    folder_data_incomplete: Boolean(folder && !folder.complete_in_normalized_data),
    hidden_research: Boolean(vehicle.hiddenResearch),
    partial_unresolved: partialVehicleIds.has(vehicle.id),
  });
}

export function createTreeAbState(initial = {}) {
  return Object.freeze({
    startId: initial.startId || null,
    targetId: initial.targetId || null,
    result: initial.result || null,
    userResultSource: initial.userResultSource || "legacy",
    calculationStatus: initial.calculationStatus || null,
    fallbackReason: initial.fallbackReason || null,
  });
}

function databaseVehicle(database, vehicleId) {
  if (!vehicleId) return null;
  return (database?.vehicles || []).find(vehicle => vehicle.id === vehicleId) || null;
}

function assertCompatibleVehicles(start, target) {
  if (start && target
    && (start.countryId !== target.countryId || start.branchId !== target.branchId)) {
    throw new Error("Start A und Ziel B müssen im selben Forschungsbaum liegen.");
  }
}

export function setTreeAbEndpoint(database, state, role, vehicleId) {
  if (role !== "start" && role !== "target") throw new Error("Unbekannte A/B-Rolle.");
  const current = createTreeAbState(state);
  const vehicle = databaseVehicle(database, vehicleId);
  if (vehicleId && !vehicle) throw new Error(`Unbekanntes Fahrzeug: ${vehicleId}`);
  const startId = role === "start" ? vehicle?.id || null : current.startId;
  const targetId = role === "target" ? vehicle?.id || null : current.targetId;
  const start = databaseVehicle(database, startId);
  const target = databaseVehicle(database, targetId);
  assertCompatibleVehicles(start, target);
  return createTreeAbState({
    ...current,
    startId,
    targetId,
    result: null,
    calculationStatus: null,
    fallbackReason: null,
  });
}

export function attachTreeAbResult(state, result, options = {}) {
  const current = createTreeAbState(state);
  if (!result || result.startVehicleId !== current.startId
    || result.targetVehicleId !== current.targetId) {
    throw new Error("Das Solver-Ergebnis passt nicht zur aktuellen A/B-Auswahl.");
  }
  return createTreeAbState({
    ...current,
    result,
    userResultSource: options.userResultSource || "legacy",
    calculationStatus: options.calculationStatus || "complete",
    fallbackReason: options.fallbackReason || null,
  });
}

export function resetTreeAbState() {
  return createTreeAbState();
}

export function treeAbTreeKey(database, state) {
  const current = createTreeAbState(state);
  const start = databaseVehicle(database, current.startId);
  const target = databaseVehicle(database, current.targetId);
  assertCompatibleVehicles(start, target);
  const vehicle = target || start;
  return vehicle ? `${vehicle.countryId}/${vehicle.branchId}` : null;
}

export function treeAbMatchesLayout(database, state, layout) {
  if (!layout) return false;
  const key = treeAbTreeKey(database, state);
  return key === `${layout.country_id}/${layout.branch_id}`;
}

export function buildTreeAbSelectionHighlight(layout, state) {
  if (!layout) return null;
  const current = createTreeAbState(state);
  const nodeIds = new Set(layout.nodes.map(node => node.vehicle_id));
  const startId = nodeIds.has(current.startId) ? current.startId : null;
  const targetId = nodeIds.has(current.targetId) ? current.targetId : null;
  if (!startId && !targetId) return null;
  const nodeStates = {};
  for (const node of layout.nodes) {
    const states = [];
    if (node.vehicle_id === startId) states.push("start_a");
    if (node.vehicle_id === targetId) states.push("target_b");
    states.push("not_required");
    if (node.group_id) states.push("folder_member");
    if (node.hidden_research) states.push("hidden_research");
    if (partialVehicleIds.has(node.vehicle_id)) states.push("partial_unresolved");
    nodeStates[node.vehicle_id] = states;
  }
  return Object.freeze({
    contract_version: "visual-tree-ab-selection-v1",
    start_vehicle_id: startId,
    target_vehicle_id: targetId,
    node_states: nodeStates,
    required_edge_ids: [],
    user_result_source: null,
    calculation_status: null,
    fallback_reason: null,
    complete: false,
  });
}

export function treeResultPresentation(database, result) {
  if (!result) return null;
  const start = databaseVehicle(database, result.startVehicleId);
  const target = databaseVehicle(database, result.targetVehicleId);
  if (!target) throw new Error("Das Solver-Ziel ist in der Datenbank nicht vorhanden.");
  assertCompatibleVehicles(start, target);
  const requiredVehicleIds = [...result.requiredVehicleIds];
  const directVehicleIds = result.lines
    .filter(line => line.reason === "direct_path")
    .map(line => line.id);
  const additionalVehicleIds = result.lines
    .filter(line => line.reason !== "direct_path")
    .map(line => line.id);
  const partialVehicleIdsInResult = [...new Set([
    result.startVehicleId,
    result.targetVehicleId,
    ...requiredVehicleIds,
  ].filter(vehicleId => partialVehicleIds.has(vehicleId)))].sort();
  return Object.freeze({
    start_name: start?.name || start?.id || "Forschungsbaum",
    target_name: target.name || target.id,
    vehicle_count: requiredVehicleIds.length,
    total_rp: result.totalRp,
    total_sl: result.totalSl,
    total_ge: result.totalGe,
    required_vehicle_ids: Object.freeze(requiredVehicleIds),
    direct_vehicle_ids: Object.freeze(directVehicleIds),
    additional_vehicle_ids: Object.freeze(additionalVehicleIds),
    partial_vehicle_ids: Object.freeze(partialVehicleIdsInResult),
    calculation_status: partialVehicleIdsInResult.length ? "partial" : "complete",
  });
}
