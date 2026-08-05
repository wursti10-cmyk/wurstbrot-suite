export function validateDatabase(raw) {
  if (!raw || raw.schemaVersion !== 1) throw new Error("Nicht unterstützte Datenbank.");
  if (!Array.isArray(raw.vehicles) || !raw.vehicles.length) throw new Error("Keine Fahrzeuge gefunden.");
  const ids = new Set();
  for (const vehicle of raw.vehicles) {
    if (!vehicle.id || ids.has(vehicle.id)) throw new Error(`Ungültige Fahrzeug-ID: ${vehicle.id || "leer"}`);
    ids.add(vehicle.id);
  }
  for (const [id, predecessor] of Object.entries(raw.predecessors || {})) {
    if (ids.has(id) && predecessor && !ids.has(predecessor)) throw new Error(`Unbekannter Vorgänger: ${predecessor}`);
  }
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
    seen.add(current); result.push(current);
    current = (database.predecessors || {})[current] || null;
  }
  return result.reverse();
}

function discount(value, percent) { return Math.round(value * (1 - percent / 100)); }

export function calculate(database, {startId = null, targetId, partialRp = 0, ownedGe = 0, slDiscount = 0} = {}) {
  validateDatabase(database);
  const index = vehicleIndex(database);
  const target = index.get(targetId);
  const start = startId ? index.get(startId) : null;
  if (!target) throw new Error("Bitte ein Ziel auswählen.");
  if (start && (start.countryId !== target.countryId || start.branchId !== target.branchId)) {
    throw new Error("Start und Ziel müssen im selben Forschungsbaum liegen.");
  }
  const owned = new Set(start ? closure(database, start.id) : []);
  const required = closure(database, target.id).filter(id => !owned.has(id));
  const rpPerGe = Number(database.economy?.rpPerGE || 45);
  const lines = required.map(id => {
    const vehicle = index.get(id);
    const researched = id === targetId ? Math.max(0, Math.min(Number(partialRp) || 0, vehicle.rp)) : 0;
    const remainingRp = Math.max(0, Number(vehicle.rp || 0) - researched);
    return {id, name: vehicle.name || id, remainingRp, ge: remainingRp ? Math.ceil(remainingRp / rpPerGe) : 0, sl: discount(Number(vehicle.sl || 0), Number(slDiscount) || 0)};
  });
  const totalRp = lines.reduce((sum, line) => sum + line.remainingRp, 0);
  const totalGeBeforeOwned = lines.reduce((sum, line) => sum + line.ge, 0);
  return {lines, totalRp, totalGeBeforeOwned, totalGe: Math.max(0, totalGeBeforeOwned - (Number(ownedGe) || 0)), totalSl: lines.reduce((sum, line) => sum + line.sl, 0)};
}
