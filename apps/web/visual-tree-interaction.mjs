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
  return Object.freeze({
    vehicle_id: vehicle.id,
    name: vehicle.name || vehicle.id,
    country: COUNTRY_LABELS[vehicle.countryId] || vehicle.countryId,
    branch: BRANCH_LABELS[vehicle.branchId] || vehicle.branchId,
    rank: Number(vehicle.rank),
    rp: Number(vehicle.rp || 0),
    sl: Number(vehicle.sl || 0),
    group_id: vehicle.group || null,
    partial_unresolved: partialVehicleIds.has(vehicle.id),
  });
}
