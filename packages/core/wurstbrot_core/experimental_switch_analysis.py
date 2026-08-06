from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

from .database import VehicleDatabase
from .engine_execution import (
    EXECUTION_FINGERPRINT_VERSION,
    CalculationEngine,
    EngineFeatureFlags,
    ExecutionMode,
    ResultSource,
)
from .graph_pipeline import canonicalize, serialize_options, serialize_progress
from .graph_shadow import DualEngineCase, build_full_pipeline_cases, build_special_cases
from .models import PlayerProgress, SolveOptions, SolveResult, VehicleProgress


EXPERIMENTAL_REPORT_SCHEMA_VERSION = 1
EXPERIMENTAL_REPORT_VERSION = "1.0.0-experimental"
EXPERIMENTAL_REPORT_FINGERPRINT_VERSION = "graph-experimental-report-v1"

REQUIRED_ACCEPTANCE_TAGS = (
    "e2e:aircraft",
    "e2e:bluewater",
    "e2e:coastal",
    "e2e:germany_ground",
    "e2e:helicopter",
    "e2e:israel_ground",
    "e2e:japan_ground",
    "e2e:usa_ground",
    "e2e:ussr_ground",
)


def run_experimental_switch_matrix(
    database: VehicleDatabase,
    golden_fixture: dict[str, Any],
    *,
    cases: Iterable[DualEngineCase] | None = None,
) -> dict[str, Any]:
    """Exercise the opt-in graph source without changing productive defaults."""

    engine = CalculationEngine(
        database,
        feature_flags=EngineFeatureFlags.explicit_graph_experimental(),
    )
    full_cases = tuple(cases or build_full_pipeline_cases(database))
    comparison_counts: Counter[str] = Counter()
    graph_status_counts: Counter[str] = Counter()
    result_source_counts: Counter[str] = Counter()
    calculation_status_counts: Counter[str] = Counter()
    fallback_counts: Counter[str] = Counter()
    level_counts: dict[str, Counter[str]] = defaultdict(Counter)
    case_index: list[dict[str, Any]] = []

    for case in full_cases:
        result = engine.calculate(
            target_vehicle_id=case.target_vehicle_id,
            start_vehicle_id=case.start_vehicle_id,
            progress=case.progress,
            options=case.options,
            mode=ExecutionMode.GRAPH_EXPERIMENTAL,
        )
        comparison = (
            result.comparison_status.value
            if result.comparison_status is not None
            else "not_run"
        )
        graph_status = (
            result.graph_status.value if result.graph_status is not None else "not_run"
        )
        source = (
            result.result_source.value
            if result.result_source is not None
            else "none"
        )
        fallback_reason = (
            result.fallback_reason.value
            if result.fallback_reason is not None
            else "none"
        )
        comparison_counts[comparison] += 1
        graph_status_counts[graph_status] += 1
        result_source_counts[source] += 1
        calculation_status_counts[result.calculation_status.value] += 1
        fallback_counts[fallback_reason] += 1
        level_counts[case.level][source] += 1
        case_index.append(
            {
                "caseId": case.case_id,
                "level": case.level,
                "targetVehicleId": case.target_vehicle_id,
                "startVehicleId": case.start_vehicle_id,
                "resultSource": source,
                "calculationStatus": result.calculation_status.value,
                "graphStatus": graph_status,
                "comparisonStatus": comparison,
                "fallbackApplied": result.fallback_applied,
                "fallbackReason": fallback_reason,
                "executionFingerprint": result.fingerprint,
            }
        )

    acceptance = _run_acceptance_matrix(database, golden_fixture, engine)
    special = _run_special_case_matrix(database, engine)
    report = {
        "schemaVersion": EXPERIMENTAL_REPORT_SCHEMA_VERSION,
        "reportVersion": EXPERIMENTAL_REPORT_VERSION,
        "gameVersion": database.game_version,
        "executionFingerprintVersion": EXECUTION_FINGERPRINT_VERSION,
        "executionModes": {
            "legacy": "Only Legacy executes and supplies the user result.",
            "shadow": "Legacy supplies the user result while Graph is compared.",
            "graph_experimental": (
                "Graph supplies an exact complete result; Legacy runs in parallel "
                "and remains the fallback."
            ),
        },
        "defaultMode": "legacy",
        "recommendedMode": "legacy",
        "featureFlag": {
            "defaultEnabled": False,
            "activation": "explicit_per_cli_invocation",
            "persistent": False,
            "automaticConfidenceSwitching": False,
            "dataMigrationRequired": False,
        },
        "graphAcceptanceRule": "pipeline_complete_and_exact_match",
        "partialPolicy": "visible_graph_partial_status_with_legacy_fallback",
        "fullMatrix": {
            "scenarioCount": len(full_cases),
            "countingLevel": "one execution request per case",
            "comparisonCounts": _complete_counter(
                comparison_counts,
                (
                    "exact_match",
                    "equivalent_match",
                    "unresolved_expected",
                    "unsupported",
                    "input_contract_difference",
                    "mismatch",
                    "internal_error",
                ),
            ),
            "graphStatusCounts": dict(sorted(graph_status_counts.items())),
            "resultSourceCounts": _complete_counter(
                result_source_counts,
                ("graph", "legacy", "none"),
            ),
            "calculationStatusCounts": _complete_counter(
                calculation_status_counts,
                ("complete", "partial", "unavailable"),
            ),
            "fallbackReasonCounts": dict(sorted(fallback_counts.items())),
            "levelResultSourceCounts": {
                level: _complete_counter(counts, ("graph", "legacy", "none"))
                for level, counts in sorted(level_counts.items())
            },
            "caseIndex": case_index,
        },
        "acceptanceMatrix": acceptance,
        "specialCaseMatrix": special,
        "fallbackMatrix": {
            "policyCases": [
                {
                    "condition": "internal_error",
                    "action": "legacy_fallback",
                    "verifiedBy": "test_internal_error_uses_legacy_fallback_and_is_not_unresolved",
                },
                {
                    "condition": "unavailable",
                    "action": "legacy_fallback_when_legacy_result_exists",
                    "verifiedBy": "test_unavailable_and_mismatch_results_are_never_used_as_graph_output",
                },
                {
                    "condition": "invalid_input_legacy_accepted",
                    "action": "legacy_fallback",
                    "verifiedBy": "test_invalid_graph_input_that_legacy_accepts_uses_visible_fallback",
                },
                {
                    "condition": "partial",
                    "action": "legacy_fallback_without_graph_binding_totals",
                    "verifiedBy": "test_partial_graph_result_uses_visible_legacy_fallback",
                },
                {
                    "condition": "comparison_not_exact",
                    "action": "legacy_fallback",
                    "verifiedBy": "test_unavailable_and_mismatch_results_are_never_used_as_graph_output",
                },
                {
                    "condition": "adapter_contract_violation",
                    "action": "legacy_fallback",
                    "verifiedBy": "test_adapter_contract_violation_falls_back_without_leaking_exception",
                },
            ],
            "productiveLegacyFallback": True,
            "fallbackIsDiagnosed": True,
        },
        "runtimeScope": {
            "cliGraphExperimentalAvailable": True,
            "desktopResultSource": "legacy",
            "browserResultSource": "legacy",
            "desktopModified": False,
            "browserModified": False,
        },
        "fingerprintVersion": EXPERIMENTAL_REPORT_FINGERPRINT_VERSION,
        "fingerprint": "",
    }
    report["fingerprint"] = _report_fingerprint(report)
    return canonicalize(report)


def validate_experimental_switch_report(report: dict[str, Any]) -> None:
    _require(report.get("schemaVersion") == EXPERIMENTAL_REPORT_SCHEMA_VERSION)
    _require(report.get("reportVersion") == EXPERIMENTAL_REPORT_VERSION)
    _require(report.get("defaultMode") == "legacy")
    _require(report.get("recommendedMode") == "legacy")
    _require(report["featureFlag"]["defaultEnabled"] is False)
    _require(report["featureFlag"]["persistent"] is False)
    _require(report["featureFlag"]["automaticConfidenceSwitching"] is False)
    full = report["fullMatrix"]
    _require(full["scenarioCount"] == 2_090)
    _require(full["comparisonCounts"]["mismatch"] == 0)
    _require(full["comparisonCounts"]["internal_error"] == 0)
    _require(report["acceptanceMatrix"]["caseCount"] == 9)
    _require(report["acceptanceMatrix"]["passed"] == 9)
    _require(report["specialCaseMatrix"]["caseCount"] == 49)
    _require(report["specialCaseMatrix"]["graphResultFullyUsed"] == 35)
    _require(report["specialCaseMatrix"]["legacyFallbackUsed"] == 14)
    _require(report["specialCaseMatrix"]["partialGraphCases"] == 14)
    _require(report["runtimeScope"]["desktopResultSource"] == "legacy")
    _require(report["runtimeScope"]["browserResultSource"] == "legacy")
    _require(report.get("fingerprint") == _report_fingerprint(report))


def write_experimental_switch_reports(
    report: dict[str, Any],
    output_directory: str | Path,
) -> tuple[Path, Path]:
    validate_experimental_switch_report(report)
    output = Path(output_directory)
    output.mkdir(parents=True, exist_ok=True)
    stem = f"Graph_Experimental_{report['gameVersion']}"
    json_path = output / f"{stem}.json"
    text_path = output / f"{stem}.txt"
    json_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    text_path.write_text(render_experimental_switch_text(report), encoding="utf-8")
    return json_path, text_path


def render_experimental_switch_text(report: dict[str, Any]) -> str:
    full = report["fullMatrix"]
    comparisons = full["comparisonCounts"]
    sources = full["resultSourceCounts"]
    special = report["specialCaseMatrix"]
    acceptance = report["acceptanceMatrix"]
    return "\n".join(
        (
            f"Graph Experimental report: {report['gameVersion']}",
            f"Default mode: {report['defaultMode']}",
            f"Recommended mode: {report['recommendedMode']}",
            f"Scenarios: {full['scenarioCount']}",
            f"Graph result used: {sources['graph']}",
            f"Legacy fallback used: {sources['legacy']}",
            f"Unavailable: {sources['none']}",
            f"Exact matches: {comparisons['exact_match']}",
            f"Mismatches: {comparisons['mismatch']}",
            f"Internal errors: {comparisons['internal_error']}",
            f"Real A-to-B acceptance: {acceptance['passed']}/{acceptance['caseCount']}",
            f"Special cases using Graph: {special['graphResultFullyUsed']}",
            f"Special cases using Legacy fallback: {special['legacyFallbackUsed']}",
            f"Partial graph special cases: {special['partialGraphCases']}",
            f"Fingerprint: {report['fingerprint']}",
            "",
        )
    )


def _run_acceptance_matrix(
    database: VehicleDatabase,
    fixture: dict[str, Any],
    engine: CalculationEngine,
) -> dict[str, Any]:
    selected = [
        case
        for case in fixture["cases"]
        if any(tag in REQUIRED_ACCEPTANCE_TAGS for tag in case["tags"])
    ]
    observed_tags = {
        tag
        for case in selected
        for tag in case["tags"]
        if tag in REQUIRED_ACCEPTANCE_TAGS
    }
    _require(observed_tags == set(REQUIRED_ACCEPTANCE_TAGS))
    rows = []
    for case in selected:
        request = case["input"]
        progress = _progress_from_payload(request["progress"])
        options = _options_from_payload(request["options"])
        execution = engine.calculate(
            target_vehicle_id=request["target_vehicle_id"],
            start_vehicle_id=request["start_vehicle_id"],
            progress=progress,
            options=options,
            mode=ExecutionMode.GRAPH_EXPERIMENTAL,
        )
        actual = (
            _user_result_projection(execution.result)
            if execution.result is not None
            else None
        )
        expected = _golden_user_projection(case)
        passed = (
            execution.result_source is ResultSource.GRAPH
            and not execution.fallback_applied
            and actual == expected
        )
        rows.append(
            {
                "caseId": case["case_id"],
                "category": next(
                    tag for tag in case["tags"] if tag in REQUIRED_ACCEPTANCE_TAGS
                ),
                "purpose": case["purpose"],
                "startVehicleId": request["start_vehicle_id"],
                "targetVehicleId": request["target_vehicle_id"],
                "progress": serialize_progress(progress),
                "options": serialize_options(options),
                "expected": expected,
                "actual": actual,
                "expectedRuleIds": case["expected"]["rule_ids"],
                "graphStatus": (
                    execution.graph_status.value if execution.graph_status else None
                ),
                "comparisonStatus": (
                    execution.comparison_status.value
                    if execution.comparison_status
                    else None
                ),
                "resultSource": (
                    execution.result_source.value if execution.result_source else None
                ),
                "fallbackApplied": execution.fallback_applied,
                "fallbackReason": (
                    execution.fallback_reason.value
                    if execution.fallback_reason
                    else None
                ),
                "reviewStatus": case["review_status"],
                "expectationOrigins": [
                    case["primary_origin"],
                    *case["supporting_origins"],
                ],
                "passed": passed,
                "executionFingerprint": execution.fingerprint,
            }
        )
    passed = sum(item["passed"] for item in rows)
    return {
        "caseCount": len(rows),
        "passed": passed,
        "failed": len(rows) - passed,
        "independentExpectedResults": True,
        "cases": rows,
    }


def _run_special_case_matrix(
    database: VehicleDatabase,
    engine: CalculationEngine,
) -> dict[str, Any]:
    rows = []
    classifications: Counter[str] = Counter()
    for case in build_special_cases(database):
        execution = engine.calculate(
            target_vehicle_id=case.target_vehicle_id,
            start_vehicle_id=case.start_vehicle_id,
            progress=case.progress,
            options=case.options,
            mode=ExecutionMode.GRAPH_EXPERIMENTAL,
        )
        vehicle = database.get(case.target_vehicle_id)
        if execution.result_source is ResultSource.GRAPH:
            classification = "graph_result_fully_used"
        elif execution.fallback_applied:
            classification = "legacy_fallback_used"
        else:
            classification = "unsupported"
        classifications[classification] += 1
        rows.append(
            {
                "caseId": case.case_id,
                "targetVehicleId": case.target_vehicle_id,
                "hiddenResearch": vehicle.hidden_research,
                "reqUnlock": vehicle.req_unlock,
                "classification": classification,
                "resultSource": (
                    execution.result_source.value if execution.result_source else None
                ),
                "graphStatus": (
                    execution.graph_status.value if execution.graph_status else None
                ),
                "comparisonStatus": (
                    execution.comparison_status.value
                    if execution.comparison_status
                    else None
                ),
                "fallbackApplied": execution.fallback_applied,
                "fallbackReason": (
                    execution.fallback_reason.value
                    if execution.fallback_reason
                    else None
                ),
                "reason": (
                    "Exact complete Graph result accepted."
                    if classification == "graph_result_fully_used"
                    else (
                        "Graph prerequisite evidence is partial; binding Graph totals "
                        "are not exposed and Legacy supplies the user result."
                        if execution.graph_status
                        and execution.graph_status.value == "partial"
                        else "No safe graph user result is available."
                    )
                ),
            }
        )
    partial = sum(item["graphStatus"] == "partial" for item in rows)
    return {
        "caseCount": len(rows),
        "graphResultFullyUsed": classifications["graph_result_fully_used"],
        "legacyFallbackUsed": classifications["legacy_fallback_used"],
        "partialGraphCases": partial,
        "unsupported": classifications["unsupported"],
        "cases": rows,
    }


def _golden_user_projection(case: dict[str, Any]) -> dict[str, Any]:
    expected = case["expected"]
    totals = expected["totals"]
    _require(expected["pipeline_status"] == "complete")
    _require(totals is not None)
    return canonicalize(
        {
            "startVehicleId": case["input"]["start_vehicle_id"],
            "targetVehicleId": case["input"]["target_vehicle_id"],
            "requiredVehicleIds": expected["required_vehicle_ids"],
            "vehicleCostLines": [
                {
                    "vehicleId": line["vehicle_id"],
                    "remainingRp": line["remaining_rp"],
                    "ge": line["ge"],
                    "sl": line["discounted_sl"],
                }
                for line in expected["vehicle_cost_lines"]
            ],
            "rankRequirements": [
                {
                    "rank": item["rank"],
                    "required": item["required_count"],
                    "availableBefore": item["satisfied_count"],
                    "availableAfter": (
                        item["satisfied_count"] + len(item["selected_vehicle_ids"])
                    ),
                    "addedVehicleIds": item["selected_vehicle_ids"],
                }
                for item in expected["rank_requirements"]
            ],
            "totalRp": totals["remaining_rp"],
            "totalGeBeforeOwned": totals["ge_before_owned"],
            "totalGeAfterOwned": totals["ge_after_owned"],
            "totalSl": totals["sl"],
            "convertibleRpShortfall": totals["convertible_rp_shortfall"],
        }
    )


def _user_result_projection(result: SolveResult) -> dict[str, Any]:
    return canonicalize(
        {
            "startVehicleId": result.start_vehicle_id,
            "targetVehicleId": result.target_vehicle_id,
            "requiredVehicleIds": list(result.required_vehicle_ids),
            "vehicleCostLines": [
                {
                    "vehicleId": item.vehicle_id,
                    "remainingRp": item.remaining_rp,
                    "ge": item.ge,
                    "sl": item.sl,
                }
                for item in result.vehicle_lines
            ],
            "rankRequirements": [
                {
                    "rank": item.rank,
                    "required": item.required,
                    "availableBefore": item.available_before,
                    "availableAfter": item.available_after,
                    "addedVehicleIds": list(item.added_vehicle_ids),
                }
                for item in result.rank_requirements
            ],
            "totalRp": result.total_rp,
            "totalGeBeforeOwned": result.total_ge_before_owned,
            "totalGeAfterOwned": result.total_ge_after_owned,
            "totalSl": result.total_sl,
            "convertibleRpShortfall": result.convertible_rp_shortfall,
        }
    )


def _progress_from_payload(payload: dict[str, Any]) -> PlayerProgress:
    return PlayerProgress(
        vehicles={
            vehicle_id: VehicleProgress(
                researched_rp=state["researched_rp"],
                researched=state["researched"],
                purchased=state["purchased"],
            )
            for vehicle_id, state in payload["vehicles"].items()
        },
        convertible_rp=payload["convertible_rp"],
        owned_ge=payload["owned_ge"],
        fulfilled_unlocks=frozenset(payload["fulfilled_unlocks"]),
    )


def _options_from_payload(payload: dict[str, Any]) -> SolveOptions:
    return SolveOptions(
        optimize_for=payload["optimize_for"],
        include_start_vehicle=payload["include_start_vehicle"],
        include_hidden_legacy=payload["include_hidden_legacy"],
        assume_external_unlocks=payload["assume_external_unlocks"],
        sl_discount_percent=payload["sl_discount_percent"],
    )


def _complete_counter(
    counter: Counter[str],
    keys: tuple[str, ...],
) -> dict[str, int]:
    return {key: counter[key] for key in keys} | {
        key: value for key, value in sorted(counter.items()) if key not in keys
    }


def _report_fingerprint(report: dict[str, Any]) -> str:
    from .graph_pipeline import stable_fingerprint

    content = {key: value for key, value in report.items() if key != "fingerprint"}
    return stable_fingerprint(
        content,
        version=EXPERIMENTAL_REPORT_FINGERPRINT_VERSION,
    )


def _require(condition: bool) -> None:
    if not condition:
        raise ValueError("Experimental Graph Switch report contract failed.")
