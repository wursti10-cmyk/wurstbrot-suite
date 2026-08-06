from __future__ import annotations

import json
import math
from collections import Counter
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from .database import VehicleDatabase
from .graph_pipeline import GraphCalculationPipeline, canonicalize, stable_fingerprint
from .models import PlayerProgress, SolveOptions, Vehicle, VehicleProgress
from .research_graph import ResearchGraphBuilder


ACCURACY_BASELINE_SCHEMA_VERSION = 1
GOLDEN_SUITE_SCHEMA_VERSION = 1
CONFIDENCE_REPORT_SCHEMA_VERSION = 1
CONFIDENCE_SUITE_VERSION = "1.0.0-shadow"
BASELINE_FINGERPRINT_VERSION = "accuracy-baseline-v1"
DATAMINE_FINGERPRINT_VERSION = "datamine-semantic-v1"
GRAPH_FINGERPRINT_VERSION = "research-graph-v1"
GOLDEN_FIXTURE_FINGERPRINT_VERSION = "accuracy-golden-fixture-v1"
GOLDEN_RESULT_FINGERPRINT_VERSION = "accuracy-golden-results-v1"
CONFIDENCE_REPORT_FINGERPRINT_VERSION = "accuracy-confidence-report-v1"

PROVENANCE_CATEGORIES = (
    "DATAMINE_DIRECT",
    "FORMULA_DERIVED",
    "LEGACY_CONFIRMED",
    "MANUALLY_REVIEWED",
    "SYNTHETIC_CONTRACT",
    "UNRESOLVED_SOURCE_LIMITATION",
)

REQUIRED_GOLDEN_TAGS = (
    "chain:short",
    "chain:medium",
    "chain:long",
    "start_a_target_b",
    "progress:target_partial",
    "progress:intermediate_partial",
    "progress:intermediate_purchased",
    "rank:fulfilled",
    "rank:partial",
    "folder",
    "req_unlock",
    "hidden:allowed",
    "hidden:blocked",
    "zero_rp",
    "zero_sl",
    "owned_ge",
    "convertible_rp_shortfall",
    "sl_discount:0",
    "sl_discount:30",
    "sl_discount:50",
)

REQUIRED_E2E_TAGS = (
    "e2e:germany_ground",
    "e2e:usa_ground",
    "e2e:ussr_ground",
    "e2e:japan_ground",
    "e2e:israel_ground",
    "e2e:aircraft",
    "e2e:helicopter",
    "e2e:bluewater",
    "e2e:coastal",
)

EXPECTED_PARTIAL_TARGET_IDS = (
    "fiat_cr42",
    "fiat_g50_seria2",
    "fiat_g50_seria7as",
    "mc-202",
    "mc200_serie3",
    "mc200_serie7",
    "r2y2_kai",
    "r2y2_v1",
    "r2y2_v2",
    "sm_79_1936",
    "sm_79_1939",
    "sm_79_1941",
    "sm_79_1943",
    "sm_79_iar",
)

EXPECTED_DECISION_IDS = (
    "CONTRACT_SL_DISCOUNT_DOMAIN",
    "CONTRACT_INVALID_PROGRESS",
    "CONTRACT_RESEARCH_FLAG_RP_CONFLICT",
    "CONTRACT_PARTIAL_OWNED_GE",
    "CONTRACT_LEGACY_RANK_COMPATIBILITY",
)

PLATFORM_EXCLUDED_FIELDS = (
    "generatedAt",
    "localPath",
    "objectAddress",
    "platform",
    "pythonExecutable",
    "pythonImplementation",
    "pythonVersion",
    "timestamp",
)


class AccuracyContractError(ValueError):
    pass


@dataclass(frozen=True)
class AccuracySuiteResult:
    total: int
    passed: int
    failed: int
    results_by_origin: dict[str, dict[str, int]]
    case_results: tuple[dict[str, Any], ...]
    fingerprint_version: str
    fingerprint: str
    reviewed_end_to_end_references: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "total": self.total,
            "passed": self.passed,
            "failed": self.failed,
            "resultsByOrigin": canonicalize(self.results_by_origin),
            "caseResults": [canonicalize(item) for item in self.case_results],
            "fingerprintVersion": self.fingerprint_version,
            "fingerprint": self.fingerprint,
            "reviewedEndToEndReferences": self.reviewed_end_to_end_references,
        }


def load_json(path: str | Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise AccuracyContractError(f"{path} must contain a JSON object.")
    return payload


def database_semantic_payload(database: VehicleDatabase) -> dict[str, Any]:
    vehicles = []
    for vehicle in sorted(database.vehicles.values(), key=lambda item: item.id):
        vehicles.append(
            {
                "id": vehicle.id,
                "name": vehicle.name,
                "countryId": vehicle.country_id,
                "branchId": vehicle.branch_id,
                "rank": vehicle.rank,
                "rp": vehicle.rp,
                "sl": vehicle.sl,
                "reserve": vehicle.reserve,
                "premium": vehicle.premium,
                "special": vehicle.special,
                "hiddenResearch": vehicle.hidden_research,
                "reqUnlock": vehicle.req_unlock,
                "group": vehicle.group,
                "groupIndex": vehicle.group_index,
                "column": vehicle.column,
                "order": vehicle.order,
            }
        )
    return {
        "schemaVersion": 1,
        "gameVersion": database.game_version,
        "economy": {"rpPerGE": database.rp_per_ge},
        "vehicles": vehicles,
        "predecessors": canonicalize(database.predecessors),
        "groups": canonicalize(database.raw_groups),
        "rankUnlock": canonicalize(database.rank_unlock),
    }


def database_semantic_fingerprint(database: VehicleDatabase) -> str:
    return stable_fingerprint(
        database_semantic_payload(database),
        version=DATAMINE_FINGERPRINT_VERSION,
    )


def graph_semantic_fingerprint(database: VehicleDatabase) -> str:
    graph = ResearchGraphBuilder.from_database(database)
    return stable_fingerprint(graph.to_dict(), version=GRAPH_FINGERPRINT_VERSION)


def baseline_fingerprint(payload: dict[str, Any]) -> str:
    content = {
        key: value
        for key, value in payload.items()
        if key not in {"artifactReferences", "fingerprint"}
    }
    return stable_fingerprint(content, version=BASELINE_FINGERPRINT_VERSION)


def validate_baseline(
    payload: dict[str, Any],
    database: VehicleDatabase,
    *,
    validator_version: str,
    validator_rule_count: int,
) -> None:
    _require(payload.get("schemaVersion") == ACCURACY_BASELINE_SCHEMA_VERSION, "baseline schema")
    _require(payload.get("gameVersion") == database.game_version, "baseline game version")
    _require(payload.get("databaseSchemaVersion") == 1, "database schema version")
    _require(payload.get("validatorVersion") == validator_version, "validator version")
    _require(
        payload.get("pipelineVersion") == GraphCalculationPipeline.version,
        "pipeline version",
    )
    _require(payload.get("ruleCount") == validator_rule_count, "validator rule count")
    trees = {(item.country_id, item.branch_id) for item in database.vehicles.values()}
    countries = {item.country_id for item in database.vehicles.values()}
    graph = ResearchGraphBuilder.from_database(database)
    _require(payload.get("vehicleCount") == len(database.vehicles), "vehicle count")
    _require(payload.get("countryCount") == len(countries), "country count")
    _require(payload.get("researchTreeCount") == len(trees), "research tree count")
    _require(payload.get("groupCount") == len(database.raw_groups), "group count")
    _require(payload.get("graphNodeCount") == len(graph.nodes), "graph node count")
    _require(payload.get("graphEdgeCount") == len(graph.edges), "graph edge count")
    _require(
        payload.get("knownContractDifferences") == list(EXPECTED_DECISION_IDS),
        "known contract differences",
    )
    fingerprints = payload.get("fingerprints", {})
    _require(
        fingerprints.get("datamine") == database_semantic_fingerprint(database),
        "datamine fingerprint",
    )
    _require(
        fingerprints.get("graph") == graph_semantic_fingerprint(database),
        "graph fingerprint",
    )
    known = payload.get("knownCases", {})
    _require(known.get("shadowScenarioCount") == 2_090, "shadow scenario count")
    _require(known.get("unresolvedExpectedComparisons") == 80, "unresolved count")
    _require(known.get("partialPipelineResults") == 80, "partial pipeline count")
    _require(known.get("inputContractDifferences") == 20, "input contract count")
    _require(known.get("specialCaseCount") == 49, "special case count")
    _require(known.get("specialCompleteCount") == 35, "special complete count")
    _require(known.get("specialPartialCount") == 14, "special partial count")
    _require(known.get("partialTargets") == list(EXPECTED_PARTIAL_TARGET_IDS), "partial targets")
    _require(
        payload.get("fingerprintVersion") == BASELINE_FINGERPRINT_VERSION,
        "fingerprint version",
    )
    _require(payload.get("fingerprint") == baseline_fingerprint(payload), "baseline fingerprint")
    _reject_environment_fields(payload)


def golden_fixture_fingerprint(payload: dict[str, Any]) -> str:
    content = {
        key: value
        for key, value in payload.items()
        if key not in {"fixtureFingerprint", "resultFingerprint"}
    }
    return stable_fingerprint(content, version=GOLDEN_FIXTURE_FINGERPRINT_VERSION)


def validate_golden_fixture(payload: dict[str, Any], database: VehicleDatabase) -> None:
    _require(payload.get("schemaVersion") == GOLDEN_SUITE_SCHEMA_VERSION, "golden schema")
    _require(payload.get("gameVersion") == database.game_version, "golden game version")
    _require(payload.get("generationPolicy") == "manual_review_only", "manual generation policy")
    _require(payload.get("immutable") is True, "fixture immutability flag")
    _require(payload.get("rpPerGE") == database.rp_per_ge, "golden rpPerGE")
    _require(
        payload.get("provenanceCategories") == list(PROVENANCE_CATEGORIES),
        "provenance category registry",
    )
    _require(
        payload.get("fixtureFingerprintVersion") == GOLDEN_FIXTURE_FINGERPRINT_VERSION,
        "fixture fingerprint version",
    )
    _require(
        payload.get("resultFingerprintVersion") == GOLDEN_RESULT_FINGERPRINT_VERSION,
        "result fingerprint version",
    )
    cases = payload.get("cases")
    _require(isinstance(cases, list) and len(cases) >= 44, "at least 44 golden cases")
    case_ids = [item.get("case_id") for item in cases if isinstance(item, dict)]
    _require(len(case_ids) == len(cases), "golden cases are objects")
    _require(case_ids == sorted(case_ids), "deterministic golden case ordering")
    _require(len(case_ids) == len(set(case_ids)), "unique golden case IDs")

    all_tags: set[str] = set()
    origins: Counter[str] = Counter()
    tree_coverage: set[tuple[str, str]] = set()
    reviewed_e2e: set[str] = set()
    synthetic_databases = payload.get("syntheticDatabases", {})
    _require(isinstance(synthetic_databases, dict), "synthetic database registry")
    for case in cases:
        _validate_golden_case(case, database, synthetic_databases)
        tags = set(case["tags"])
        all_tags.update(tags)
        origins[case["primary_origin"]] += 1
        if "tree_coverage" in tags:
            tree_coverage.add((case["tree"]["country_id"], case["tree"]["vehicle_type"]))
        if case["review_status"] == "reviewed":
            reviewed_e2e.update(tag for tag in tags if tag.startswith("e2e:"))

    expected_trees = {
        (item.country_id, item.branch_id) for item in database.vehicles.values()
    }
    _require(tree_coverage == expected_trees, "all research trees have a golden case")
    _require(set(PROVENANCE_CATEGORIES) <= set(origins), "every provenance category is used")
    _require(set(REQUIRED_GOLDEN_TAGS) <= all_tags, "required golden scenario tags")
    _require(set(REQUIRED_E2E_TAGS) <= reviewed_e2e, "reviewed end-to-end references")
    _require(
        payload.get("fixtureFingerprint") == golden_fixture_fingerprint(payload),
        "golden fixture fingerprint",
    )
    _require(
        isinstance(payload.get("resultFingerprint"), str)
        and payload["resultFingerprint"].startswith(f"{GOLDEN_RESULT_FINGERPRINT_VERSION}:"),
        "golden result fingerprint",
    )
    _reject_environment_fields(payload)


def _validate_golden_case(
    case: dict[str, Any],
    database: VehicleDatabase,
    synthetic_databases: dict[str, Any],
) -> None:
    required = {
        "case_id",
        "purpose",
        "game_version",
        "database_ref",
        "tree",
        "tags",
        "input",
        "expected",
        "rationale",
        "primary_origin",
        "supporting_origins",
        "origin_evidence",
        "review_status",
    }
    _require(required <= set(case), f"required fields in {case.get('case_id')}")
    _require(case["game_version"] == database.game_version, "case game version")
    _require(case["review_status"] in {"reviewed", "approved"}, "review status")
    _require(case["primary_origin"] in PROVENANCE_CATEGORIES, "primary provenance")
    _require(
        all(item in PROVENANCE_CATEGORIES for item in case["supporting_origins"]),
        "supporting provenance",
    )
    evidence_origins = {item.get("origin") for item in case["origin_evidence"]}
    _require(case["primary_origin"] in evidence_origins, "primary provenance evidence")
    if case["primary_origin"] == "LEGACY_CONFIRMED":
        independent = {
            "DATAMINE_DIRECT",
            "FORMULA_DERIVED",
            "MANUALLY_REVIEWED",
            "SYNTHETIC_CONTRACT",
        }
        _require(
            bool(independent & set(case["supporting_origins"])),
            "legacy confirmation has independent support",
        )
    database_ref = case["database_ref"]
    _require(
        database_ref == "sample" or database_ref in synthetic_databases,
        "case database reference",
    )
    source_database = (
        database
        if database_ref == "sample"
        else _database_from_payload(synthetic_databases[database_ref])
    )
    request = case["input"]
    _require(
        set(request)
        == {"target_vehicle_id", "start_vehicle_id", "progress", "options"},
        "canonical case input",
    )
    _progress_from_payload(request["progress"])
    _options_from_payload(request["options"])
    expected = case["expected"]
    expected_fields = {
        "pipeline_status",
        "resolution_status",
        "required_vehicle_ids",
        "rank_requirements",
        "folder_requirements",
        "unlock_requirements",
        "vehicle_cost_lines",
        "totals",
        "partial_totals",
        "rule_ids",
        "incomplete_reason_codes",
        "explanation_trace",
    }
    _require(expected_fields == set(expected), "canonical golden expected fields")
    status = expected["pipeline_status"]
    if status == "complete":
        _require(expected["totals"] is not None, "complete totals")
        _require(expected["partial_totals"] is None, "no partial totals for complete")
    elif status == "partial":
        _require(expected["totals"] is None, "partial has no binding totals")
        _require(expected["partial_totals"] is not None, "partial diagnostic totals")
    elif status in {"blocked", "unavailable", "invalid_input"}:
        _require(expected["totals"] is None, "unavailable has no totals")
        _require(expected["vehicle_cost_lines"] == [], "unavailable has no invented lines")
    else:
        raise AccuracyContractError(f"Unsupported golden pipeline status: {status!r}")
    _validate_golden_cost_sources(case, source_database)


def _validate_golden_cost_sources(
    case: dict[str, Any],
    database: VehicleDatabase,
) -> None:
    """Verify frozen numeric expectations directly from datamine and formulas."""
    request = case["input"]
    expected = case["expected"]
    progress = request["progress"]
    options = request["options"]
    target = request["target_vehicle_id"]
    if target in database.vehicles:
        closure = list(database.closure(target))
        _require(
            set(expected["required_vehicle_ids"]) <= set(closure),
            "required vehicles come from the datamine predecessor closure",
        )
        start = request["start_vehicle_id"]
        if start in closure and not options["include_start_vehicle"]:
            obsolete = set(closure[: closure.index(start) + 1])
            _require(
                not obsolete.intersection(expected["required_vehicle_ids"]),
                "fulfilled start segment is excluded",
            )
        purchased = {
            vehicle_id
            for vehicle_id, state in progress["vehicles"].items()
            if state["purchased"]
        }
        _require(
            not purchased.intersection(expected["required_vehicle_ids"]),
            "purchased vehicles are excluded from required vehicles",
        )
    line_ids = [item["vehicle_id"] for item in expected["vehicle_cost_lines"]]
    if expected["pipeline_status"] in {"complete", "partial"}:
        _require(line_ids == expected["required_vehicle_ids"], "cost lines match required vehicles")
    for line in expected["vehicle_cost_lines"]:
        vehicle = database.get(line["vehicle_id"])
        state = progress["vehicles"].get(
            vehicle.id,
            {"researched_rp": 0, "researched": False, "purchased": False},
        )
        already_researched = (
            state["researched"]
            or state["purchased"]
            or vehicle.reserve
            or vehicle.rp == 0
            or state["researched_rp"] == vehicle.rp
        )
        effective_rp = vehicle.rp if already_researched else state["researched_rp"]
        remaining = 0 if already_researched or state["purchased"] else vehicle.rp - effective_rp
        expected_ge = 0 if remaining <= 0 else math.ceil(remaining / database.rp_per_ge)
        expected_sl = (
            0
            if state["purchased"] or vehicle.reserve
            else round(vehicle.sl * (1 - options["sl_discount_percent"] / 100))
        )
        _require(line["total_rp"] == vehicle.rp, "datamine vehicle RP")
        _require(line["base_sl"] == vehicle.sl, "datamine vehicle SL")
        _require(line["researched_rp"] == effective_rp, "effective researched RP")
        _require(line["remaining_rp"] == remaining, "remaining RP formula")
        _require(line["ge"] == expected_ge, "per-vehicle GE formula")
        _require(line["discounted_sl"] == expected_sl, "per-vehicle SL formula")
    line_rp = sum(item["remaining_rp"] for item in expected["vehicle_cost_lines"])
    line_ge = sum(item["ge"] for item in expected["vehicle_cost_lines"])
    line_sl = sum(item["discounted_sl"] for item in expected["vehicle_cost_lines"])
    if expected["totals"] is not None:
        totals = expected["totals"]
        _require(totals["remaining_rp"] == line_rp, "total remaining RP")
        _require(totals["ge_before_owned"] == line_ge, "total GE before owned")
        _require(
            totals["ge_after_owned"] == max(line_ge - progress["owned_ge"], 0),
            "total GE after owned",
        )
        _require(totals["sl"] == line_sl, "total SL")
        convertible = progress["convertible_rp"]
        expected_shortfall = 0 if convertible is None else max(line_rp - convertible, 0)
        _require(
            totals["convertible_rp_shortfall"] == expected_shortfall,
            "convertible RP shortfall",
        )
    if expected["partial_totals"] is not None:
        partial = expected["partial_totals"]
        _require(
            partial
            == {"remaining_rp": line_rp, "ge_before_owned": line_ge, "sl": line_sl},
            "partial diagnostic sums",
        )


def execute_golden_suite(
    database: VehicleDatabase,
    payload: dict[str, Any],
) -> AccuracySuiteResult:
    validate_golden_fixture(payload, database)
    database_cache: dict[str, VehicleDatabase] = {"sample": database}
    pipeline_cache: dict[str, GraphCalculationPipeline] = {}
    cases: list[dict[str, Any]] = []
    origins: dict[str, Counter[str]] = {
        item: Counter() for item in PROVENANCE_CATEGORIES
    }
    for case in payload["cases"]:
        database_ref = case["database_ref"]
        if database_ref not in database_cache:
            database_cache[database_ref] = _database_from_payload(
                payload["syntheticDatabases"][database_ref]
            )
        pipeline = pipeline_cache.setdefault(
            database_ref,
            GraphCalculationPipeline(database_cache[database_ref]),
        )
        request = case["input"]
        result = pipeline.run(
            target_vehicle_id=request["target_vehicle_id"],
            start_vehicle_id=request["start_vehicle_id"],
            progress=_progress_from_payload(request["progress"]),
            options=_options_from_payload(request["options"]),
        )
        actual = golden_result_projection(result)
        passed = actual == canonicalize(case["expected"])
        origins[case["primary_origin"]]["passed" if passed else "failed"] += 1
        cases.append(
            {
                "caseId": case["case_id"],
                "passed": passed,
                "primaryOrigin": case["primary_origin"],
                "expected": canonicalize(case["expected"]),
                "actual": actual,
                "graphFingerprint": result.fingerprint,
            }
        )
    result_payload = [
        {"caseId": item["caseId"], "actual": item["actual"]} for item in cases
    ]
    fingerprint = stable_fingerprint(
        result_payload,
        version=GOLDEN_RESULT_FINGERPRINT_VERSION,
    )
    _require(fingerprint == payload["resultFingerprint"], "golden result fingerprint changed")
    passed_count = sum(item["passed"] for item in cases)
    by_origin = {
        origin: {
            "total": origins[origin]["passed"] + origins[origin]["failed"],
            "passed": origins[origin]["passed"],
            "failed": origins[origin]["failed"],
        }
        for origin in PROVENANCE_CATEGORIES
    }
    return AccuracySuiteResult(
        total=len(cases),
        passed=passed_count,
        failed=len(cases) - passed_count,
        results_by_origin=by_origin,
        case_results=tuple(cases),
        fingerprint_version=GOLDEN_RESULT_FINGERPRINT_VERSION,
        fingerprint=fingerprint,
        reviewed_end_to_end_references=_reviewed_e2e_count(payload),
    )


def golden_result_projection(result: Any) -> dict[str, Any]:
    resolution = result.prerequisite_resolution
    cost = result.cost_result
    active_rules = set(result.status_contract.affected_rule_ids)
    active_rules.update(item.rule_id for item in result.input_findings)
    if result.evaluation_report is not None:
        active_rules.update(
            item.rule_id
            for item in result.evaluation_report.evaluations
            if item.status.value != "not_applicable"
        )
    required = list(resolution.required_vehicle_ids) if resolution is not None else []
    rank_requirements = []
    folder_requirements = []
    unlock_requirements = []
    if resolution is not None:
        rank_requirements = [
            {
                "rank": item.rank,
                "required_count": item.required_count,
                "satisfied_count": item.satisfied_count,
                "missing_count": item.missing_count,
                "selected_vehicle_ids": list(item.selected_vehicle_ids),
            }
            for item in resolution.rank_requirements
        ]
        folder_requirements = [
            {
                "vehicle_id": item.vehicle_id,
                "folder_ids": list(item.folder_ids),
                "relationship": item.relationship,
                "status": item.status,
            }
            for item in resolution.folder_requirements
        ]
        unlock_requirements = [
            {
                "vehicle_id": item.vehicle_id,
                "tokens": list(item.tokens),
                "classification": item.classification,
                "status": item.status,
                "required_vehicle_ids": list(item.required_vehicle_ids),
            }
            for item in resolution.unlock_requirements
        ]
    lines = []
    if cost is not None:
        lines = [
            {
                "vehicle_id": item.vehicle_id,
                "total_rp": item.total_rp,
                "researched_rp": item.researched_rp,
                "remaining_rp": item.remaining_rp,
                "ge": item.ge,
                "base_sl": item.base_sl,
                "discounted_sl": item.discounted_sl,
            }
            for item in cost.vehicle_cost_lines
        ]
    totals = None
    partial_totals = None
    incomplete: list[str] = []
    if cost is not None:
        incomplete = list(cost.incomplete_reason_codes)
        if cost.cost_status.value == "complete":
            totals = {
                "remaining_rp": cost.total_remaining_rp,
                "ge_before_owned": cost.total_ge_before_owned,
                "ge_after_owned": cost.total_ge_after_owned,
                "sl": cost.total_sl,
                "convertible_rp_shortfall": cost.convertible_rp_shortfall,
            }
        elif cost.cost_status.value == "partial":
            partial_totals = {
                "remaining_rp": cost.partial_remaining_rp,
                "ge_before_owned": cost.partial_ge_before_owned,
                "sl": cost.partial_sl,
            }
    resolution_status = resolution.resolution_status.value if resolution is not None else None
    trace = _semantic_trace(
        target_vehicle_id=result.target_vehicle_id,
        start_vehicle_id=result.start_vehicle_id,
        pipeline_status=result.pipeline_status.value,
        resolution_status=resolution_status,
        required_vehicle_ids=required,
        lines=lines,
        active_rule_ids=sorted(active_rules),
    )
    return canonicalize(
        {
            "pipeline_status": result.pipeline_status.value,
            "resolution_status": resolution_status,
            "required_vehicle_ids": required,
            "rank_requirements": rank_requirements,
            "folder_requirements": folder_requirements,
            "unlock_requirements": unlock_requirements,
            "vehicle_cost_lines": lines,
            "totals": totals,
            "partial_totals": partial_totals,
            "rule_ids": sorted(active_rules),
            "incomplete_reason_codes": incomplete,
            "explanation_trace": trace,
        }
    )


def run_metamorphic_suite(database: VehicleDatabase) -> AccuracySuiteResult:
    pipeline = GraphCalculationPipeline(database)
    cases: list[dict[str, Any]] = []

    def record(property_id: str, passed: bool, evidence: dict[str, Any]) -> None:
        cases.append(
            {
                "caseId": property_id,
                "passed": bool(passed),
                "primaryOrigin": "SYNTHETIC_CONTRACT",
                "evidence": canonicalize(evidence),
                "seed": None,
            }
        )

    target = "gladiator_mk2"
    base = pipeline.run(target_vehicle_id=target)
    partial_progress = PlayerProgress(
        vehicles={target: VehicleProgress(researched_rp=1_000)}
    )
    improved = pipeline.run(target_vehicle_id=target, progress=partial_progress)
    base_cost = _complete_cost(base)
    improved_cost = _complete_cost(improved)
    record(
        "META_RP_PROGRESS_NONINCREASING_RP",
        improved_cost.total_remaining_rp <= base_cost.total_remaining_rp,
        {"before": base_cost.total_remaining_rp, "after": improved_cost.total_remaining_rp},
    )
    record(
        "META_RP_PROGRESS_NONINCREASING_GE",
        improved_cost.total_ge_before_owned <= base_cost.total_ge_before_owned,
        {"before": base_cost.total_ge_before_owned, "after": improved_cost.total_ge_before_owned},
    )

    chain_target = "us_m3a1_stuart"
    chain_base = pipeline.run(target_vehicle_id=chain_target)
    intermediate = database.get("us_m3_stuart")
    chain_owned = pipeline.run(
        target_vehicle_id=chain_target,
        progress=PlayerProgress(
            vehicles={
                intermediate.id: VehicleProgress(
                    researched_rp=intermediate.rp,
                    researched=True,
                    purchased=True,
                )
            }
        ),
    )
    before_line = _line_or_zero(_complete_cost(chain_base), intermediate.id)
    after_line = _line_or_zero(_complete_cost(chain_owned), intermediate.id)
    record(
        "META_PURCHASED_REQUIRED_VEHICLE_NONINCREASING_COST",
        all(after_line[key] <= before_line[key] for key in ("rp", "ge", "sl")),
        {"before": before_line, "after": after_line},
    )

    ge_10 = pipeline.run(target_vehicle_id=target, progress=PlayerProgress(owned_ge=10))
    ge_20 = pipeline.run(target_vehicle_id=target, progress=PlayerProgress(owned_ge=20))
    ge_10_cost = _complete_cost(ge_10)
    ge_20_cost = _complete_cost(ge_20)
    record(
        "META_OWNED_GE_NONINCREASING_REMAINDER",
        ge_20_cost.total_ge_after_owned <= ge_10_cost.total_ge_after_owned,
        {"owned10": ge_10_cost.total_ge_after_owned, "owned20": ge_20_cost.total_ge_after_owned},
    )
    record(
        "META_GE_REMAINDER_NONNEGATIVE",
        ge_20_cost.total_ge_after_owned >= 0,
        {"remainingGe": ge_20_cost.total_ge_after_owned},
    )

    enough = pipeline.run(
        target_vehicle_id=target,
        progress=PlayerProgress(convertible_rp=database.get(target).rp),
    )
    more = pipeline.run(
        target_vehicle_id=target,
        progress=PlayerProgress(convertible_rp=database.get(target).rp * 2),
    )
    less = pipeline.run(target_vehicle_id=target, progress=PlayerProgress(convertible_rp=1))
    record(
        "META_CONVERTIBLE_RP_SUFFICIENT_ZERO_SHORTFALL",
        _complete_cost(enough).convertible_rp_shortfall == 0,
        {"shortfall": _complete_cost(enough).convertible_rp_shortfall},
    )
    record(
        "META_CONVERTIBLE_RP_NONINCREASING_SHORTFALL",
        _complete_cost(more).convertible_rp_shortfall
        <= _complete_cost(less).convertible_rp_shortfall,
        {
            "lessConvertible": _complete_cost(less).convertible_rp_shortfall,
            "moreConvertible": _complete_cost(more).convertible_rp_shortfall,
        },
    )

    discount_results = {
        value: pipeline.run(
            target_vehicle_id=target,
            options=SolveOptions(sl_discount_percent=value),
        )
        for value in (0, 30, 50)
    }
    sl = {value: _complete_cost(result).total_sl for value, result in discount_results.items()}
    record("META_SL_DISCOUNT_30_NOT_ABOVE_0", sl[30] <= sl[0], sl)
    record("META_SL_DISCOUNT_50_NOT_ABOVE_30", sl[50] <= sl[30], sl)

    record(
        "META_GE_TOTAL_IS_SUM_OF_INDIVIDUAL_LINES",
        base_cost.total_ge_before_owned == sum(item.ge for item in base_cost.vehicle_cost_lines),
        {
            "total": base_cost.total_ge_before_owned,
            "lineSum": sum(item.ge for item in base_cost.vehicle_cost_lines),
        },
    )
    repeated = pipeline.run(target_vehicle_id=target)
    record(
        "META_IDENTICAL_INPUT_IDENTICAL_FINGERPRINT",
        base.fingerprint == repeated.fingerprint,
        {"first": base.fingerprint, "second": repeated.fingerprint},
    )

    ordered_a = PlayerProgress(
        vehicles={
            "gladiator_mk2": VehicleProgress(researched_rp=100),
            "fury_mk1": VehicleProgress(researched=True, purchased=True),
        }
    )
    ordered_b = PlayerProgress(
        vehicles={
            "fury_mk1": VehicleProgress(researched=True, purchased=True),
            "gladiator_mk2": VehicleProgress(researched_rp=100),
        }
    )
    order_a = pipeline.run(target_vehicle_id=target, progress=ordered_a)
    order_b = pipeline.run(target_vehicle_id=target, progress=ordered_b)
    record(
        "META_MAPPING_ORDER_IRRELEVANT",
        order_a.fingerprint == order_b.fingerprint,
        {"first": order_a.fingerprint, "second": order_b.fingerprint},
    )

    irrelevant = pipeline.run(
        target_vehicle_id=target,
        progress=PlayerProgress(
            vehicles={"us_m2a4": VehicleProgress(researched_rp=0)}
        ),
    )
    record(
        "META_IRRELEVANT_PROGRESS_SEMANTIC_RESULT_UNCHANGED",
        golden_result_projection(base) == golden_result_projection(irrelevant),
        {
            "baseProjection": golden_result_projection(base),
            "withIrrelevantProgress": golden_result_projection(irrelevant),
            "fingerprintExcludedFromAssertion": True,
        },
    )

    unresolved_blocking = [
        item.rule_id
        for item in (base.evaluation_report.evaluations if base.evaluation_report else ())
        if item.blocking and item.status.value == "unresolved"
    ]
    record(
        "META_COMPLETE_HAS_NO_UNRESOLVED_BLOCKING_RULE",
        base.pipeline_status.value == "complete" and not unresolved_blocking,
        {"unresolvedBlockingRuleIds": unresolved_blocking},
    )

    partial = pipeline.run(
        target_vehicle_id="fiat_cr42",
        options=SolveOptions(include_hidden_legacy=True),
    )
    partial_cost = partial.cost_result
    record(
        "META_PARTIAL_HAS_NO_BINDING_TOTALS",
        partial.pipeline_status.value == "partial"
        and partial_cost is not None
        and all(
            value is None
            for value in (
                partial_cost.total_remaining_rp,
                partial_cost.total_ge_before_owned,
                partial_cost.total_ge_after_owned,
                partial_cost.total_sl,
            )
        ),
        {
            "pipelineStatus": partial.pipeline_status.value,
            "totals": golden_result_projection(partial)["totals"],
        },
    )

    unavailable = pipeline.run(target_vehicle_id="fiat_cr42")
    unavailable_lines = (
        unavailable.cost_result.vehicle_cost_lines if unavailable.cost_result is not None else ()
    )
    record(
        "META_UNAVAILABLE_HAS_NO_INVENTED_COST_LINES",
        unavailable.pipeline_status.value == "blocked" and not unavailable_lines,
        {
            "pipelineStatus": unavailable.pipeline_status.value,
            "vehicleCostLineCount": len(unavailable_lines),
        },
    )

    passed = sum(item["passed"] for item in cases)
    fingerprint = stable_fingerprint(cases, version="accuracy-metamorphic-v1")
    return AccuracySuiteResult(
        total=len(cases),
        passed=passed,
        failed=len(cases) - passed,
        results_by_origin={
            "SYNTHETIC_CONTRACT": {
                "total": len(cases),
                "passed": passed,
                "failed": len(cases) - passed,
            }
        },
        case_results=tuple(cases),
        fingerprint_version="accuracy-metamorphic-v1",
        fingerprint=fingerprint,
    )


def validate_decision_register(payload: dict[str, Any]) -> None:
    _require(payload.get("schemaVersion") == 1, "decision register schema")
    decisions = payload.get("decisions")
    _require(isinstance(decisions, list), "decision list")
    ids = [item.get("decision_id") for item in decisions]
    _require(ids == list(EXPECTED_DECISION_IDS), "decision IDs and ordering")
    required = {
        "decision_id",
        "legacy_behavior",
        "graph_behavior",
        "risk",
        "recommendation",
        "alternatives",
        "required_product_owner_decision",
        "status",
        "release_blocking",
        "evidence",
    }
    for item in decisions:
        _require(required == set(item), f"decision contract {item.get('decision_id')}")
        _require(
            item["status"] in {"proposed", "accepted", "rejected", "deferred"},
            "decision status",
        )
        _require(isinstance(item["release_blocking"], bool), "release blocking flag")
        _require(bool(item["alternatives"]), "decision alternatives")
        _require(bool(item["evidence"]), "decision evidence")
    _reject_environment_fields(payload)


def validate_partial_dossier(payload: dict[str, Any], database: VehicleDatabase) -> None:
    _require(payload.get("schemaVersion") == 1, "partial dossier schema")
    _require(payload.get("gameVersion") == database.game_version, "partial dossier game version")
    cases = payload.get("cases")
    _require(isinstance(cases, list) and len(cases) == 14, "exactly 14 partial cases")
    ids = [item.get("target_vehicle_id") for item in cases]
    _require(ids == list(EXPECTED_PARTIAL_TARGET_IDS), "partial target IDs and ordering")
    for item in cases:
        vehicle = database.get(item["target_vehicle_id"])
        _require(item["folder_id"] == vehicle.group, "partial folder")
        _require(item["members"] == database.raw_groups[vehicle.group], "partial folder members")
        _require(item["group_index"] == vehicle.group_index, "partial groupIndex")
        _require(item["hidden_research"] == vehicle.hidden_research, "partial hiddenResearch")
        _require(item["predecessor"] == database.predecessors[vehicle.id], "partial predecessor")
        _require(item["rank"] == vehicle.rank, "partial rank")
        _require(item["known_costs"] == {"rp": vehicle.rp, "sl": vehicle.sl}, "partial costs")
        _require(bool(item["missing_source_data"]), "missing source data")
        _require(bool(item["why_not_complete"]), "partial rationale")
        _require(bool(item["required_evidence"]), "required evidence")
        _require(item["heuristic_applied"] is False, "no folder heuristic")
    grouped_ids = sorted(
        target
        for group in payload.get("causeGroups", [])
        for target in group.get("target_vehicle_ids", [])
    )
    _require(grouped_ids == sorted(EXPECTED_PARTIAL_TARGET_IDS), "partial cause grouping")
    _reject_environment_fields(payload)


def validate_rollback_plan(payload: dict[str, Any]) -> None:
    _require(payload.get("schemaVersion") == 1, "rollback schema")
    _require(payload.get("status") == "design_only", "rollback remains design only")
    _require(payload.get("productiveSwitchImplemented") is False, "no productive switch")
    _require(payload.get("dataMigrationRequired") is False, "no data migration")
    _require(payload.get("telemetryEnabled") is False, "no telemetry")
    for field in (
        "featureFlag",
        "legacyFallback",
        "shadowComparison",
        "errorHandling",
        "graphPathDisable",
        "localReports",
        "telemetryPolicy",
    ):
        _require(bool(payload.get(field)), f"rollback field {field}")
    _reject_environment_fields(payload)


def build_confidence_report(
    *,
    database: VehicleDatabase,
    baseline: dict[str, Any],
    golden: AccuracySuiteResult,
    metamorphic: AccuracySuiteResult,
    shadow_report: dict[str, Any],
    browser_report: dict[str, Any],
    decision_register: dict[str, Any],
    partial_dossier: dict[str, Any],
    rollback_plan: dict[str, Any],
) -> dict[str, Any]:
    comparisons = shadow_report["comparisonCounts"]
    options_coverage = shadow_report["optionsCoverage"]["coverage"]
    input_coverage = shadow_report["inputValidationCoverage"]["coverage"]
    decisions = decision_register["decisions"]
    open_decisions = [item["decision_id"] for item in decisions if item["status"] != "accepted"]
    release_blocking_decisions = [
        item["decision_id"] for item in decisions if item["release_blocking"]
    ]
    e2e_count = golden.reviewed_end_to_end_references
    evidence = {
        "zeroMismatches": comparisons.get("mismatch", 0) == 0,
        "zeroInternalErrors": comparisons.get("internal_error", 0) == 0,
        "goldenSuitePassed": golden.failed == 0,
        "metamorphicSuitePassed": metamorphic.failed == 0,
        "optionsCoverageComplete": options_coverage == 100.0,
        "inputCoverageComplete": input_coverage == 100.0,
        "contractDecisionsAcceptedOrReleaseBlocking": all(
            item["status"] == "accepted" or item["release_blocking"] for item in decisions
        ),
        "browserParityDocumented": browser_report.get("browserParityStatus")
        in {"fixture_validation_only", "runtime_parity"},
        "browserCanonicalFixturePassed": (
            browser_report.get("failed") == 0
            and browser_report.get("resultFingerprint") == golden.fingerprint
        ),
        "rollbackPlanPresent": rollback_plan.get("status") == "design_only",
        "realEndToEndReferencesReviewed": e2e_count >= 9,
        "productiveResultSource": "legacy",
    }
    release_candidate = all(evidence[key] for key in evidence if key != "productiveResultSource")
    readiness = {
        "ready_for_experimental_use": (
            evidence["zeroMismatches"]
            and evidence["zeroInternalErrors"]
            and evidence["goldenSuitePassed"]
            and evidence["metamorphicSuitePassed"]
            and evidence["optionsCoverageComplete"]
            and evidence["inputCoverageComplete"]
        ),
        "experimental_use_scope": "shadow_mode_only",
        "ready_for_release_candidate": release_candidate,
        "release_candidate_scope": "shadow_release_candidate_only",
        "ready_for_default_use": False,
        "blockers": {
            "releaseCandidate": [] if release_candidate else sorted(
                key for key, value in evidence.items() if isinstance(value, bool) and not value
            ),
            "defaultUse": sorted(
                {
                    "BROWSER_GRAPH_RUNTIME_PARITY_MISSING",
                    "CONTRACT_DECISIONS_OPEN",
                    "FOLDER_PARTIAL_CASES_OPEN",
                    "LEGACY_RANK_COMPATIBILITY_NOT_RETIRED",
                    "PRODUCTIVE_SWITCH_NOT_REVIEWED",
                }
            ),
        },
        "warnings": sorted(
            {
                "Browser checks canonical fixtures only; it does not execute the graph runtime.",
                "Fourteen special targets remain partial because folder evidence is insufficient.",
                "Open contract decisions remain explicit release blockers, not successful matches.",
            }
        ),
        "evidence": evidence,
    }
    preliminary = {
        "schemaVersion": CONFIDENCE_REPORT_SCHEMA_VERSION,
        "reportVersion": CONFIDENCE_SUITE_VERSION,
        "gameVersion": database.game_version,
        "baseline": {
            "version": baseline["baselineVersion"],
            "fingerprint": baseline["fingerprint"],
        },
        "goldenCases": golden.to_dict(),
        "metamorphicTests": metamorphic.to_dict(),
        "crossPython": {
            "requiredVersions": ["3.10", "3.12", "3.13"],
            "canonicalFixtureFingerprint": baseline["fingerprints"].get(
                "goldenFixture",
                "validated-from-immutable-fixture",
            ),
            "canonicalResultFingerprint": golden.fingerprint,
            "status": "contract_enforced_by_ci_matrix",
            "excludedFields": list(PLATFORM_EXCLUDED_FIELDS),
        },
        "browserParity": canonicalize(browser_report),
        "pipelineComparisons": {
            "scenarioCount": shadow_report["scenarioCount"],
            "comparisonCounts": canonicalize(comparisons),
            "optionsCoverage": options_coverage,
            "inputValidationCoverage": input_coverage,
            "shadowFingerprint": shadow_report["fingerprint"],
        },
        "contractDecisions": {
            "total": len(decisions),
            "open": open_decisions,
            "releaseBlocking": release_blocking_decisions,
        },
        "specialCases": {
            "total": shadow_report["specialCaseStatistics"]["caseCount"],
            "complete": shadow_report["specialCaseStatistics"]
            ["pipelineStatusDistribution"]["complete"],
            "partial": shadow_report["specialCaseStatistics"]
            ["pipelineStatusDistribution"]["partial"],
            "dossierCases": len(partial_dossier["cases"]),
        },
        "readiness": readiness,
        "knownLimits": [
            "Browser graph runtime parity is not implemented; fixture validation is explicit.",
            "Fourteen hidden folder targets remain partial without acquisition-semantics evidence.",
            (
                "LegacyRankCompatibilityStrategy remains comparison-only and is not "
                "optimizer semantics."
            ),
            "Partial results do not expose binding totals and do not apply owned GE.",
            "No productive solver switch, telemetry, GUI, or browser-runtime change is included.",
        ],
        "scorePolicy": "No numeric confidence score is defined.",
        "fingerprintVersion": CONFIDENCE_REPORT_FINGERPRINT_VERSION,
    }
    fingerprint = stable_fingerprint(preliminary, version=CONFIDENCE_REPORT_FINGERPRINT_VERSION)
    return {**preliminary, "fingerprint": fingerprint}


def write_confidence_reports(payload: dict[str, Any], output: str | Path) -> tuple[Path, Path]:
    output_dir = Path(output)
    output_dir.mkdir(parents=True, exist_ok=True)
    game_version = payload["gameVersion"]
    json_path = output_dir / f"Accuracy_Confidence_{game_version}.json"
    text_path = output_dir / f"Accuracy_Confidence_{game_version}.txt"
    json_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    text_path.write_text(render_confidence_text(payload), encoding="utf-8")
    return json_path, text_path


def render_confidence_text(payload: dict[str, Any]) -> str:
    golden = payload["goldenCases"]
    metamorphic = payload["metamorphicTests"]
    comparisons = payload["pipelineComparisons"]["comparisonCounts"]
    readiness = payload["readiness"]
    lines = [
        "Accuracy confidence validation: "
        + ("passed" if golden["failed"] == 0 and metamorphic["failed"] == 0 else "failed"),
        f"Game version: {payload['gameVersion']}",
        f"Golden cases: {golden['passed']}/{golden['total']}",
        f"Metamorphic tests: {metamorphic['passed']}/{metamorphic['total']}",
        "Python versions: " + ", ".join(payload["crossPython"]["requiredVersions"]),
        f"Browser parity: {payload['browserParity']['browserParityStatus']}",
        f"Pipeline scenarios: {payload['pipelineComparisons']['scenarioCount']}",
        f"Mismatches: {comparisons['mismatch']}",
        f"Internal errors: {comparisons['internal_error']}",
        f"Open contract decisions: {len(payload['contractDecisions']['open'])}",
        f"Complete special cases: {payload['specialCases']['complete']}",
        f"Partial special cases: {payload['specialCases']['partial']}",
        "Ready for experimental use: "
        + ("yes (Shadow Mode only)" if readiness["ready_for_experimental_use"] else "no"),
        "Ready for release candidate: "
        + ("yes (Shadow RC only)" if readiness["ready_for_release_candidate"] else "no"),
        "Ready for default use: no",
        "Confidence score: not defined",
        f"Fingerprint: {payload['fingerprint']}",
        "",
    ]
    return "\n".join(lines)


def _reviewed_e2e_count(golden_payload: dict[str, Any]) -> int:
    tags = {
        tag
        for case in golden_payload["cases"]
        if case["review_status"] == "reviewed"
        for tag in case["tags"]
        if tag.startswith("e2e:")
    }
    return len(tags & set(REQUIRED_E2E_TAGS))


def _progress_from_payload(payload: dict[str, Any]) -> PlayerProgress:
    _require(
        set(payload) == {"vehicles", "convertible_rp", "owned_ge", "fulfilled_unlocks"},
        "canonical progress input",
    )
    vehicles = {
        vehicle_id: VehicleProgress(
            researched_rp=state["researched_rp"],
            researched=state["researched"],
            purchased=state["purchased"],
        )
        for vehicle_id, state in payload["vehicles"].items()
    }
    return PlayerProgress(
        vehicles=vehicles,
        convertible_rp=payload["convertible_rp"],
        owned_ge=payload["owned_ge"],
        fulfilled_unlocks=frozenset(payload["fulfilled_unlocks"]),
    )


def _options_from_payload(payload: dict[str, Any]) -> SolveOptions:
    _require(
        set(payload)
        == {
            "optimize_for",
            "include_start_vehicle",
            "include_hidden_legacy",
            "assume_external_unlocks",
            "sl_discount_percent",
        },
        "canonical options input",
    )
    return SolveOptions(
        optimize_for=payload["optimize_for"],
        include_start_vehicle=payload["include_start_vehicle"],
        include_hidden_legacy=payload["include_hidden_legacy"],
        assume_external_unlocks=payload["assume_external_unlocks"],
        sl_discount_percent=payload["sl_discount_percent"],
    )


def _database_from_payload(payload: dict[str, Any]) -> VehicleDatabase:
    vehicles: dict[str, Vehicle] = {}
    for item in payload["vehicles"]:
        vehicle = Vehicle(
            id=item["id"],
            name=item["name"],
            country_id=item["countryId"],
            branch_id=item["branchId"],
            rank=item["rank"],
            rp=item["rp"],
            sl=item["sl"],
            reserve=item.get("reserve", False),
            premium=item.get("premium", False),
            special=item.get("special", False),
            hidden_research=item.get("hiddenResearch", False),
            req_unlock=item.get("reqUnlock", ""),
            group=item.get("group"),
            group_index=item.get("groupIndex", 0),
            column=item.get("column", 0),
            order=item.get("order", 0),
        )
        vehicles[vehicle.id] = vehicle
    predecessors = {
        vehicle_id: payload.get("predecessors", {}).get(vehicle_id)
        for vehicle_id in vehicles
    }
    groups = deepcopy(payload.get("groups", {}))
    return VehicleDatabase(
        game_version=payload["gameVersion"],
        rp_per_ge=payload["economy"]["rpPerGE"],
        vehicles=vehicles,
        predecessors=predecessors,
        groups=groups,
        raw_groups=groups,
        rank_unlock=deepcopy(payload.get("rankUnlock", {})),
    )


def _semantic_trace(
    *,
    target_vehicle_id: str,
    start_vehicle_id: str | None,
    pipeline_status: str,
    resolution_status: str | None,
    required_vehicle_ids: Iterable[str],
    lines: Iterable[dict[str, Any]],
    active_rule_ids: Iterable[str],
) -> list[str]:
    trace = [
        f"target={target_vehicle_id}",
        f"start={start_vehicle_id or 'none'}",
        f"resolution={resolution_status or 'none'}",
    ]
    trace.extend(f"required={item}" for item in required_vehicle_ids)
    trace.extend(
        (
            f"cost={item['vehicle_id']}:rp={item['remaining_rp']}:"
            f"ge={item['ge']}:sl={item['discounted_sl']}"
        )
        for item in lines
    )
    trace.extend(f"rule={item}" for item in active_rule_ids)
    trace.append(f"pipeline={pipeline_status}")
    return trace


def _complete_cost(result: Any) -> Any:
    if result.cost_result is None or result.cost_result.cost_status.value != "complete":
        raise AccuracyContractError(
            f"Metamorphic reference {result.target_vehicle_id} did not produce complete costs."
        )
    return result.cost_result


def _line_or_zero(cost: Any, vehicle_id: str) -> dict[str, int]:
    for line in cost.vehicle_cost_lines:
        if line.vehicle_id == vehicle_id:
            return {"rp": line.remaining_rp, "ge": line.ge, "sl": line.discounted_sl}
    return {"rp": 0, "ge": 0, "sl": 0}


def _reject_environment_fields(value: Any, path: str = "$") -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            _require(key not in PLATFORM_EXCLUDED_FIELDS, f"environment field {path}.{key}")
            _reject_environment_fields(item, f"{path}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _reject_environment_fields(item, f"{path}[{index}]")


def _require(condition: bool, label: str) -> None:
    if not condition:
        raise AccuracyContractError(f"Accuracy contract violation: {label}.")
