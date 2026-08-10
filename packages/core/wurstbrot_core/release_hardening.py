from __future__ import annotations

import json
import math
import time
from collections import Counter
from copy import deepcopy
from pathlib import Path
from typing import Any, Iterable, Mapping

from .accuracy_confidence import (
    EXPECTED_PARTIAL_TARGET_IDS,
    execute_core_reference_suite,
    execute_golden_suite,
    run_metamorphic_suite,
)
from .database import VehicleDatabase
from .engine_execution import (
    CalculationEngine,
    CalculationStatus,
    EngineFeatureFlags,
    ExecutionMode,
    ResultSource,
    serialize_solve_result,
)
from .graph_pipeline import PipelineStatus, canonicalize, stable_fingerprint
from .graph_shadow import build_special_cases
from .models import PlayerProgress, SolveOptions, VehicleProgress


RELEASE_HARDENING_SCHEMA_VERSION = 1
RELEASE_HARDENING_VERSION = "1.0.0-accuracy10"
DIRECT_FIXTURE_FINGERPRINT_VERSION = "accuracy10-direct-fixture-v1"
DIRECT_RESULT_FINGERPRINT_VERSION = "accuracy10-direct-results-v1"
RELEASE_REPORT_FINGERPRINT_VERSION = "accuracy10-release-hardening-report-v1"

EXPECTED_EXECUTION_MODES = ("legacy", "shadow", "graph_experimental")
EXPECTED_TREE_COUNT = 44
MINIMUM_REAL_ACCEPTANCE_CASES = 50
EXPECTED_PARTIAL_CASES = 14
PERFORMANCE_SMOKE_LIMIT_SECONDS = 30.0

REQUIRED_COVERAGE = (
    "all_nations",
    "all_vehicle_types",
    "all_research_trees",
    "path_short",
    "path_medium",
    "path_long",
    "root_to_mid",
    "mid_to_late",
    "rank_transition",
    "target_progress",
    "intermediate_progress",
    "purchased_vehicle",
    "folder",
    "req_unlock",
    "hidden_research",
    "reserve",
    "zero_rp",
    "zero_sl",
    "owned_ge",
    "convertible_rp",
    "sl_discount_0",
    "sl_discount_30",
    "sl_discount_50",
)


class ReleaseHardeningError(ValueError):
    pass


def load_release_fixture(path: str | Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ReleaseHardeningError("Release-hardening fixture must be a JSON object.")
    return payload


def direct_fixture_fingerprint(payload: Mapping[str, Any]) -> str:
    content = {
        key: value
        for key, value in payload.items()
        if key not in {"fixtureFingerprint", "resultFingerprint"}
    }
    return stable_fingerprint(content, version=DIRECT_FIXTURE_FINGERPRINT_VERSION)


def validate_release_fixture(
    payload: dict[str, Any],
    database: VehicleDatabase,
    *,
    validate_result_fingerprint: bool = True,
) -> None:
    _require(payload.get("schemaVersion") == RELEASE_HARDENING_SCHEMA_VERSION, "schema")
    _require(payload.get("suiteVersion") == RELEASE_HARDENING_VERSION, "suite version")
    _require(payload.get("gameVersion") == database.game_version, "game version")
    _require(payload.get("generationPolicy") == "manual_review_only", "manual review policy")
    _require(payload.get("immutable") is True, "immutable fixture")
    _require(payload.get("automaticOverwriteSupported") is False, "no overwrite path")
    _require(payload.get("rpPerGE") == database.rp_per_ge, "rpPerGE")
    _require(
        payload.get("fixtureFingerprintVersion") == DIRECT_FIXTURE_FINGERPRINT_VERSION,
        "fixture fingerprint version",
    )
    _require(
        payload.get("resultFingerprintVersion") == DIRECT_RESULT_FINGERPRINT_VERSION,
        "result fingerprint version",
    )
    _require(
        payload.get("fixtureFingerprint") == direct_fixture_fingerprint(payload),
        "fixture fingerprint",
    )
    if validate_result_fingerprint:
        _require(
            isinstance(payload.get("resultFingerprint"), str)
            and payload["resultFingerprint"].startswith(
                f"{DIRECT_RESULT_FINGERPRINT_VERSION}:"
            ),
            "result fingerprint",
        )

    profiles = payload.get("profiles")
    cases = payload.get("cases")
    _require(isinstance(profiles, dict) and profiles, "profiles")
    _require(isinstance(cases, list) and len(cases) == 44, "44 direct cases")
    _require(payload.get("caseCount") == len(cases), "case count")
    case_ids = [item.get("caseId") for item in cases if isinstance(item, dict)]
    _require(len(case_ids) == len(cases), "case objects")
    _require(case_ids == sorted(case_ids), "deterministic case ordering")
    _require(len(case_ids) == len(set(case_ids)), "unique case IDs")
    _require(
        payload.get("expectedValueSources")
        == ["DATAMINE_DIRECT", "FORMULA_DERIVED", "MANUALLY_REVIEWED"],
        "independent expected-value sources",
    )

    observed_trees: set[tuple[str, str]] = set()
    expected_trees = {
        (vehicle.country_id, vehicle.branch_id)
        for vehicle in database.vehicles.values()
    }
    for case in cases:
        _require(set(case) == {
            "caseId",
            "countryId",
            "vehicleType",
            "startVehicleId",
            "targetVehicleId",
            "profile",
            "expectedRequiredVehicleIds",
            "tags",
        }, f"canonical fields for {case.get('caseId')}")
        start = database.get(case["startVehicleId"])
        target = database.get(case["targetVehicleId"])
        tree = (case["countryId"], case["vehicleType"])
        _require((start.country_id, start.branch_id) == tree, "start tree")
        _require((target.country_id, target.branch_id) == tree, "target tree")
        _require(database.predecessors[target.id] == start.id, "direct predecessor")
        _require(start.rank == target.rank, "same-rank direct oracle")
        _require(not target.hidden_research, "visible target")
        _require(not target.req_unlock, "target without unlock ambiguity")
        _require(target.group is None, "target without folder ambiguity")
        _require(case["profile"] in profiles, "known profile")
        include_start = bool(profiles[case["profile"]].get("includeStartVehicle", False))
        expected_path = [start.id, target.id] if include_start else [target.id]
        _require(case["expectedRequiredVehicleIds"] == expected_path, "static path oracle")
        _require("direct_predecessor" in case["tags"], "direct-path tag")
        if case["caseId"].startswith("tree:"):
            observed_trees.add(tree)
    _require(len(expected_trees) == EXPECTED_TREE_COUNT, "expected research tree count")
    _require(observed_trees == expected_trees, "one direct reference per research tree")
    _reject_environment_fields(payload)


def execute_direct_acceptance(
    database: VehicleDatabase,
    payload: dict[str, Any],
    *,
    validate_result_fingerprint: bool = True,
) -> dict[str, Any]:
    validate_release_fixture(
        payload,
        database,
        validate_result_fingerprint=validate_result_fingerprint,
    )
    engine = CalculationEngine(
        database,
        feature_flags=EngineFeatureFlags.explicit_graph_experimental(),
    )
    started = time.perf_counter()
    results: list[dict[str, Any]] = []
    mode_counts: dict[str, Counter[str]] = {
        mode: Counter() for mode in EXPECTED_EXECUTION_MODES
    }
    for case in payload["cases"]:
        progress, options = _direct_request(database, payload, case)
        expected = _direct_expected(database, payload, case)
        mode_results: dict[str, dict[str, Any]] = {}
        for mode in ExecutionMode:
            result = engine.calculate(
                target_vehicle_id=case["targetVehicleId"],
                start_vehicle_id=case["startVehicleId"],
                progress=progress,
                options=options,
                mode=mode,
            )
            actual = _user_projection(result.result)
            passed = actual == expected
            if mode is ExecutionMode.LEGACY:
                passed = passed and result.result_source is ResultSource.LEGACY
                passed = passed and result.graph_status is None
            elif mode is ExecutionMode.SHADOW:
                passed = passed and result.result_source is ResultSource.LEGACY
                passed = passed and result.comparison_status is not None
                passed = passed and result.comparison_status.value == "exact_match"
            else:
                passed = passed and result.result_source is ResultSource.GRAPH
                passed = passed and result.graph_status is PipelineStatus.COMPLETE
                passed = passed and result.comparison_status is not None
                passed = passed and result.comparison_status.value == "exact_match"
                passed = passed and not result.fallback_applied
            mode_counts[mode.value]["passed" if passed else "failed"] += 1
            mode_results[mode.value] = {
                "passed": passed,
                "resultSource": (
                    result.result_source.value if result.result_source is not None else None
                ),
                "calculationStatus": result.calculation_status.value,
                "pipelineStatus": (
                    result.graph_status.value if result.graph_status is not None else None
                ),
                "comparisonStatus": (
                    result.comparison_status.value
                    if result.comparison_status is not None
                    else None
                ),
                "fallbackUsed": result.fallback_applied,
                "fingerprint": result.fingerprint,
            }
        results.append(
            {
                "caseId": case["caseId"],
                "startVehicleId": case["startVehicleId"],
                "targetVehicleId": case["targetVehicleId"],
                "expected": expected,
                "modes": mode_results,
                "passed": all(item["passed"] for item in mode_results.values()),
            }
        )
    elapsed = time.perf_counter() - started
    fingerprint_payload = [
        {
            "caseId": item["caseId"],
            "expected": item["expected"],
            "modes": item["modes"],
        }
        for item in results
    ]
    fingerprint = stable_fingerprint(
        fingerprint_payload,
        version=DIRECT_RESULT_FINGERPRINT_VERSION,
    )
    if validate_result_fingerprint:
        _require(fingerprint == payload["resultFingerprint"], "direct result fingerprint")
    passed_count = sum(item["passed"] for item in results)
    return {
        "total": len(results),
        "passed": passed_count,
        "failed": len(results) - passed_count,
        "modeCounts": {
            mode: {
                "passed": counts["passed"],
                "failed": counts["failed"],
            }
            for mode, counts in sorted(mode_counts.items())
        },
        "caseResults": results,
        "fingerprintVersion": DIRECT_RESULT_FINGERPRINT_VERSION,
        "fingerprint": fingerprint,
        "performanceSmoke": {
            "caseExecutions": len(results) * len(EXPECTED_EXECUTION_MODES),
            "limitSeconds": PERFORMANCE_SMOKE_LIMIT_SECONDS,
            "observedSeconds": round(elapsed, 6),
            "passed": elapsed <= PERFORMANCE_SMOKE_LIMIT_SECONDS,
            "benchmark": False,
            "fingerprintExcludedFields": ["observedSeconds"],
        },
    }


def run_boundary_matrix(database: VehicleDatabase) -> dict[str, Any]:
    start = "germ_pzkpfw_35t"
    target = "germ_pzkpfw_38t_ausf_A"
    target_rp = database.get(target).rp
    graph_engine = CalculationEngine(
        database,
        feature_flags=EngineFeatureFlags.explicit_graph_experimental(),
    )
    invalid_cases = _invalid_boundary_cases(start, target, target_rp)
    invalid_results: list[dict[str, Any]] = []
    for case_id, request in invalid_cases:
        result = graph_engine.calculate(
            target_vehicle_id=request["target"],
            start_vehicle_id=request["start"],
            progress=request["progress"],
            options=request["options"],
            mode=ExecutionMode.GRAPH_EXPERIMENTAL,
        )
        legacy_rejected = False
        try:
            graph_engine.calculate(
                target_vehicle_id=request["target"],
                start_vehicle_id=request["start"],
                progress=request["progress"],
                options=request["options"],
                mode=ExecutionMode.LEGACY,
            )
        except (KeyError, TypeError, ValueError):
            legacy_rejected = True
        documented_contract_difference = (
            case_id == "invalid:empty-start" and not legacy_rejected
        )
        passed = (
            result.calculation_status is CalculationStatus.UNAVAILABLE
            and result.result is None
            and result.result_source is None
            and not result.fallback_applied
            and (legacy_rejected or documented_contract_difference)
        )
        invalid_results.append(
            {
                "caseId": case_id,
                "passed": passed,
                "legacyRejected": legacy_rejected,
                "documentedContractDifference": documented_contract_difference,
                "contractNote": (
                    "Legacy treats an empty optional start as absent; Graph rejects it. "
                    "Graph Experimental exposes the difference without fallback."
                    if documented_contract_difference
                    else None
                ),
                "calculationStatus": result.calculation_status.value,
                "pipelineStatus": (
                    result.graph_status.value if result.graph_status is not None else None
                ),
                "comparisonStatus": (
                    result.comparison_status.value
                    if result.comparison_status is not None
                    else None
                ),
                "fallbackUsed": result.fallback_applied,
                "resultSource": None,
            }
        )

    valid_results: list[dict[str, Any]] = []
    for case_id, progress, options in _valid_boundary_cases(target, target_rp):
        projections = []
        sources = []
        for mode in ExecutionMode:
            result = graph_engine.calculate(
                target_vehicle_id=target,
                start_vehicle_id=start,
                progress=progress,
                options=options,
                mode=mode,
            )
            projections.append(_user_projection(result.result))
            sources.append(
                result.result_source.value if result.result_source is not None else None
            )
        projection = projections[0]
        numeric_values = _all_numeric_values(projection)
        passed = (
            projections[0] == projections[1] == projections[2]
            and sources == ["legacy", "legacy", "graph"]
            and all(value >= 0 for value in numeric_values)
        )
        valid_results.append(
            {
                "caseId": case_id,
                "passed": passed,
                "resultSources": sources,
                "projection": projection,
            }
        )

    all_results = invalid_results + valid_results
    fingerprint = stable_fingerprint(all_results, version="accuracy10-boundary-v1")
    passed_count = sum(item["passed"] for item in all_results)
    return {
        "total": len(all_results),
        "passed": passed_count,
        "failed": len(all_results) - passed_count,
        "invalidCases": invalid_results,
        "validBoundaryCases": valid_results,
        "randomized": False,
        "seed": None,
        "fingerprintVersion": "accuracy10-boundary-v1",
        "fingerprint": fingerprint,
    }


def run_partial_case_gate(database: VehicleDatabase, dossier: dict[str, Any]) -> dict[str, Any]:
    dossier_targets = tuple(sorted(item["target_vehicle_id"] for item in dossier["cases"]))
    _require(dossier.get("caseCount") == EXPECTED_PARTIAL_CASES, "dossier case count")
    _require(dossier_targets == EXPECTED_PARTIAL_TARGET_IDS, "dossier partial targets")
    _require(
        all(item.get("heuristic_applied") is False for item in dossier["cases"]),
        "no hidden-folder heuristic",
    )
    engine = CalculationEngine(
        database,
        feature_flags=EngineFeatureFlags.explicit_graph_experimental(),
    )
    rows: list[dict[str, Any]] = []
    for case in build_special_cases(database):
        result = engine.calculate(
            target_vehicle_id=case.target_vehicle_id,
            start_vehicle_id=case.start_vehicle_id,
            progress=case.progress,
            options=case.options,
            mode=ExecutionMode.GRAPH_EXPERIMENTAL,
        )
        if case.target_vehicle_id not in dossier_targets:
            continue
        passed = (
            result.graph_status is PipelineStatus.PARTIAL
            and result.result_source is ResultSource.LEGACY
            and result.fallback_applied
            and result.fallback_reason is not None
            and result.fallback_reason.value == "graph_partial"
        )
        rows.append(
            {
                "targetVehicleId": case.target_vehicle_id,
                "passed": passed,
                "pipelineStatus": result.graph_status.value,
                "resultSource": result.result_source.value,
                "fallbackUsed": result.fallback_applied,
                "fallbackReason": result.fallback_reason.value,
            }
        )
    rows.sort(key=lambda item: item["targetVehicleId"])
    _require(tuple(item["targetVehicleId"] for item in rows) == dossier_targets, "14 rows")
    passed_count = sum(item["passed"] for item in rows)
    return {
        "total": len(rows),
        "passed": passed_count,
        "failed": len(rows) - passed_count,
        "expectedStatus": "partial",
        "heuristicsIntroduced": False,
        "cases": rows,
        "fingerprint": stable_fingerprint(rows, version="accuracy10-partial-gate-v1"),
    }


def build_release_hardening_report(
    database: VehicleDatabase,
    direct_fixture: dict[str, Any],
    golden_fixture: dict[str, Any],
    core_fixture: dict[str, Any],
    partial_dossier: dict[str, Any],
    *,
    gate_evidence: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    direct = execute_direct_acceptance(database, direct_fixture)
    golden = execute_golden_suite(database, golden_fixture)
    core = execute_core_reference_suite(database, core_fixture)
    metamorphic = run_metamorphic_suite(database)
    boundary = run_boundary_matrix(database)
    partial = run_partial_case_gate(database, partial_dossier)

    golden_e2e_ids = {
        case["case_id"]
        for case in golden_fixture["cases"]
        if case["input"]["start_vehicle_id"] is not None
        and any(tag.startswith("e2e:") for tag in case["tags"])
    }
    golden_passed_ids = {
        item["caseId"] for item in golden.case_results if item["passed"]
    }
    real_pairs = {
        (item["startVehicleId"], item["targetVehicleId"])
        for item in direct_fixture["cases"]
    }
    real_pairs.update(
        (case["input"]["start_vehicle_id"], case["input"]["target_vehicle_id"])
        for case in golden_fixture["cases"]
        if case["case_id"] in golden_e2e_ids
    )
    real_pairs.update(
        (case["input"]["start_vehicle_id"], case["input"]["target_vehicle_id"])
        for case in core_fixture["cases"]
    )
    real_total = direct["total"] + len(golden_e2e_ids) + core.total
    real_passed = (
        direct["passed"] + len(golden_e2e_ids & golden_passed_ids) + core.passed
    )
    _require(real_total >= MINIMUM_REAL_ACCEPTANCE_CASES, "at least 50 real A-to-B cases")
    _require(len(real_pairs) == real_total, "independent unique A-to-B pairs")

    coverage = _coverage_evidence(direct_fixture, golden_fixture, core_fixture)
    _require(set(coverage) == set(REQUIRED_COVERAGE), "coverage registry")
    _require(all(item["covered"] for item in coverage.values()), "required coverage")

    evidence = dict(gate_evidence or {})
    mismatches = int(evidence.get("mismatches", 0))
    internal_errors = int(evidence.get("internalErrors", 0))
    contract_decisions_open = int(evidence.get("contractDecisionsOpen", 0))
    cross_python_passed = bool(evidence.get("crossPythonPassed", False))
    browser_legacy_passed = bool(evidence.get("browserLegacyPassed", False))
    health_errors = int(evidence.get("healthErrors", 0))
    python_regression_passed = bool(evidence.get("pythonRegressionPassed", False))
    python_regression_cases = int(evidence.get("pythonRegressionCases", 0))
    graph_mirror_passed = bool(evidence.get("graphMirrorPassed", False))
    graph_mirror_cases = int(evidence.get("graphMirrorCases", 0))
    browser_regression_passed = bool(evidence.get("browserRegressionPassed", False))
    browser_regression_cases = int(evidence.get("browserRegressionCases", 0))
    validator_coverage = float(evidence.get("validatorCoverage", 0.0))
    validator_implemented = int(evidence.get("validatorImplementedRules", 0))
    validator_tested = int(evidence.get("validatorTestedRules", 0))
    blockers: list[str] = []
    if direct["failed"]:
        blockers.append("direct_acceptance_failed")
    if real_passed != real_total:
        blockers.append("real_acceptance_failed")
    if golden.failed or core.failed or metamorphic.failed:
        blockers.append("independent_reference_failed")
    if boundary["failed"]:
        blockers.append("boundary_matrix_failed")
    if partial["failed"] or partial["total"] != EXPECTED_PARTIAL_CASES:
        blockers.append("partial_contract_changed")
    if mismatches:
        blockers.append("mismatch_detected")
    if internal_errors:
        blockers.append("internal_error_detected")
    if contract_decisions_open:
        blockers.append("contract_decision_open")
    if health_errors:
        blockers.append("health_error")
    if not python_regression_passed or python_regression_cases != 1_977:
        blockers.append("python_regression_failed")
    if not graph_mirror_passed or graph_mirror_cases != 1_977:
        blockers.append("graph_mirror_failed")
    if not browser_regression_passed or browser_regression_cases != 1_977:
        blockers.append("browser_regression_failed")
    if (
        validator_coverage != 100.0
        or validator_implemented == 0
        or validator_implemented != validator_tested
    ):
        blockers.append("validator_coverage_incomplete")
    if not cross_python_passed:
        blockers.append("cross_python_evidence_missing")
    if not browser_legacy_passed:
        blockers.append("browser_legacy_evidence_missing")
    if not direct["performanceSmoke"]["passed"]:
        blockers.append("performance_smoke_failed")

    warnings = [
        "14 hidden-folder cases remain intentionally partial pending authoritative evidence.",
        "Browser remains Legacy-only; no browser Graph runtime exists.",
        "Graph Experimental remains opt-in and is not recommended as the default source.",
    ]
    ready = not blockers
    report = {
        "schemaVersion": RELEASE_HARDENING_SCHEMA_VERSION,
        "reportVersion": RELEASE_HARDENING_VERSION,
        "gameVersion": database.game_version,
        "scope": "release_hardening_only",
        "executionModes": list(EXPECTED_EXECUTION_MODES),
        "defaultExecutionMode": "legacy",
        "directAcceptance": direct,
        "realAcceptance": {
            "total": real_total,
            "passed": real_passed,
            "failed": real_total - real_passed,
            "uniqueAtoBPairs": len(real_pairs),
            "sources": {
                "accuracy10DirectDatamineFormula": direct["total"],
                "existingReviewedGoldenE2E": len(golden_e2e_ids),
                "accuracy9CoreReferences": core.total,
            },
            "legacyUsedAsExpectedTruth": False,
        },
        "coverage": coverage,
        "golden": {"total": golden.total, "passed": golden.passed, "failed": golden.failed},
        "coreReferences": {"total": core.total, "passed": core.passed, "failed": core.failed},
        "metamorphic": {
            "total": metamorphic.total,
            "passed": metamorphic.passed,
            "failed": metamorphic.failed,
        },
        "boundaryMatrix": boundary,
        "partialCases": partial,
        "externalGateEvidence": canonicalize(evidence),
        "readiness": {
            "ready_for_rc_review": ready,
            "ready_for_release_candidate": ready,
            "ready_for_default_use": False,
            "mismatches": mismatches,
            "internal_errors": internal_errors,
            "golden_cases_passed": golden.passed,
            "real_acceptance_cases_passed": real_passed,
            "boundary_cases_passed": boundary["passed"],
            "cross_python_passed": cross_python_passed,
            "browser_legacy_passed": browser_legacy_passed,
            "python_regression_passed": python_regression_passed,
            "python_regression_cases": python_regression_cases,
            "graph_mirror_passed": graph_mirror_passed,
            "graph_mirror_cases": graph_mirror_cases,
            "browser_regression_passed": browser_regression_passed,
            "browser_regression_cases": browser_regression_cases,
            "validator_coverage": validator_coverage,
            "validator_implemented_rules": validator_implemented,
            "validator_tested_rules": validator_tested,
            "contract_decisions_open": contract_decisions_open,
            "partial_cases": partial["total"],
            "blockers": blockers,
            "warnings": warnings,
        },
        "productiveBehavior": {
            "legacyRemainsDefault": True,
            "readyForDefaultUse": False,
            "browserRemainsLegacy": True,
            "guiRemainsLegacy": True,
            "desktopRemainsLegacy": True,
            "solverRulesChanged": False,
            "folderHeuristicsAdded": False,
        },
        "reportFingerprintVersion": RELEASE_REPORT_FINGERPRINT_VERSION,
    }
    report["reportFingerprint"] = release_report_fingerprint(report)
    _reject_environment_fields(report)
    return report


def release_report_fingerprint(report: Mapping[str, Any]) -> str:
    payload = deepcopy(dict(report))
    payload.pop("reportFingerprint", None)
    performance = payload.get("directAcceptance", {}).get("performanceSmoke", {})
    performance.pop("observedSeconds", None)
    return stable_fingerprint(payload, version=RELEASE_REPORT_FINGERPRINT_VERSION)


def write_release_hardening_report(
    report: dict[str, Any], output: str | Path
) -> tuple[Path, Path]:
    output_path = Path(output)
    output_path.mkdir(parents=True, exist_ok=True)
    stem = f"Accuracy_Release_Hardening_{report['gameVersion']}"
    json_path = output_path / f"{stem}.json"
    text_path = output_path / f"{stem}.txt"
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    readiness = report["readiness"]
    text = "\n".join(
        (
            f"Accuracy 10 release hardening: {report['gameVersion']}",
            "Real A-to-B acceptance: "
            f"{report['realAcceptance']['passed']}/{report['realAcceptance']['total']}",
            "Direct three-mode acceptance: "
            f"{report['directAcceptance']['passed']}/{report['directAcceptance']['total']}",
            "Boundary cases: "
            f"{report['boundaryMatrix']['passed']}/{report['boundaryMatrix']['total']}",
            "Python regression and Graph Mirror: "
            f"{readiness['python_regression_cases']}/1977 and "
            f"{readiness['graph_mirror_cases']}/1977",
            "Browser regression: "
            f"{readiness['browser_regression_cases']}/1977",
            "Validator coverage: "
            f"{readiness['validator_tested_rules']}/"
            f"{readiness['validator_implemented_rules']} "
            f"({readiness['validator_coverage']:.2f}%)",
            f"Mismatches: {readiness['mismatches']}",
            f"Internal errors: {readiness['internal_errors']}",
            f"Intentional partial cases: {readiness['partial_cases']}",
            f"Ready for RC review: {'yes' if readiness['ready_for_rc_review'] else 'no'}",
            "Ready for default use: no",
            f"Fingerprint: {report['reportFingerprint']}",
            "",
        )
    )
    text_path.write_text(text, encoding="utf-8")
    return json_path, text_path


def _direct_request(
    database: VehicleDatabase,
    payload: Mapping[str, Any],
    case: Mapping[str, Any],
) -> tuple[PlayerProgress, SolveOptions]:
    target = database.get(case["targetVehicleId"])
    profile = payload["profiles"][case["profile"]]
    researched_rp = target.rp // 2 if profile["targetProgress"] == "half" else 0
    remaining_rp = target.rp - researched_rp
    convertible_rp = (
        remaining_rp // 2
        if profile["convertibleRp"] == "half_remaining"
        else None
    )
    progress = PlayerProgress(
        vehicles={
            target.id: VehicleProgress(researched_rp=researched_rp)
        } if researched_rp else {},
        convertible_rp=convertible_rp,
        owned_ge=profile["ownedGe"],
    )
    options = SolveOptions(
        include_start_vehicle=bool(profile.get("includeStartVehicle", False)),
        sl_discount_percent=profile["slDiscountPercent"],
    )
    return progress, options


def _direct_expected(
    database: VehicleDatabase,
    payload: Mapping[str, Any],
    case: Mapping[str, Any],
) -> dict[str, Any]:
    target = database.get(case["targetVehicleId"])
    profile = payload["profiles"][case["profile"]]
    researched_rp = target.rp // 2 if profile["targetProgress"] == "half" else 0
    target_remaining_rp = target.rp - researched_rp
    lines = []
    for vehicle_id in case["expectedRequiredVehicleIds"]:
        vehicle = database.get(vehicle_id)
        line_researched_rp = researched_rp if vehicle_id == target.id else 0
        remaining_rp = vehicle.rp - line_researched_rp
        ge = 0 if remaining_rp == 0 else math.ceil(remaining_rp / database.rp_per_ge)
        sl = round(vehicle.sl * (1 - profile["slDiscountPercent"] / 100))
        lines.append(
            {
                "vehicleId": vehicle.id,
                "totalRp": vehicle.rp,
                "researchedRp": line_researched_rp,
                "remainingRp": remaining_rp,
                "ge": ge,
                "sl": sl,
            }
        )
    total_rp = sum(item["remainingRp"] for item in lines)
    total_ge = sum(item["ge"] for item in lines)
    total_sl = sum(item["sl"] for item in lines)
    convertible_rp = (
        target_remaining_rp // 2
        if profile["convertibleRp"] == "half_remaining"
        else None
    )
    return {
        "requiredVehicleIds": case["expectedRequiredVehicleIds"],
        "vehicleLines": lines,
        "totalRp": total_rp,
        "totalGeBeforeOwned": total_ge,
        "totalGeAfterOwned": max(total_ge - profile["ownedGe"], 0),
        "totalSl": total_sl,
        "convertibleRpShortfall": (
            0 if convertible_rp is None else max(total_rp - convertible_rp, 0)
        ),
    }


def _user_projection(result: Any) -> dict[str, Any] | None:
    if result is None:
        return None
    payload = serialize_solve_result(result)
    return {
        "requiredVehicleIds": payload["required_vehicle_ids"],
        "vehicleLines": [
            {
                "vehicleId": item["vehicle_id"],
                "totalRp": item["total_rp"],
                "researchedRp": item["researched_rp"],
                "remainingRp": item["remaining_rp"],
                "ge": item["ge"],
                "sl": item["sl"],
            }
            for item in payload["vehicle_lines"]
        ],
        "totalRp": payload["total_rp"],
        "totalGeBeforeOwned": payload["total_ge_before_owned"],
        "totalGeAfterOwned": payload["total_ge_after_owned"],
        "totalSl": payload["total_sl"],
        "convertibleRpShortfall": payload["convertible_rp_shortfall"],
    }


def _invalid_boundary_cases(
    start: str,
    target: str,
    target_rp: int,
) -> tuple[tuple[str, dict[str, Any]], ...]:
    def request(
        *,
        target_id: str = target,
        start_id: str | None = start,
        progress: PlayerProgress | None = None,
        options: SolveOptions | None = None,
    ) -> dict[str, Any]:
        return {
            "target": target_id,
            "start": start_id,
            "progress": progress or PlayerProgress(),
            "options": options or SolveOptions(),
        }

    return (
        ("invalid:empty-target", request(target_id="")),
        ("invalid:unknown-target", request(target_id="missing_target")),
        ("invalid:empty-start", request(start_id="")),
        ("invalid:unknown-start", request(start_id="missing_start")),
        ("invalid:cross-country", request(start_id="ussr_bt_5")),
        ("invalid:cross-vehicle-type", request(start_id="bf-109b_2")),
        (
            "invalid:negative-rp",
            request(
                progress=PlayerProgress(
                    vehicles={target: VehicleProgress(researched_rp=-1)}
                )
            ),
        ),
        (
            "invalid:excess-rp",
            request(
                progress=PlayerProgress(
                    vehicles={target: VehicleProgress(researched_rp=target_rp + 1)}
                )
            ),
        ),
        (
            "invalid:researched-rp-conflict",
            request(
                progress=PlayerProgress(
                    vehicles={
                        target: VehicleProgress(
                            researched_rp=target_rp - 1,
                            researched=True,
                        )
                    }
                )
            ),
        ),
        (
            "invalid:purchased-without-researched",
            request(
                progress=PlayerProgress(
                    vehicles={
                        target: VehicleProgress(
                            researched_rp=target_rp,
                            purchased=True,
                        )
                    }
                )
            ),
        ),
        ("invalid:negative-owned-ge", request(progress=PlayerProgress(owned_ge=-1))),
        ("invalid:negative-convertible-rp", request(progress=PlayerProgress(convertible_rp=-1))),
        ("invalid:discount-negative", request(options=SolveOptions(sl_discount_percent=-1))),
        ("invalid:discount-one", request(options=SolveOptions(sl_discount_percent=1))),
        ("invalid:discount-twenty-nine", request(options=SolveOptions(sl_discount_percent=29))),
        ("invalid:discount-thirty-one", request(options=SolveOptions(sl_discount_percent=31))),
        ("invalid:discount-forty-nine", request(options=SolveOptions(sl_discount_percent=49))),
        ("invalid:discount-fifty-one", request(options=SolveOptions(sl_discount_percent=51))),
        ("invalid:discount-one-hundred", request(options=SolveOptions(sl_discount_percent=100))),
        (
            "invalid:unknown-optimize-mode",
            request(
                options=SolveOptions(optimize_for="unknown")  # type: ignore[arg-type]
            ),
        ),
    )


def _valid_boundary_cases(
    target: str,
    target_rp: int,
) -> tuple[tuple[str, PlayerProgress, SolveOptions], ...]:
    return (
        ("boundary:rp-zero", PlayerProgress(), SolveOptions()),
        (
            "boundary:rp-one",
            PlayerProgress(vehicles={target: VehicleProgress(researched_rp=1)}),
            SolveOptions(),
        ),
        (
            "boundary:rp-total-minus-one",
            PlayerProgress(
                vehicles={target: VehicleProgress(researched_rp=target_rp - 1)}
            ),
            SolveOptions(),
        ),
        (
            "boundary:fully-researched",
            PlayerProgress(
                vehicles={
                    target: VehicleProgress(
                        researched_rp=target_rp,
                        researched=True,
                    )
                }
            ),
            SolveOptions(),
        ),
        (
            "boundary:purchased",
            PlayerProgress(
                vehicles={
                    target: VehicleProgress(
                        researched_rp=target_rp,
                        researched=True,
                        purchased=True,
                    )
                }
            ),
            SolveOptions(),
        ),
        ("boundary:owned-ge-large", PlayerProgress(owned_ge=10**12), SolveOptions()),
        ("boundary:convertible-rp-zero", PlayerProgress(convertible_rp=0), SolveOptions()),
        ("boundary:convertible-rp-exact", PlayerProgress(convertible_rp=target_rp), SolveOptions()),
        ("boundary:convertible-rp-large", PlayerProgress(convertible_rp=10**12), SolveOptions()),
        ("boundary:discount-zero", PlayerProgress(), SolveOptions(sl_discount_percent=0)),
        ("boundary:discount-thirty", PlayerProgress(), SolveOptions(sl_discount_percent=30)),
        ("boundary:discount-fifty", PlayerProgress(), SolveOptions(sl_discount_percent=50)),
    )


def _all_numeric_values(value: Any) -> list[int]:
    if isinstance(value, bool) or value is None:
        return []
    if isinstance(value, int):
        return [value]
    if isinstance(value, list):
        return [item for nested in value for item in _all_numeric_values(nested)]
    if isinstance(value, dict):
        return [item for nested in value.values() for item in _all_numeric_values(nested)]
    return []


def _coverage_evidence(
    direct_fixture: Mapping[str, Any],
    golden_fixture: Mapping[str, Any],
    core_fixture: Mapping[str, Any],
) -> dict[str, dict[str, Any]]:
    direct_ids = [item["caseId"] for item in direct_fixture["cases"]]
    direct_tags = {
        tag: [item["caseId"] for item in direct_fixture["cases"] if tag in item["tags"]]
        for tag in {tag for item in direct_fixture["cases"] for tag in item["tags"]}
    }
    golden_tags = {
        tag: [item["case_id"] for item in golden_fixture["cases"] if tag in item["tags"]]
        for tag in {tag for item in golden_fixture["cases"] for tag in item["tags"]}
    }
    core_tags = {
        tag: [item["case_id"] for item in core_fixture["cases"] if tag in item["tags"]]
        for tag in {tag for item in core_fixture["cases"] for tag in item["tags"]}
    }
    evidence = {
        "all_nations": direct_ids,
        "all_vehicle_types": direct_ids,
        "all_research_trees": [
            item["caseId"]
            for item in direct_fixture["cases"]
            if item["caseId"].startswith("tree:")
        ],
        "path_short": direct_ids,
        "path_medium": golden_tags.get("chain:medium", []),
        "path_long": golden_tags.get("chain:long", []) + core_tags.get("accuracy9:path_long", []),
        "root_to_mid": direct_tags.get("reserve_start", []),
        "mid_to_late": golden_tags.get("chain:long", [])
        + core_tags.get("accuracy9:rank_transition", []),
        "rank_transition": golden_tags.get("rank:fulfilled", [])
        + golden_tags.get("rank:partial", [])
        + core_tags.get("accuracy9:rank_transition", []),
        "target_progress": direct_tags.get("target_partial_progress", [])
        + core_tags.get("accuracy9:target_partial", []),
        "intermediate_progress": golden_tags.get("progress:intermediate_partial", []),
        "purchased_vehicle": golden_tags.get("progress:intermediate_purchased", [])
        + core_tags.get("accuracy9:owned_intermediate", []),
        "folder": golden_tags.get("folder", []) + core_tags.get("accuracy9:folder", []),
        "req_unlock": golden_tags.get("req_unlock", []) + core_tags.get("accuracy9:req_unlock", []),
        "hidden_research": golden_tags.get("hidden:allowed", [])
        + golden_tags.get("hidden:blocked", [])
        + core_tags.get("accuracy9:hidden", []),
        "reserve": direct_tags.get("reserve_start", []),
        "zero_rp": direct_tags.get("zero_rp_line", []),
        "zero_sl": direct_tags.get("zero_sl_line", []),
        "owned_ge": direct_tags.get("owned_ge", [])
        + golden_tags.get("owned_ge", [])
        + core_tags.get("accuracy9:owned_ge", []),
        "convertible_rp": direct_tags.get("convertible_rp_shortfall", [])
        + golden_tags.get("convertible_rp_shortfall", [])
        + core_tags.get("accuracy9:convertible_shortfall", []),
        "sl_discount_0": [
            item["caseId"]
            for item in direct_fixture["cases"]
            if direct_fixture["profiles"][item["profile"]]["slDiscountPercent"] == 0
        ],
        "sl_discount_30": [
            item["caseId"]
            for item in direct_fixture["cases"]
            if direct_fixture["profiles"][item["profile"]]["slDiscountPercent"] == 30
        ],
        "sl_discount_50": [
            item["caseId"]
            for item in direct_fixture["cases"]
            if direct_fixture["profiles"][item["profile"]]["slDiscountPercent"] == 50
        ],
    }
    return {
        key: {"covered": bool(values), "caseIds": sorted(set(values))}
        for key, values in sorted(evidence.items())
    }


def _reject_environment_fields(payload: Any) -> None:
    forbidden = {
        "generatedAt",
        "localPath",
        "objectAddress",
        "platform",
        "pythonExecutable",
        "timestamp",
    }
    if isinstance(payload, dict):
        _require(not (forbidden & set(payload)), "environment fields excluded")
        for value in payload.values():
            _reject_environment_fields(value)
    elif isinstance(payload, list):
        for value in payload:
            _reject_environment_fields(value)


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ReleaseHardeningError(f"Release-hardening contract failed: {message}")
