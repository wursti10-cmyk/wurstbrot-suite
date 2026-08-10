import {createHash} from "node:crypto";
import {mkdir, readFile, writeFile} from "node:fs/promises";
import path from "node:path";
import {fileURLToPath} from "node:url";
import {calculate} from "../apps/web/solver.mjs";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const fixture = JSON.parse(await readFile(
  path.join(root, "accuracy", "acceptance", "release_hardening_2.57.1.67.json"),
  "utf8",
));
const database = JSON.parse(await readFile(
  path.join(root, "data", "samples", "WT_Database_2.57.1.67.json"),
  "utf8",
));

function assert(condition, message) {
  if (!condition) throw new Error(`Browser release-hardening violation: ${message}`);
}

function canonical(value) {
  if (Array.isArray(value)) return value.map(canonical);
  if (value !== null && typeof value === "object") {
    return Object.fromEntries(Object.keys(value).sort().map((key) => [key, canonical(value[key])]));
  }
  return value;
}

function fingerprint(value, version) {
  const digest = createHash("sha256")
    .update(JSON.stringify(canonical(value)))
    .digest("hex");
  return `${version}:${digest}`;
}

assert(fixture.schemaVersion === 1, "fixture schema");
assert(fixture.suiteVersion === "1.0.0-accuracy10", "fixture suite version");
assert(fixture.generationPolicy === "manual_review_only", "manual fixture policy");
assert(fixture.immutable === true, "immutable fixture");
assert(fixture.cases.length === 44, "44 direct tree references");

const fixtureContent = Object.fromEntries(
  Object.entries(fixture).filter(
    ([key]) => !["fixtureFingerprint", "resultFingerprint"].includes(key),
  ),
);
assert(
  fingerprint(fixtureContent, "accuracy10-direct-fixture-v1") === fixture.fixtureFingerprint,
  "fixture fingerprint",
);

const vehicles = new Map(database.vehicles.map((item) => [item.id, item]));
const results = [];
for (const item of fixture.cases) {
  const target = vehicles.get(item.targetVehicleId);
  const start = vehicles.get(item.startVehicleId);
  const profile = fixture.profiles[item.profile];
  assert(target && start, `${item.caseId} vehicles exist`);
  assert(database.predecessors[target.id] === start.id, `${item.caseId} static path oracle`);
  assert(
    start.countryId === target.countryId && start.branchId === target.branchId,
    `${item.caseId} same tree`,
  );
  assert(start.rank === target.rank, `${item.caseId} same-rank direct case`);
  const researchedRp = profile.targetProgress === "half" ? Math.floor(target.rp / 2) : 0;
  const remainingRp = target.rp - researchedRp;
  const convertibleRp = profile.convertibleRp === "half_remaining"
    ? Math.floor(remainingRp / 2)
    : null;
  const progress = {
    vehicles: researchedRp > 0 ? {[target.id]: {researchedRp}} : {},
    ownedGe: profile.ownedGe,
    convertibleRp,
  };
  const actual = calculate(database, {
    startId: start.id,
    targetId: target.id,
    progress,
    slDiscount: profile.slDiscountPercent,
  });
  const expected = {
    requiredVehicleIds: item.expectedRequiredVehicleIds,
    remainingRp,
    geBeforeOwned: remainingRp === 0 ? 0 : Math.ceil(remainingRp / fixture.rpPerGE),
    geAfterOwned: Math.max(
      (remainingRp === 0 ? 0 : Math.ceil(remainingRp / fixture.rpPerGE)) - profile.ownedGe,
      0,
    ),
    sl: Math.round(target.sl * (1 - profile.slDiscountPercent / 100)),
    convertibleRpShortfall: convertibleRp === null ? 0 : Math.max(remainingRp - convertibleRp, 0),
  };
  const passed = JSON.stringify(actual.requiredVehicleIds)
    === JSON.stringify(expected.requiredVehicleIds)
    && actual.lines.length === 1
    && actual.lines[0].id === target.id
    && actual.lines[0].remainingRp === expected.remainingRp
    && actual.lines[0].ge === expected.geBeforeOwned
    && actual.lines[0].sl === expected.sl
    && actual.totalRp === expected.remainingRp
    && actual.totalGeBeforeOwned === expected.geBeforeOwned
    && actual.totalGe === expected.geAfterOwned
    && actual.totalSl === expected.sl
    && actual.convertibleRpShortfall === expected.convertibleRpShortfall;
  assert(passed, `${item.caseId} legacy result`);
  results.push({caseId: item.caseId, expected, passed});
}

const legacyEntryPoints = [
  "apps/web/app.js",
  "apps/web/solver.mjs",
  "apps/ge-calculator/ge_calculator_gui.py",
];
for (const relative of legacyEntryPoints) {
  const source = await readFile(path.join(root, relative), "utf8");
  assert(!source.includes("graph_experimental"), `${relative} has no experimental activation`);
  assert(!source.includes("GraphCalculationPipeline"), `${relative} has no graph runtime`);
}

const report = {
  schemaVersion: 1,
  harnessVersion: "1.0.0-accuracy10",
  gameVersion: fixture.gameVersion,
  browserExecutionMode: "legacy",
  browserLegacyPassed: true,
  graphRuntimeAvailable: false,
  hiddenGraphActivationFound: false,
  directCases: fixture.cases.length,
  passed: results.length,
  failed: 0,
  fixtureFingerprint: fixture.fixtureFingerprint,
  resultFingerprint: fingerprint(results, "accuracy10-browser-legacy-v1"),
  productiveBrowserLogicModified: false,
};

const serialized = `${JSON.stringify(report, null, 2)}\n`;
const outputFlag = process.argv.indexOf("--output");
if (outputFlag >= 0) {
  const output = process.argv[outputFlag + 1];
  assert(Boolean(output), "--output requires a path");
  await mkdir(path.dirname(path.resolve(output)), {recursive: true});
  await writeFile(output, serialized, "utf8");
}
process.stdout.write(serialized);
