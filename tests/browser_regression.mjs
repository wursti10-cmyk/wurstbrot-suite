import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import {calculate, validateDatabase} from "../apps/web/solver.mjs";

const database = validateDatabase(JSON.parse(readFileSync(
  new URL("../data/samples/WT_Database_2.57.1.67.json", import.meta.url), "utf8")));
const stats = {root_targets: 0, passed: 0, skipped_special: 0};

for (const target of database.vehicles) {
  if (target.hiddenResearch || target.reqUnlock) {
    stats.skipped_special += 1;
    continue;
  }
  const predecessor = database.predecessors?.[target.id];
  if (!predecessor) {
    stats.root_targets += 1;
    continue;
  }
  const result = calculate(database, {
    startId: predecessor,
    targetId: target.id,
    optimizeFor: "ge",
  });
  assert.ok(result.requiredVehicleIds.includes(target.id), target.id);
  assert.equal(result.totalGeBeforeOwned,
    result.lines.reduce((sum, line) => sum + line.ge, 0), target.id);
  assert.ok(result.rankRequirements.every(rank => rank.availableAfter >= rank.required), target.id);
  stats.passed += 1;
}

assert.deepEqual(stats, {root_targets: 206, passed: 1977, skipped_special: 49});
console.log(JSON.stringify(stats));
