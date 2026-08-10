import { createHash } from "node:crypto";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const fixturePath = path.join(root, "accuracy", "golden", "2.57.1.67.json");
const fixture = JSON.parse(await readFile(fixturePath, "utf8"));
const coreFixturePath = path.join(
  root,
  "accuracy",
  "golden",
  "core_contract_2.57.1.67.json",
);
const coreFixture = JSON.parse(await readFile(coreFixturePath, "utf8"));

const FIXTURE_VERSION = "accuracy-golden-fixture-v1";
const RESULT_VERSION = "accuracy-golden-results-v1";
const CORE_FIXTURE_VERSION = "accuracy-core-reference-fixture-v1";
const CORE_RESULT_VERSION = "accuracy-core-reference-results-v1";

function canonical(value) {
  if (Array.isArray(value)) return value.map(canonical);
  if (value !== null && typeof value === "object") {
    return Object.fromEntries(
      Object.keys(value)
        .sort()
        .map((key) => [key, canonical(value[key])]),
    );
  }
  return value;
}

function fingerprint(value, version) {
  const bytes = JSON.stringify(canonical(value));
  return `${version}:${createHash("sha256").update(bytes, "utf8").digest("hex")}`;
}

function assert(condition, message) {
  if (!condition) throw new Error(`Browser shadow contract violation: ${message}`);
}

assert(fixture.schemaVersion === 1, "fixture schema version");
assert(fixture.gameVersion === "2.57.1.67", "game version");
assert(fixture.generationPolicy === "manual_review_only", "manual-only generation");
assert(fixture.immutable === true, "immutable fixture flag");
assert(Array.isArray(fixture.cases) && fixture.cases.length === 60, "60 golden cases");

const caseIds = fixture.cases.map((item) => item.case_id);
assert(JSON.stringify(caseIds) === JSON.stringify([...caseIds].sort()), "case ordering");
assert(new Set(caseIds).size === caseIds.length, "case ID uniqueness");

const fixtureContent = Object.fromEntries(
  Object.entries(fixture).filter(([key]) => !["fixtureFingerprint", "resultFingerprint"].includes(key)),
);
assert(
  fingerprint(fixtureContent, FIXTURE_VERSION) === fixture.fixtureFingerprint,
  "fixture fingerprint",
);

assert(coreFixture.schemaVersion === 1, "core fixture schema version");
assert(coreFixture.gameVersion === fixture.gameVersion, "core fixture game version");
assert(coreFixture.generationPolicy === "manual_review_only", "core manual-only generation");
assert(coreFixture.immutable === true, "core immutable fixture flag");
assert(Array.isArray(coreFixture.cases) && coreFixture.cases.length === 8, "8 core cases");
const coreCaseIds = coreFixture.cases.map((item) => item.case_id);
assert(JSON.stringify(coreCaseIds) === JSON.stringify([...coreCaseIds].sort()), "core case ordering");
assert(new Set(coreCaseIds).size === coreCaseIds.length, "core case ID uniqueness");
const coreFixtureContent = Object.fromEntries(
  Object.entries(coreFixture).filter(
    ([key]) => !["fixtureFingerprint", "resultFingerprint"].includes(key),
  ),
);
assert(
  fingerprint(coreFixtureContent, CORE_FIXTURE_VERSION) === coreFixture.fixtureFingerprint,
  "core fixture fingerprint",
);

function validateCase(item) {
  const input = item.input;
  const expected = item.expected;
  const lines = expected.vehicle_cost_lines;
  assert(
    JSON.stringify(Object.keys(input).sort())
      === JSON.stringify(["options", "progress", "start_vehicle_id", "target_vehicle_id"]),
    `${item.case_id} canonical input fields`,
  );
  assert(typeof input.target_vehicle_id === "string", `${item.case_id} target input`);
  assert(input.start_vehicle_id === null || typeof input.start_vehicle_id === "string", `${item.case_id} start input`);
  assert(Number.isInteger(input.progress.owned_ge) && input.progress.owned_ge >= 0, `${item.case_id} owned GE input`);
  assert([0, 30, 50].includes(input.options.sl_discount_percent), `${item.case_id} SL discount input`);
  assert(Array.isArray(lines), `${item.case_id} cost lines`);
  let rp = 0;
  let ge = 0;
  let sl = 0;
  for (const line of lines) {
    for (const key of ["total_rp", "researched_rp", "remaining_rp", "ge", "base_sl", "discounted_sl"]) {
      assert(Number.isInteger(line[key]) && line[key] >= 0, `${item.case_id} ${key}`);
    }
    assert(line.remaining_rp <= line.total_rp, `${item.case_id} remaining RP range`);
    assert(line.ge === (line.remaining_rp === 0 ? 0 : Math.ceil(line.remaining_rp / 45)), `${item.case_id} per-line GE rounding`);
    assert(
      line.discounted_sl
        === Math.round(line.base_sl * (1 - input.options.sl_discount_percent / 100)),
      `${item.case_id} per-line SL discount`,
    );
    rp += line.remaining_rp;
    ge += line.ge;
    sl += line.discounted_sl;
  }
  if (expected.pipeline_status === "complete") {
    assert(expected.totals !== null, `${item.case_id} complete totals`);
    assert(expected.partial_totals === null, `${item.case_id} no partial totals`);
    assert(expected.totals.remaining_rp === rp, `${item.case_id} RP line sum`);
    assert(expected.totals.ge_before_owned === ge, `${item.case_id} GE line sum`);
    assert(
      expected.totals.ge_after_owned === Math.max(ge - input.progress.owned_ge, 0),
      `${item.case_id} owned GE subtraction`,
    );
    assert(expected.totals.sl === sl, `${item.case_id} SL line sum`);
    const convertible = input.progress.convertible_rp;
    assert(
      expected.totals.convertible_rp_shortfall
        === (convertible === null ? 0 : Math.max(rp - convertible, 0)),
      `${item.case_id} convertible RP shortfall`,
    );
  } else if (expected.pipeline_status === "partial") {
    assert(expected.totals === null, `${item.case_id} partial has no binding totals`);
    assert(expected.partial_totals !== null, `${item.case_id} partial diagnostics`);
    assert(expected.partial_totals.remaining_rp === rp, `${item.case_id} partial RP sum`);
    assert(expected.partial_totals.ge_before_owned === ge, `${item.case_id} partial GE sum`);
    assert(expected.partial_totals.sl === sl, `${item.case_id} partial SL sum`);
  } else {
    assert(expected.totals === null, `${item.case_id} unavailable totals`);
    assert(lines.length === 0, `${item.case_id} unavailable lines`);
  }
  assert(Array.isArray(expected.rule_ids), `${item.case_id} rule IDs`);
  assert(Array.isArray(expected.explanation_trace), `${item.case_id} explanation trace`);
}

for (const item of fixture.cases) validateCase(item);
for (const item of coreFixture.cases) validateCase(item);

const canonicalResults = fixture.cases.map((item) => ({
  caseId: item.case_id,
  actual: item.expected,
}));
const resultFingerprint = fingerprint(canonicalResults, RESULT_VERSION);
assert(resultFingerprint === fixture.resultFingerprint, "canonical result fingerprint");
const coreCanonicalResults = coreFixture.cases.map((item) => ({
  caseId: item.case_id,
  actual: item.expected,
}));
const coreResultFingerprint = fingerprint(coreCanonicalResults, CORE_RESULT_VERSION);
assert(coreResultFingerprint === coreFixture.resultFingerprint, "core result fingerprint");

const report = {
  schemaVersion: 1,
  harnessVersion: "1.0.0-shadow",
  gameVersion: fixture.gameVersion,
  browserParityStatus: "fixture_validation_only",
  graphRuntimeAvailable: false,
  missingGraphRuntimeParity: true,
  canonicalGoldenCasesValidated: fixture.cases.length,
  canonicalCoreReferenceCasesValidated: coreFixture.cases.length,
  passed: fixture.cases.length + coreFixture.cases.length,
  failed: 0,
  statusValuesValidated: [...new Set(fixture.cases.map((item) => item.expected.pipeline_status))].sort(),
  ruleIdsValidated: [...new Set(fixture.cases.flatMap((item) => item.expected.rule_ids))].sort(),
  vehicleCostFieldsValidated: [
    "total_rp",
    "researched_rp",
    "remaining_rp",
    "ge",
    "base_sl",
    "discounted_sl",
  ],
  incompleteSemanticsValidated: true,
  fixtureFingerprint: fixture.fixtureFingerprint,
  resultFingerprint,
  coreFixtureFingerprint: coreFixture.fixtureFingerprint,
  coreResultFingerprint,
  platformFieldsInFingerprint: false,
  productiveBrowserLogicModified: false,
  knownLimit: "The browser harness validates canonical graph fixtures; it does not execute a browser graph runtime.",
};

const serialized = `${JSON.stringify(report, null, 2)}\n`;
const outputFlag = process.argv.indexOf("--output");
if (outputFlag >= 0) {
  const output = process.argv[outputFlag + 1];
  assert(Boolean(output), "--output requires a path");
  await mkdir(path.dirname(path.resolve(output)), { recursive: true });
  await writeFile(output, serialized, "utf8");
}
process.stdout.write(serialized);
