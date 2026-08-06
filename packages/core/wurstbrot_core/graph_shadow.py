from __future__ import annotations

import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from .database import VehicleDatabase
from .dual_engine import ComparisonStatus, DualEngineRunner
from .graph_cost import GraphCostEngine
from .graph_cost_analysis import build_cost_scenarios, build_full_cost_shadow_cases
from .graph_evaluation import GraphRuleEvaluator
from .graph_pipeline import (
    DATAMINE_VALIDATION_RULE_IDS,
    FINGERPRINT_VERSION,
    INPUT_VALIDATION_RULE_IDS,
    GraphCalculationPipeline,
    PipelineStatus,
    canonicalize,
    serialize_options,
    serialize_progress,
    stable_fingerprint,
)
from .graph_resolution import GraphPrerequisiteResolver
from .graph_resolution_analysis import build_player_progress_scenarios
from .models import PlayerProgress, SolveOptions, VehicleProgress


SHADOW_REPORT_SCHEMA_VERSION = 1
SHADOW_REPORT_VERSION = "1.0.0-shadow"

COUNTING_LEVELS = (
    "regular_regression",
    "cost_scenario",
    "player_progress",
    "options_compatibility",
    "special_case",
    "input_validation",
)

OPTION_COVERAGE_LABELS = (
    "assume_external_unlocks:false",
    "assume_external_unlocks:true",
    "convertible_rp:set",
    "convertible_rp:unset",
    "include_hidden_legacy:false",
    "include_hidden_legacy:true",
    "include_start_vehicle:false",
    "include_start_vehicle:true",
    "legacy_discount:10",
    "legacy_discount:100",
    "optimize_for:ge",
    "optimize_for:rp",
    "optimize_for:sl",
    "optimize_for:vehicles",
    "owned_ge:positive",
    "owned_ge:zero",
    "sl_discount:0",
    "sl_discount:30",
    "sl_discount:50",
)

KNOWN_CONTRACT_DIFFERENCES = (
    {
        "contractRule": "GRAPH_SL_DISCOUNT_SET",
        "legacy": "Accepts every integer discount from 0 through 100.",
        "graph": "Accepts only the evidenced 0, 30 and 50 percent levels.",
        "decisionRequired": True,
    },
    {
        "contractRule": "STRICT_PROGRESS_RANGE",
        "legacy": "Clamps negative and excessive numeric research progress.",
        "graph": "Rejects invalid progress at the input boundary.",
        "decisionRequired": True,
    },
    {
        "contractRule": "RESEARCH_FLAG_NUMERIC_CONSISTENCY",
        "legacy": "Uses numeric RP for a researched but unpurchased vehicle.",
        "graph": "Keeps researched=True and conflicting numeric RP visible.",
        "decisionRequired": True,
    },
    {
        "contractRule": "STRUCTURED_INPUT_FAILURES",
        "legacy": "Uses exceptions or permissive runtime values.",
        "graph": "Returns invalid_input with rule-addressable evidence.",
        "decisionRequired": False,
    },
)

KNOWN_LIMITS = (
    "Folder acquisition semantics remain unresolved for 14 known Hidden/Folder targets.",
    "External unlock state is observable only through explicit progress or caller options.",
    "LegacyRankCompatibilityStrategy remains a comparison bridge, not optimizer semantics.",
    "The graph pipeline is not implemented in the browser runtime.",
    "Euro prices, packages, crew costs and user-facing Explain output are out of scope.",
)


@dataclass(frozen=True)
class DualEngineCase:
    level: str
    case_id: str
    target_vehicle_id: str
    start_vehicle_id: str | None = None
    progress: PlayerProgress | None = None
    options: SolveOptions | None = None
    coverage_labels: tuple[str, ...] = ()
    expected_input_rule_ids: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "level": self.level,
            "case_id": self.case_id,
            "target_vehicle_id": self.target_vehicle_id,
            "start_vehicle_id": self.start_vehicle_id,
            "progress": serialize_progress(self.progress or PlayerProgress()),
            "options": serialize_options(self.options or SolveOptions()),
            "coverage_labels": list(self.coverage_labels),
            "expected_input_rule_ids": list(self.expected_input_rule_ids),
        }


@dataclass(frozen=True)
class FullShadowSummary:
    game_version: str
    component_versions: dict[str, str]
    scenario_count: int
    comparison_counts: dict[str, int]
    pipeline_status_distribution: dict[str, int]
    counts_by_level: dict[str, dict[str, int]]
    case_index: tuple[dict[str, Any], ...]
    non_exact_details: tuple[dict[str, Any], ...]
    options_coverage: dict[str, Any]
    input_validation_coverage: dict[str, Any]
    special_case_statistics: dict[str, Any]
    readiness: dict[str, Any]
    known_contract_differences: tuple[dict[str, Any], ...]
    known_limits: tuple[str, ...]
    fingerprint_version: str
    fingerprint: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "schemaVersion": SHADOW_REPORT_SCHEMA_VERSION,
            "reportVersion": SHADOW_REPORT_VERSION,
            "gameVersion": self.game_version,
            "componentVersions": canonicalize(self.component_versions),
            "scenarioCount": self.scenario_count,
            "countingLevels": list(COUNTING_LEVELS),
            "comparisonCounts": _all_comparison_counts(self.comparison_counts),
            "pipelineStatusDistribution": _all_pipeline_counts(
                self.pipeline_status_distribution
            ),
            "countsByLevel": canonicalize(self.counts_by_level),
            "differencesByCategory": {
                key: self.comparison_counts.get(key, 0)
                for key in (
                    ComparisonStatus.EQUIVALENT_MATCH.value,
                    ComparisonStatus.UNRESOLVED_EXPECTED.value,
                    ComparisonStatus.UNSUPPORTED.value,
                    ComparisonStatus.INPUT_CONTRACT_DIFFERENCE.value,
                    ComparisonStatus.MISMATCH.value,
                    ComparisonStatus.INTERNAL_ERROR.value,
                )
            },
            "specialCaseStatistics": canonicalize(self.special_case_statistics),
            "optionsCoverage": canonicalize(self.options_coverage),
            "inputValidationCoverage": canonicalize(self.input_validation_coverage),
            "readiness": canonicalize(self.readiness),
            "caseResults": [canonicalize(item) for item in self.case_index],
            "nonExactDetails": [canonicalize(item) for item in self.non_exact_details],
            "fingerprints": {
                item["caseId"]: item["dualFingerprint"] for item in self.case_index
            },
            "knownContractDifferences": [
                canonicalize(item) for item in self.known_contract_differences
            ],
            "knownLimits": list(self.known_limits),
            "fingerprintVersion": self.fingerprint_version,
            "fingerprint": self.fingerprint,
            "shadowMode": True,
            "productiveLegacySolverModified": False,
            "guiModified": False,
            "browserModified": False,
            "optimizerSelectionPerformed": False,
        }


def build_full_pipeline_cases(database: VehicleDatabase) -> tuple[DualEngineCase, ...]:
    cases: list[DualEngineCase] = []
    regular = tuple(
        item
        for item in build_full_cost_shadow_cases(database)
        if item.scenario_id.startswith("regular_empty_progress:")
    )
    cases.extend(
        DualEngineCase(
            "regular_regression",
            f"regular:{item.scenario_id.removeprefix('regular_empty_progress:')}",
            item.target_vehicle_id,
            item.start_vehicle_id,
            item.progress,
            item.options,
        )
        for item in regular
    )
    cases.extend(
        DualEngineCase(
            "cost_scenario",
            f"cost:{item.scenario_id}",
            item.target_vehicle_id,
            item.start_vehicle_id,
            item.progress,
            item.options,
        )
        for item in build_cost_scenarios(database)
    )
    cases.extend(
        DualEngineCase(
            "player_progress",
            f"progress:{item.scenario_id}",
            item.target_vehicle_id,
            item.start_vehicle_id,
            item.progress,
            item.options,
        )
        for item in build_player_progress_scenarios(database)
    )
    cases.extend(build_options_compatibility_cases(database))
    cases.extend(build_special_cases(database))
    cases.extend(build_input_validation_cases(database))
    return tuple(
        sorted(
            cases,
            key=lambda item: (
                COUNTING_LEVELS.index(item.level),
                item.case_id,
                item.target_vehicle_id,
                item.start_vehicle_id or "",
            ),
        )
    )


def build_options_compatibility_cases(
    database: VehicleDatabase,
) -> tuple[DualEngineCase, ...]:
    target = database.vehicles.get("a5m4") or _first_regular_target(database)
    start = database.predecessors.get(target.id)
    hidden = next(
        item
        for item in sorted(database.vehicles.values(), key=lambda value: value.id)
        if item.hidden_research and not item.group and not item.req_unlock
    )
    unlock = next(
        item
        for item in sorted(database.vehicles.values(), key=lambda value: value.id)
        if item.req_unlock and not item.hidden_research
    )
    level = "options_compatibility"
    return (
        DualEngineCase(
            level,
            "options:baseline",
            target.id,
            start,
            coverage_labels=(
                "optimize_for:ge",
                "include_start_vehicle:false",
                "sl_discount:0",
                "owned_ge:zero",
                "convertible_rp:unset",
            ),
        ),
        DualEngineCase(
            level,
            "options:optimize_rp",
            target.id,
            start,
            options=SolveOptions(optimize_for="rp"),
            coverage_labels=("optimize_for:rp",),
        ),
        DualEngineCase(
            level,
            "options:optimize_sl",
            target.id,
            start,
            options=SolveOptions(optimize_for="sl"),
            coverage_labels=("optimize_for:sl",),
        ),
        DualEngineCase(
            level,
            "options:optimize_vehicles",
            target.id,
            start,
            options=SolveOptions(optimize_for="vehicles"),
            coverage_labels=("optimize_for:vehicles",),
        ),
        DualEngineCase(
            level,
            "options:include_start",
            target.id,
            start,
            options=SolveOptions(include_start_vehicle=True),
            coverage_labels=("include_start_vehicle:true",),
        ),
        DualEngineCase(
            level,
            "options:hidden_false",
            hidden.id,
            options=SolveOptions(include_hidden_legacy=False),
            coverage_labels=("include_hidden_legacy:false",),
        ),
        DualEngineCase(
            level,
            "options:hidden_true",
            hidden.id,
            options=SolveOptions(include_hidden_legacy=True),
            coverage_labels=("include_hidden_legacy:true",),
        ),
        DualEngineCase(
            level,
            "options:external_false",
            unlock.id,
            options=SolveOptions(assume_external_unlocks=False),
            coverage_labels=("assume_external_unlocks:false",),
        ),
        DualEngineCase(
            level,
            "options:external_true",
            unlock.id,
            options=SolveOptions(assume_external_unlocks=True),
            coverage_labels=("assume_external_unlocks:true",),
        ),
        DualEngineCase(
            level,
            "options:discount_30",
            target.id,
            start,
            options=SolveOptions(sl_discount_percent=30),
            coverage_labels=("sl_discount:30",),
        ),
        DualEngineCase(
            level,
            "options:discount_50",
            target.id,
            start,
            options=SolveOptions(sl_discount_percent=50),
            coverage_labels=("sl_discount:50",),
        ),
        DualEngineCase(
            level,
            "options:legacy_discount_10",
            target.id,
            start,
            options=SolveOptions(sl_discount_percent=10),
            coverage_labels=("legacy_discount:10",),
        ),
        DualEngineCase(
            level,
            "options:legacy_discount_100",
            target.id,
            start,
            options=SolveOptions(sl_discount_percent=100),
            coverage_labels=("legacy_discount:100",),
        ),
        DualEngineCase(
            level,
            "options:owned_ge",
            target.id,
            start,
            progress=PlayerProgress(owned_ge=1),
            coverage_labels=("owned_ge:positive",),
        ),
        DualEngineCase(
            level,
            "options:convertible_rp",
            target.id,
            start,
            progress=PlayerProgress(convertible_rp=target.rp),
            coverage_labels=("convertible_rp:set",),
        ),
    )


def build_special_cases(database: VehicleDatabase) -> tuple[DualEngineCase, ...]:
    return tuple(
        DualEngineCase(
            "special_case",
            f"special:{vehicle.id}",
            vehicle.id,
            options=SolveOptions(
                include_hidden_legacy=vehicle.hidden_research,
                assume_external_unlocks=bool(vehicle.req_unlock),
            ),
        )
        for vehicle in sorted(database.vehicles.values(), key=lambda item: item.id)
        if vehicle.hidden_research or vehicle.req_unlock
    )


def build_input_validation_cases(
    database: VehicleDatabase,
) -> tuple[DualEngineCase, ...]:
    target = database.vehicles.get("a5m4") or _first_regular_target(database)
    start = database.predecessors.get(target.id)
    same_type_other_country = next(
        item
        for item in sorted(database.vehicles.values(), key=lambda value: value.id)
        if item.branch_id == target.branch_id and item.country_id != target.country_id
    )
    same_country_other_type = next(
        item
        for item in sorted(database.vehicles.values(), key=lambda value: value.id)
        if item.country_id == target.country_id and item.branch_id != target.branch_id
    )
    level = "input_validation"

    def case(
        case_id: str,
        rule_id: str,
        *,
        target_id: str = target.id,
        start_id: str | None = start,
        progress: PlayerProgress | None = None,
        options: SolveOptions | None = None,
    ) -> DualEngineCase:
        return DualEngineCase(
            level,
            f"input:{case_id}",
            target_id,
            start_id,
            progress,
            options,
            expected_input_rule_ids=(rule_id,),
        )

    return (
        case("unknown_target", "INPUT_TARGET_UNKNOWN", target_id="missing", start_id=None),
        case("unknown_start", "INPUT_START_UNKNOWN", start_id="missing"),
        case(
            "country_mismatch",
            "INPUT_START_COUNTRY_MISMATCH",
            start_id=same_type_other_country.id,
        ),
        case(
            "vehicle_type_mismatch",
            "INPUT_START_VEHICLE_TYPE_MISMATCH",
            start_id=same_country_other_type.id,
        ),
        case(
            "unknown_progress_vehicle",
            "INPUT_PROGRESS_VEHICLE_UNKNOWN",
            progress=PlayerProgress(vehicles={"missing": VehicleProgress()}),
        ),
        case(
            "negative_progress",
            "INPUT_PROGRESS_RP_NEGATIVE_OR_INVALID",
            progress=PlayerProgress(
                vehicles={target.id: VehicleProgress(researched_rp=-1)}
            ),
        ),
        case(
            "excess_progress",
            "INPUT_PROGRESS_RP_EXCEEDS_TOTAL",
            progress=PlayerProgress(
                vehicles={target.id: VehicleProgress(researched_rp=target.rp + 1)}
            ),
        ),
        case(
            "invalid_progress_status",
            "INPUT_PROGRESS_STATUS_INVALID",
            progress=PlayerProgress(
                vehicles={
                    target.id: VehicleProgress(researched="yes")  # type: ignore[arg-type]
                }
            ),
        ),
        case(
            "purchase_without_research",
            "INPUT_PURCHASE_WITHOUT_RESEARCH",
            progress=PlayerProgress(
                vehicles={
                    target.id: VehicleProgress(researched=False, purchased=True)
                }
            ),
        ),
        case(
            "research_flag_rp_conflict",
            "INPUT_RESEARCH_FLAG_RP_CONFLICT",
            progress=PlayerProgress(
                vehicles={
                    target.id: VehicleProgress(researched_rp=0, researched=True)
                }
            ),
        ),
        case(
            "invalid_owned_ge",
            "INPUT_OWNED_GE_INVALID",
            progress=PlayerProgress(owned_ge=-1),
        ),
        case(
            "invalid_convertible_rp",
            "INPUT_CONVERTIBLE_RP_INVALID",
            progress=PlayerProgress(convertible_rp=-1),
        ),
        case(
            "invalid_unlock_token",
            "INPUT_FULFILLED_UNLOCK_INVALID",
            progress=PlayerProgress(
                fulfilled_unlocks=frozenset({1})  # type: ignore[arg-type]
            ),
        ),
        case(
            "invalid_optimize_for",
            "INPUT_OPTIMIZE_FOR_INVALID",
            options=SolveOptions(optimize_for="speed"),  # type: ignore[arg-type]
        ),
        case(
            "invalid_include_start",
            "INPUT_INCLUDE_START_INVALID",
            options=SolveOptions(include_start_vehicle=1),  # type: ignore[arg-type]
        ),
        case(
            "invalid_include_hidden",
            "INPUT_INCLUDE_HIDDEN_INVALID",
            options=SolveOptions(include_hidden_legacy=1),  # type: ignore[arg-type]
        ),
        case(
            "invalid_assume_external",
            "INPUT_ASSUME_EXTERNAL_INVALID",
            options=SolveOptions(assume_external_unlocks=1),  # type: ignore[arg-type]
        ),
        case(
            "invalid_discount",
            "INPUT_SL_DISCOUNT_INVALID",
            options=SolveOptions(sl_discount_percent=10),
        ),
    )


def run_full_pipeline_shadow(
    database: VehicleDatabase,
    cases: Iterable[DualEngineCase] | None = None,
) -> FullShadowSummary:
    ordered_cases = tuple(cases or build_full_pipeline_cases(database))
    runner = DualEngineRunner(database)
    comparison_counts: Counter[str] = Counter()
    pipeline_counts: Counter[str] = Counter()
    level_counts: dict[str, Counter[str]] = defaultdict(Counter)
    case_index: list[dict[str, Any]] = []
    details: list[dict[str, Any]] = []
    observed_option_labels: set[str] = set()
    observed_input_rules: set[str] = set()

    for case in ordered_cases:
        result = runner.run(
            target_vehicle_id=case.target_vehicle_id,
            start_vehicle_id=case.start_vehicle_id,
            progress=case.progress,
            options=case.options,
        )
        category = result.comparison_status.value
        pipeline_status = result.graph_result.pipeline_status.value
        comparison_counts[category] += 1
        pipeline_counts[pipeline_status] += 1
        level_counts[case.level][category] += 1
        observed_option_labels.update(case.coverage_labels)
        observed_input_rules.update(
            item.rule_id for item in result.graph_result.input_findings
        )
        expected_rules = set(case.expected_input_rule_ids)
        actual_rules = {
            item.rule_id for item in result.graph_result.input_findings
        }
        case_index.append(
            {
                "caseId": case.case_id,
                "level": case.level,
                "targetVehicleId": case.target_vehicle_id,
                "startVehicleId": case.start_vehicle_id,
                "comparisonStatus": category,
                "pipelineStatus": pipeline_status,
                "legacyStatus": result.legacy_result.status,
                "dualFingerprint": result.fingerprint,
                "graphFingerprint": result.graph_result.fingerprint,
                "legacyFingerprint": result.legacy_result.fingerprint,
                "coverageLabels": list(case.coverage_labels),
                "expectedInputRuleIds": sorted(expected_rules),
                "observedInputRuleIds": sorted(actual_rules),
                "expectedInputRulesObserved": expected_rules <= actual_rules,
            }
        )
        if result.comparison_status is not ComparisonStatus.EXACT_MATCH:
            non_exact_diagnostics = dict(
                result.diagnostics["nonExactComparison"] or {}
            )
            non_exact_diagnostics.update(
                {
                    "playerProgressScenario": case.case_id,
                    "countingLevel": case.level,
                    "dualFingerprint": result.fingerprint,
                }
            )
            details.append(
                {
                    "case": case.to_dict(),
                    "diagnostics": non_exact_diagnostics,
                    "comparison": result.to_dict(),
                }
            )

    options_coverage = _coverage(OPTION_COVERAGE_LABELS, observed_option_labels)
    input_coverage = _coverage(INPUT_VALIDATION_RULE_IDS, observed_input_rules)
    input_coverage.update(
        {
            "datamineRules": list(DATAMINE_VALIDATION_RULE_IDS),
            "datamineRulesCoveredByFocusedTests": True,
            "allExpectedRulesObserved": all(
                item["expectedInputRulesObserved"]
                for item in case_index
                if item["level"] == "input_validation"
            ),
        }
    )
    special_rows = [item for item in case_index if item["level"] == "special_case"]
    special_pipeline_counts = Counter(item["pipelineStatus"] for item in special_rows)
    special_comparison_counts = Counter(item["comparisonStatus"] for item in special_rows)
    special_stats = {
        "caseCount": len(special_rows),
        "pipelineStatusDistribution": _all_pipeline_counts(special_pipeline_counts),
        "comparisonCounts": _all_comparison_counts(special_comparison_counts),
    }
    readiness = _readiness(
        comparison_counts,
        options_coverage,
        input_coverage,
        special_stats,
    )
    component_versions = {
        "ruleEvaluator": GraphRuleEvaluator.version,
        "prerequisiteResolver": GraphPrerequisiteResolver.version,
        "costEngine": GraphCostEngine.version,
        "calculationPipeline": GraphCalculationPipeline.version,
        "dualEngineRunner": DualEngineRunner.version,
        "pipelineFingerprint": FINGERPRINT_VERSION,
        "dualFingerprint": "dual-engine-comparison-v1",
    }
    normalized_levels = {
        level: _all_comparison_counts(level_counts[level]) for level in COUNTING_LEVELS
    }
    preliminary_payload = {
        "gameVersion": database.game_version,
        "componentVersions": component_versions,
        "scenarioCount": len(ordered_cases),
        "comparisonCounts": _all_comparison_counts(comparison_counts),
        "pipelineStatusDistribution": _all_pipeline_counts(pipeline_counts),
        "countsByLevel": normalized_levels,
        "caseFingerprints": {
            item["caseId"]: item["dualFingerprint"] for item in case_index
        },
        "optionsCoverage": options_coverage,
        "inputValidationCoverage": input_coverage,
        "readiness": readiness,
    }
    return FullShadowSummary(
        game_version=database.game_version,
        component_versions=component_versions,
        scenario_count=len(ordered_cases),
        comparison_counts=dict(comparison_counts),
        pipeline_status_distribution=dict(pipeline_counts),
        counts_by_level=normalized_levels,
        case_index=tuple(case_index),
        non_exact_details=tuple(details),
        options_coverage=options_coverage,
        input_validation_coverage=input_coverage,
        special_case_statistics=special_stats,
        readiness=readiness,
        known_contract_differences=KNOWN_CONTRACT_DIFFERENCES,
        known_limits=KNOWN_LIMITS,
        fingerprint_version="graph-shadow-report-v1",
        fingerprint=stable_fingerprint(
            preliminary_payload,
            version="graph-shadow-report-v1",
        ),
    )


def write_shadow_reports(summary: FullShadowSummary, output: str | Path) -> tuple[Path, Path]:
    output_dir = Path(output)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / f"Graph_Shadow_{summary.game_version}.json"
    text_path = output_dir / f"Graph_Shadow_{summary.game_version}.txt"
    json_path.write_text(
        json.dumps(summary.to_dict(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    text_path.write_text(render_shadow_text(summary), encoding="utf-8")
    return json_path, text_path


def render_shadow_text(summary: FullShadowSummary) -> str:
    counts = _all_comparison_counts(summary.comparison_counts)
    statuses = _all_pipeline_counts(summary.pipeline_status_distribution)
    readiness = summary.readiness
    passed = not counts["mismatch"] and not counts["internal_error"]
    lines = [
        f"Graph shadow validation: {'passed' if passed else 'failed'}",
        f"Game version: {summary.game_version}",
        f"Scenarios: {summary.scenario_count}",
        f"Exact matches: {counts['exact_match']}",
        f"Equivalent matches: {counts['equivalent_match']}",
        f"Unresolved expected: {counts['unresolved_expected']}",
        f"Unsupported: {counts['unsupported']}",
        f"Input contract differences: {counts['input_contract_difference']}",
        f"Mismatches: {counts['mismatch']}",
        f"Internal errors: {counts['internal_error']}",
        f"Pipeline complete: {statuses['complete']}",
        f"Pipeline partial: {statuses['partial']}",
        f"Pipeline blocked: {statuses['blocked']}",
        f"Pipeline unavailable: {statuses['unavailable']}",
        f"Pipeline invalid input: {statuses['invalid_input']}",
        f"Pipeline internal error: {statuses['internal_error']}",
        f"Options coverage: {summary.options_coverage['coverage']:.2f}%",
        f"Input validation coverage: {summary.input_validation_coverage['coverage']:.2f}%",
        f"Special cases: {summary.special_case_statistics['caseCount']}",
        "Ready for experimental use: "
        + ("yes" if readiness["ready_for_experimental_use"] else "no"),
        "Ready for default use: "
        + ("yes" if readiness["ready_for_default_use"] else "no"),
        f"Fingerprint: {summary.fingerprint}",
        "",
    ]
    return "\n".join(lines)


def _coverage(expected: Iterable[str], observed: Iterable[str]) -> dict[str, Any]:
    implemented = tuple(sorted(set(expected)))
    tested = tuple(sorted(set(observed) & set(implemented)))
    missing = tuple(sorted(set(implemented) - set(tested)))
    coverage = 100.0 if not implemented else 100.0 * len(tested) / len(implemented)
    return {
        "implemented": len(implemented),
        "tested": len(tested),
        "coverage": round(coverage, 6),
        "implementedItems": list(implemented),
        "testedItems": list(tested),
        "missingItems": list(missing),
    }


def _readiness(
    comparisons: Counter[str],
    options_coverage: dict[str, Any],
    input_coverage: dict[str, Any],
    special_stats: dict[str, Any],
) -> dict[str, Any]:
    zero_mismatch = comparisons[ComparisonStatus.MISMATCH.value] == 0
    zero_internal = comparisons[ComparisonStatus.INTERNAL_ERROR.value] == 0
    options_complete = options_coverage["coverage"] == 100.0
    inputs_complete = input_coverage["coverage"] == 100.0
    experimental = zero_mismatch and zero_internal and options_complete and inputs_complete
    blockers = [
        "GRAPH_PIPELINE_NOT_IN_BROWSER",
        "LEGACY_RANK_COMPATIBILITY_STILL_ACTIVE",
    ]
    if comparisons[ComparisonStatus.UNRESOLVED_EXPECTED.value]:
        blockers.append("UNRESOLVED_PREREQUISITE_CASES")
    if comparisons[ComparisonStatus.UNSUPPORTED.value]:
        blockers.append("UNSUPPORTED_COMPARISON_CASES")
    if comparisons[ComparisonStatus.INPUT_CONTRACT_DIFFERENCE.value]:
        blockers.append("INPUT_CONTRACT_DIFFERENCES_REQUIRE_DECISION")
    if special_stats["pipelineStatusDistribution"][PipelineStatus.PARTIAL.value]:
        blockers.append("SPECIAL_FOLDER_CASES_PARTIAL")
    blockers = sorted(set(blockers))
    default = experimental and not blockers
    warnings = [
        "Experimental means shadow-only; the productive result remains Legacy.",
        "Graph diagnostics are evidence and are not automatic validator errors.",
    ]
    return {
        "ready_for_experimental_use": experimental,
        "ready_for_default_use": default,
        "blockers": blockers,
        "warnings": warnings,
        "evidence": {
            "zeroMismatches": zero_mismatch,
            "zeroInternalErrors": zero_internal,
            "allProductiveOptionsCovered": options_complete,
            "inputValidationCovered": inputs_complete,
            "knownContractDifferencesDecided": False,
            "folderUnlockLimitsDocumented": True,
            "representativeRealReferenceCasesPresent": True,
            "browserGraphPipelineParity": False,
            "legacyRankCompatibilityRetired": False,
            "rollbackPath": "Keep ResearchSolver as the productive source.",
        },
    }


def _all_comparison_counts(values: dict[str, int] | Counter[str]) -> dict[str, int]:
    return {status.value: int(values.get(status.value, 0)) for status in ComparisonStatus}


def _all_pipeline_counts(values: dict[str, int] | Counter[str]) -> dict[str, int]:
    return {status.value: int(values.get(status.value, 0)) for status in PipelineStatus}


def _first_regular_target(database: VehicleDatabase):
    return next(
        item
        for item in sorted(database.vehicles.values(), key=lambda value: value.id)
        if not item.hidden_research
        and not item.req_unlock
        and database.predecessors.get(item.id)
    )
