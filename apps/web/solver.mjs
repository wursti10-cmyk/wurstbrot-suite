const validatedDatabases = new WeakSet();

export function validateDatabase(raw) {
  if (raw && typeof raw === "object" && validatedDatabases.has(raw)) return raw;
  if (!raw || raw.schemaVersion !== 1) throw new Error("Nicht unterstützte Datenbank.");
  if (!Array.isArray(raw.vehicles) || !raw.vehicles.length) {
    throw new Error("Keine Fahrzeuge gefunden.");
  }
  const ids = new Set();
  for (const vehicle of raw.vehicles) {
    if (!vehicle.id || ids.has(vehicle.id)) {
      throw new Error(`Ungültige Fahrzeug-ID: ${vehicle.id || "leer"}`);
    }
    ids.add(vehicle.id);
  }
  for (const [id, predecessor] of Object.entries(raw.predecessors || {})) {
    if (ids.has(id) && predecessor && !ids.has(predecessor)) {
      throw new Error(`Unbekannter Vorgänger: ${predecessor}`);
    }
  }
  const rpPerGe = Number(raw.economy?.rpPerGE ?? 45);
  if (!Number.isInteger(rpPerGe) || rpPerGe <= 0) {
    throw new Error("rpPerGE muss eine positive Ganzzahl sein.");
  }
  for (const vehicle of raw.vehicles) {
    const seen = new Set();
    let current = vehicle.id;
    while (current) {
      if (seen.has(current)) throw new Error(`Zyklus im Forschungsweg bei ${current}`);
      if (!ids.has(current)) throw new Error(`Unbekanntes Fahrzeug: ${current}`);
      seen.add(current);
      current = (raw.predecessors || {})[current] || null;
    }
  }
  validatedDatabases.add(raw);
  return raw;
}

export function vehicleIndex(database) {
  return new Map(database.vehicles.map(vehicle => [vehicle.id, vehicle]));
}

export function closure(database, targetId) {
  const index = vehicleIndex(database);
  if (!index.has(targetId)) throw new Error(`Unbekanntes Fahrzeug: ${targetId}`);
  const result = [];
  const seen = new Set();
  let current = targetId;
  while (current) {
    if (seen.has(current)) throw new Error(`Zyklus im Forschungsweg bei ${current}`);
    if (!index.has(current)) throw new Error(`Unbekanntes Fahrzeug: ${current}`);
    seen.add(current);
    result.push(current);
    current = (database.predecessors || {})[current] || null;
  }
  return result.reverse();
}

function halfEvenDivide(numerator, denominator) {
  const quotient = Math.floor(numerator / denominator);
  const remainder = numerator % denominator;
  if (remainder * 2 < denominator) return quotient;
  if (remainder * 2 > denominator) return quotient + 1;
  return quotient % 2 === 0 ? quotient : quotient + 1;
}

function applyDiscount(value, percent) {
  if (!Number.isInteger(percent) || percent < 0 || percent > 100) {
    throw new Error("Rabatt muss zwischen 0 und 100 liegen.");
  }
  return halfEvenDivide(value * (100 - percent), 100);
}

function compareTuples(left, right) {
  for (let i = 0; i < Math.max(left.length, right.length); i += 1) {
    if (left[i] < right[i]) return -1;
    if (left[i] > right[i]) return 1;
  }
  return 0;
}

class MinHeap {
  constructor(compare) { this.items = []; this.compare = compare; }
  get size() { return this.items.length; }
  push(value) {
    this.items.push(value);
    for (let index = this.items.length - 1; index > 0;) {
      const parent = Math.floor((index - 1) / 2);
      if (this.compare(this.items[parent], this.items[index]) <= 0) break;
      [this.items[parent], this.items[index]] = [this.items[index], this.items[parent]];
      index = parent;
    }
  }
  pop() {
    const first = this.items[0];
    const last = this.items.pop();
    if (this.items.length && last) {
      this.items[0] = last;
      for (let index = 0;;) {
        const left = index * 2 + 1;
        const right = left + 1;
        let smallest = index;
        if (left < this.items.length && this.compare(this.items[left], this.items[smallest]) < 0) smallest = left;
        if (right < this.items.length && this.compare(this.items[right], this.items[smallest]) < 0) smallest = right;
        if (smallest === index) break;
        [this.items[index], this.items[smallest]] = [this.items[smallest], this.items[index]];
        index = smallest;
      }
    }
    return first;
  }
}

function stateFor(progress, id) {
  return progress.vehicles?.[id] || {};
}

function isOwned(state) {
  return Boolean(state.researched && state.purchased);
}

function sortKey(vehicle) {
  return [Number(vehicle.rank), Number(vehicle.column || 0), Number(vehicle.order || 0), vehicle.id];
}

function treeVehicles(database, countryId, branchId) {
  return database.vehicles
    .filter(vehicle => vehicle.countryId === countryId && vehicle.branchId === branchId)
    .sort((a, b) => compareTuples(sortKey(a), sortKey(b)));
}

function countRank(ids, rank, index) {
  let total = 0;
  for (const id of ids) if (index.get(id)?.rank === rank) total += 1;
  return total;
}

function candidateCost(ids, base, index, progress, options, rpPerGe) {
  const newIds = [...ids].filter(id => !base.has(id));
  let rp = 0; let ge = 0; let sl = 0;
  for (const id of newIds) {
    const vehicle = index.get(id);
    const state = stateFor(progress, id);
    if (isOwned(state) || vehicle.reserve) continue;
    const researched = Math.min(Math.max(Number(state.researchedRp || 0), 0), vehicle.rp);
    const remaining = Math.max(vehicle.rp - researched, 0);
    rp += remaining;
    ge += remaining ? Math.ceil(remaining / rpPerGe) : 0;
    sl += applyDiscount(Number(vehicle.sl || 0), options.slDiscountPercent);
  }
  const primary = options.optimizeFor === "sl" ? sl
    : options.optimizeFor === "vehicles" ? newIds.length
      : options.optimizeFor === "rp" ? rp : ge;
  return [primary, ge, sl, newIds.sort().join("\u0000")];
}

function minimumRankAdditions(database, base, countryId, branchId, rank, requiredCount,
  progress, options, allowReqUnlock, index, rpPerGe) {
  const candidates = treeVehicles(database, countryId, branchId).filter(vehicle =>
    vehicle.rank === rank && !base.has(vehicle.id)
    && (options.includeHiddenLegacy || !vehicle.hiddenResearch)
    && (allowReqUnlock || !vehicle.reqUnlock));
  if (!candidates.length) return new Set();

  let sequence = 0;
  const heap = new MinHeap((a, b) => compareTuples(a.cost, b.cost) || a.sequence - b.sequence);
  heap.push({cost: candidateCost(new Set(), base, index, progress, options, rpPerGe), sequence: sequence += 1, ids: new Set()});
  const visited = new Set();
  let processed = 0;
  while (heap.size) {
    const state = heap.pop();
    const signature = [...state.ids].sort().join("\u0000");
    if (visited.has(signature)) continue;
    visited.add(signature);
    processed += 1;
    if (processed > 75000) throw new Error("Rangoptimierung hat das Sicherheitslimit erreicht.");
    const combined = new Set([...base, ...state.ids]);
    if (countRank(combined, rank, index) >= requiredCount) return state.ids;

    for (const candidate of candidates) {
      if (combined.has(candidate.id)) continue;
      const addition = closure(database, candidate.id).filter(id =>
        !base.has(id) && (options.includeHiddenLegacy || !index.get(id).hiddenResearch));
      const nextIds = new Set([...state.ids, ...addition]);
      const nextSignature = [...nextIds].sort().join("\u0000");
      if (visited.has(nextSignature)) continue;
      heap.push({
        cost: candidateCost(nextIds, base, index, progress, options, rpPerGe),
        sequence: sequence += 1,
        ids: nextIds,
      });
    }
  }
  return new Set();
}

export function calculate(database, input = {}) {
  validateDatabase(database);
  const index = vehicleIndex(database);
  const target = index.get(input.targetId);
  const start = input.startId ? index.get(input.startId) : null;
  if (!target) throw new Error("Bitte ein Ziel auswählen.");
  if (input.startId && !start) throw new Error(`Unbekanntes Fahrzeug: ${input.startId}`);
  if (start && (start.countryId !== target.countryId || start.branchId !== target.branchId)) {
    throw new Error("Start und Ziel müssen im selben Forschungsbaum liegen.");
  }

  const progressInput = input.progress || {};
  const progress = {
    ...progressInput,
    vehicles: {...(progressInput.vehicles || {})},
    ownedGe: progressInput.ownedGe ?? input.ownedGe,
    convertibleRp: progressInput.convertibleRp ?? input.convertibleRp,
  };
  if (input.partialRp != null && !progress.vehicles[target.id]) {
    progress.vehicles[target.id] = {researchedRp: Number(input.partialRp) || 0};
  }
  const options = {
    optimizeFor: input.optimizeFor || "ge",
    includeStartVehicle: Boolean(input.includeStartVehicle),
    includeHiddenLegacy: Boolean(input.includeHiddenLegacy),
    slDiscountPercent: Number(input.slDiscount || 0),
  };
  if (!new Set(["ge", "rp", "sl", "vehicles"]).has(options.optimizeFor)) {
    throw new Error("Unbekanntes Optimierungsziel.");
  }
  applyDiscount(0, options.slDiscountPercent);
  if (target.hiddenResearch && !options.includeHiddenLegacy) {
    throw new Error(`${target.name || target.id} ist ein ausgeblendetes Altbestandsfahrzeug.`);
  }
  const rpPerGe = Number(database.economy?.rpPerGE ?? 45);
  const owned = new Set();
  for (const [id, state] of Object.entries(progress.vehicles || {})) {
    const vehicle = index.get(id);
    if (vehicle && isOwned(state) && vehicle.countryId === target.countryId
      && vehicle.branchId === target.branchId) {
      for (const predecessor of closure(database, id)) owned.add(predecessor);
    }
  }
  if (start) {
    const startClosure = closure(database, start.id);
    for (const id of startClosure) {
      if (!options.includeStartVehicle || id !== start.id) owned.add(id);
    }
  }

  const required = new Set(closure(database, target.id).filter(id => !owned.has(id)));
  const reasons = new Map([...required].map(id => [id, "direct_path"]));
  for (const vehicle of treeVehicles(database, target.countryId, target.branchId)) {
    if (vehicle.reserve) owned.add(vehicle.id);
  }

  const rankRequirements = [];
  const firstRank = start ? start.rank : 1;
  for (let rank = firstRank; rank < target.rank; rank += 1) {
    const needed = Number(database.rankUnlock?.[target.countryId]?.[target.branchId]?.[String(rank)] || 0);
    if (needed <= 0) continue;
    const before = new Set([...owned, ...required]);
    const availableBefore = countRank(before, rank, index);
    let added = new Set();
    if (availableBefore < needed) {
      added = minimumRankAdditions(database, before, target.countryId, target.branchId, rank,
        needed, progress, options, Boolean(start) || Boolean(owned.size), index, rpPerGe);
      for (const id of added) {
        required.add(id);
        if (!reasons.has(id)) reasons.set(id, "rank_unlock");
      }
    }
    const availableAfter = countRank(new Set([...owned, ...required]), rank, index);
    if (availableAfter < needed) {
      throw new Error(`Rang ${rank + 1} kann nicht geöffnet werden: ${availableAfter}/${needed} Fahrzeuge.`);
    }
    rankRequirements.push({
      rank, required: needed, availableBefore, availableAfter,
      addedVehicleIds: [...added].filter(id => index.get(id).rank === rank)
        .sort((a, b) => compareTuples(sortKey(index.get(a)), sortKey(index.get(b)))),
    });
  }
  if (start && options.includeStartVehicle) {
    required.add(start.id);
    reasons.set(start.id, "start_vehicle");
  }

  const warnings = [];
  const lines = [...required]
    .sort((a, b) => compareTuples(sortKey(index.get(a)), sortKey(index.get(b))))
    .map(id => {
      const vehicle = index.get(id);
      const state = stateFor(progress, id);
      const alreadyOwned = isOwned(state) || owned.has(id);
      const researched = Math.min(Math.max(Number(state.researchedRp || 0), 0), vehicle.rp);
      const remainingRp = alreadyOwned ? 0 : Math.max(vehicle.rp - researched, 0);
      if (vehicle.reqUnlock) warnings.push(`${vehicle.name}: zusätzliche Freischaltung ${vehicle.reqUnlock}`);
      if (vehicle.hiddenResearch) warnings.push(`${vehicle.name}: Altbestandsfahrzeug`);
      return {
        id, name: vehicle.name || id, reason: reasons.get(id) || "rank_unlock",
        totalRp: vehicle.rp, researchedRp: researched, remainingRp,
        ge: remainingRp ? Math.ceil(remainingRp / rpPerGe) : 0,
        sl: alreadyOwned ? 0 : applyDiscount(Number(vehicle.sl || 0), options.slDiscountPercent),
        alreadyOwned,
      };
    });
  const totalRp = lines.reduce((sum, line) => sum + line.remainingRp, 0);
  const totalGeBeforeOwned = lines.reduce((sum, line) => sum + line.ge, 0);
  const ownedGe = Math.max(Number(progress.ownedGe ?? input.ownedGe ?? 0), 0);
  const convertibleRp = progress.convertibleRp ?? input.convertibleRp;
  return {
    startVehicleId: start?.id || null,
    targetVehicleId: target.id,
    lines,
    rankRequirements,
    requiredVehicleIds: lines.map(line => line.id),
    totalRp,
    totalGeBeforeOwned,
    totalGe: Math.max(totalGeBeforeOwned - ownedGe, 0),
    totalSl: lines.reduce((sum, line) => sum + line.sl, 0),
    convertibleRpShortfall: convertibleRp == null ? 0 : Math.max(totalRp - Number(convertibleRp), 0),
    warnings: [...new Set(warnings)],
  };
}
