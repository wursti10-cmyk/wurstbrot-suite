import test from "node:test";
import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import {calculate, closure, validateDatabase} from "../apps/web/solver.mjs";

const database = {schemaVersion:1,economy:{rpPerGE:45},vehicles:[
  {id:"a",name:"A",countryId:"de",branchId:"tank",rank:1,rp:0,sl:0},
  {id:"b",name:"B",countryId:"de",branchId:"tank",rank:2,rp:100,sl:1000},
  {id:"c",name:"C",countryId:"de",branchId:"tank",rank:3,rp:90,sl:2000}
],predecessors:{a:null,b:"a",c:"b"}};

test("validates and resolves a research closure", () => {
  assert.equal(validateDatabase(database), database);
  assert.deepEqual(closure(database, "c"), ["a","b","c"]);
});
test("calculates per-vehicle GE rounding and progress", () => {
  const result = calculate(database,{startId:"a",targetId:"c",partialRp:45,ownedGe:1,slDiscount:50});
  assert.equal(result.totalRp,145); assert.equal(result.totalGeBeforeOwned,4); assert.equal(result.totalGe,3); assert.equal(result.totalSl,1500);
});
test("rejects cycles", () => {
  const cyclic = structuredClone(database); cyclic.predecessors.a="c";
  assert.throws(() => closure(cyclic,"c"), /Zyklus/);
});

test("matches the shared Python contract including rank unlocks", () => {
  const fixture = JSON.parse(readFileSync(
    new URL("fixtures/solver_contract.json", import.meta.url), "utf8"));
  const input = fixture.input;
  const result = calculate(fixture.database, {
    startId: input.startId,
    targetId: input.targetId,
    progress: {
      vehicles: {[input.targetId]: {researchedRp: input.targetResearchedRp}},
      ownedGe: input.ownedGe,
      convertibleRp: input.convertibleRp,
    },
    slDiscount: input.slDiscountPercent,
    optimizeFor: input.optimizeFor,
  });
  const expected = fixture.expected;
  assert.deepEqual(result.requiredVehicleIds, expected.requiredVehicleIds);
  assert.deepEqual(result.lines.map(line => line.reason), expected.reasons);
  assert.equal(result.totalRp, expected.totalRp);
  assert.equal(result.totalGeBeforeOwned, expected.totalGeBeforeOwned);
  assert.equal(result.totalGe, expected.totalGeAfterOwned);
  assert.equal(result.totalSl, expected.totalSl);
  assert.equal(result.convertibleRpShortfall, expected.convertibleRpShortfall);
  assert.equal(result.rankRequirements[0].availableAfter, expected.rankAvailableAfter);
});
