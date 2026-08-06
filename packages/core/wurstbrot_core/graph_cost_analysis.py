from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any, Iterable

from .database import VehicleDatabase
from .graph_cost import CostStatus, GraphCostEngine, GraphCostResult
from .graph_resolution import (
    GraphPrerequisiteResolver,
    RankCompatibilityStrategy,
    ResolutionStatus,
)
from .models import PlayerProgress, SolveOptions, VehicleProgress
from .research_graph import ResearchGraph
from .solver import ResearchSolver


@dataclass(frozen=True)
class CostShadowCase:
    scenario_id: str
    target_vehicle_id: str
    start_vehicle_id: str | None = None
    progress: PlayerProgress | None = None
    options: SolveOptions | None = None

    def to_dict(self) -> dict[str, Any]:
        progress = self.progress or PlayerProgress()
        options = self.options or SolveOptions()
        return {
            "scenario_id": self.scenario_id,
            "target_vehicle_id": self.target_vehicle_id,
            "start_vehicle_id": self.start_vehicle_id,
            "progress": {
                "vehicles": {
                    vehicle_id: {
                        "researched_rp": state.researched_rp,
                        "researched": state.researched,
                        "purchased": state.purchased,
                    }
                    for vehicle_id, state in sorted(progress.vehicles.items())
                },
                "convertible_rp": progress.convertible_rp,
                "owned_ge": progress.owned_ge,
                "fulfilled_unlocks": sorted(progress.fulfilled_unlocks),
            },
            "options": {
                "optimize_for": options.optimize_for,
                "include_start_vehicle": options.include_start_vehicle,
                "include_hidden_legacy": options.include_hidden_legacy,
                "assume_external_unlocks": options.assume_external_unlocks,
                "sl_discount_percent": options.sl_discount_percent,
            },
        }


@dataclass(frozen=True)
class CostShadowComparisonDetail:
    category: str
    target_vehicle_id: str
    start_vehicle_id: str | None
    progress_scenario: dict[str, Any]
    resolution_status: str
    cost_status: str
    legacy_vehicle_cost_lines: tuple[dict[str, Any], ...]
    graph_vehicle_cost_lines: tuple[dict[str, Any], ...]
    vehicle_differences: tuple[dict[str, Any], ...]
    rp_difference: int | None
    ge_difference: int | None
    sl_difference: int | None
    different_rounding: tuple[str, ...]
    evidence: dict[str, Any]
    explanation_trace: tuple[str, ...]
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "category": self.category,
            "target_vehicle_id": self.target_vehicle_id,
            "start_vehicle_id": self.start_vehicle_id,
            "progress_scenario": self.progress_scenario,
            "resolution_status": self.resolution_status,
            "cost_status": self.cost_status,
            "legacy_vehicle_cost_lines": list(self.legacy_vehicle_cost_lines),
            "graph_vehicle_cost_lines": list(self.graph_vehicle_cost_lines),
            "vehicle_differences": list(self.vehicle_differences),
            "rp_difference": self.rp_difference,
            "ge_difference": self.ge_difference,
            "sl_difference": self.sl_difference,
            "different_rounding": list(self.different_rounding),
            "evidence": self.evidence,
            "explanation_trace": list(self.explanation_trace),
            "reason": self.reason,
        }


@dataclass(frozen=True)
class CostShadowComparisonSummary:
    exact_match: int
    equivalent_match: int
    unresolved_expected: int
    unsupported: int
    mismatch: int
    scenario_count: int
    cost_status_distribution: dict[str, int]
    details: tuple[CostShadowComparisonDetail, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "exact_match": self.exact_match,
            "equivalent_match": self.equivalent_match,
            "unresolved_expected": self.unresolved_expected,
            "unsupported": self.unsupported,
            "mismatch": self.mismatch,
            "scenario_count": self.scenario_count,
            "cost_status_distribution": {
                key: self.cost_status_distribution.get(key, 0)
                for key in ("complete", "partial", "unavailable")
            },
            "details": [item.to_dict() for item in self.details],
        }


@dataclass(frozen=True)
class CostSpecialCaseSummary:
    complete: int
    partial: int
    unavailable: int
    rows: tuple[dict[str, Any], ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "complete": self.complete,
            "partial": self.partial,
            "unavailable": self.unavailable,
            "case_count": len(self.rows),
            "rows": list(self.rows),
        }


def run_cost_shadow_comparison(
    database: VehicleDatabase,
    graph: ResearchGraph,
    cases: Iterable[CostShadowCase],
    *,
    rank_compatibility_strategy: RankCompatibilityStrategy | None = None,
) -> CostShadowComparisonSummary:
    legacy = ResearchSolver(database)
    resolver = GraphPrerequisiteResolver(
        graph,
        rank_compatibility_strategy=rank_compatibility_strategy,
    )
    cost_engine = GraphCostEngine(database)
    counts: Counter[str] = Counter()
    cost_statuses: Counter[str] = Counter()
    details: list[CostShadowComparisonDetail] = []
    ordered_cases = tuple(
        sorted(
            cases,
            key=lambda item: (
                item.scenario_id,
                item.target_vehicle_id,
                item.start_vehicle_id or "",
            ),
        )
    )
    for case in ordered_cases:
        progress = case.progress or PlayerProgress()
        options = case.options or SolveOptions()
        legacy_result = None
        legacy_error: str | None = None
        try:
            legacy_result = legacy.solve(
                target_vehicle_id=case.target_vehicle_id,
                start_vehicle_id=case.start_vehicle_id,
                progress=progress,
                options=options,
            )
        except Exception as exc:
            legacy_error = f"{type(exc).__name__}: {exc}"

        resolution = resolver.resolve(
            target_vehicle_id=case.target_vehicle_id,
            start_vehicle_id=case.start_vehicle_id,
            progress=progress,
            options=options,
        )
        graph_result = cost_engine.calculate(
            resolution,
            progress=progress,
            options=options,
        )
        cost_statuses[graph_result.cost_status.value] += 1
        category, reason = _cost_category(
            resolution.resolution_status,
            graph_result,
            legacy_result,
            legacy_error,
            progress,
        )
        counts[category] += 1
        if category != "exact_match":
            details.append(
                _cost_comparison_detail(
                    database,
                    case,
                    graph_result,
                    legacy_result,
                    legacy_error,
                    category,
                    reason,
                )
            )

    return CostShadowComparisonSummary(
        exact_match=counts["exact_match"],
        equivalent_match=counts["equivalent_match"],
        unresolved_expected=counts["unresolved_expected"],
        unsupported=counts["unsupported"],
        mismatch=counts["mismatch"],
        scenario_count=len(ordered_cases),
        cost_status_distribution=dict(cost_statuses),
        details=tuple(details),
    )


def build_full_cost_shadow_cases(
    database: VehicleDatabase,
) -> tuple[CostShadowCase, ...]:
    cases = [
        CostShadowCase(
            scenario_id=f"regular_empty_progress:{vehicle.id}",
            target_vehicle_id=vehicle.id,
            start_vehicle_id=database.predecessors.get(vehicle.id),
        )
        for vehicle in sorted(database.vehicles.values(), key=lambda item: item.id)
        if not vehicle.hidden_research
        and not vehicle.req_unlock
        and database.predecessors.get(vehicle.id)
    ]
    cases.extend(build_cost_scenarios(database))
    return tuple(cases)


def build_cost_scenarios(database: VehicleDatabase) -> tuple[CostShadowCase, ...]:
    target = database.get("a5m4")
    start_id = database.predecessors[target.id]
    if start_id is None:
        raise ValueError("Sample cost target must have a predecessor.")
    chain_target = database.get("b6n1")
    intermediate_id = database.predecessors[chain_target.id]
    if intermediate_id is None:
        raise ValueError("Sample intermediate cost target must have a predecessor.")
    zero_rp = database.get("ab_205a_1")
    zero_sl = database.get("bf2c_1")

    return (
        CostShadowCase("01_no_progress", target.id, start_id),
        CostShadowCase(
            "02_target_partially_researched",
            target.id,
            start_id,
            PlayerProgress(
                vehicles={target.id: VehicleProgress(researched_rp=target.rp // 2)}
            ),
        ),
        CostShadowCase(
            "03_intermediate_partially_researched",
            chain_target.id,
            progress=PlayerProgress(
                vehicles={
                    intermediate_id: VehicleProgress(
                        researched_rp=database.get(intermediate_id).rp // 2
                    )
                }
            ),
        ),
        CostShadowCase(
            "04_fully_researched_not_purchased",
            target.id,
            start_id,
            PlayerProgress(
                vehicles={
                    target.id: VehicleProgress(
                        researched_rp=target.rp,
                        researched=True,
                        purchased=False,
                    )
                }
            ),
        ),
        CostShadowCase(
            "05_vehicle_purchased",
            target.id,
            start_id,
            PlayerProgress(
                vehicles={
                    target.id: VehicleProgress(researched=True, purchased=True)
                }
            ),
        ),
        CostShadowCase("06_start_excluded", target.id, start_id),
        CostShadowCase(
            "07_start_included",
            target.id,
            start_id,
            options=SolveOptions(include_start_vehicle=True),
        ),
        CostShadowCase(
            "08_owned_ge_below_total",
            target.id,
            start_id,
            PlayerProgress(owned_ge=1),
        ),
        CostShadowCase(
            "09_owned_ge_above_total",
            target.id,
            start_id,
            PlayerProgress(owned_ge=1_000_000),
        ),
        CostShadowCase(
            "10_convertible_rp_sufficient",
            target.id,
            start_id,
            PlayerProgress(convertible_rp=target.rp),
        ),
        CostShadowCase(
            "11_convertible_rp_insufficient",
            target.id,
            start_id,
            PlayerProgress(convertible_rp=1),
        ),
        CostShadowCase(
            "12_sl_discount_0",
            target.id,
            start_id,
            options=SolveOptions(sl_discount_percent=0),
        ),
        CostShadowCase(
            "13_sl_discount_30",
            target.id,
            start_id,
            options=SolveOptions(sl_discount_percent=30),
        ),
        CostShadowCase(
            "14_sl_discount_50",
            target.id,
            start_id,
            options=SolveOptions(sl_discount_percent=50),
        ),
        CostShadowCase(
            "15_zero_rp_vehicle",
            zero_rp.id,
            options=SolveOptions(assume_external_unlocks=True),
        ),
        CostShadowCase("16_zero_sl_vehicle", zero_sl.id),
        CostShadowCase("17_unresolved_folder", "ar_2", "yak-4"),
        CostShadowCase("18_unresolved_unlock", zero_rp.id),
    )


def build_cost_special_case_matrix(
    database: VehicleDatabase,
    graph: ResearchGraph,
    *,
    rank_compatibility_strategy: RankCompatibilityStrategy | None = None,
) -> CostSpecialCaseSummary:
    resolver = GraphPrerequisiteResolver(
        graph,
        rank_compatibility_strategy=rank_compatibility_strategy,
    )
    cost_engine = GraphCostEngine(database)
    counts: Counter[str] = Counter()
    rows: list[dict[str, Any]] = []
    for vehicle in sorted(database.vehicles.values(), key=lambda item: item.id):
        if not vehicle.hidden_research and not vehicle.req_unlock:
            continue
        options = SolveOptions(
            include_hidden_legacy=vehicle.hidden_research,
            assume_external_unlocks=bool(vehicle.req_unlock),
        )
        resolution = resolver.resolve(
            target_vehicle_id=vehicle.id,
            options=options,
        )
        cost = cost_engine.calculate(resolution, options=options)
        counts[cost.cost_status.value] += 1
        open_rules = tuple(
            sorted(
                {
                    item.rule_id
                    for item in (
                        *resolution.blocking_rule_results,
                        *resolution.unresolved_rule_results,
                    )
                }
            )
        )
        affected_rules = set(open_rules)
        if vehicle.hidden_research:
            affected_rules.add("TARGET_VISIBILITY")
        if vehicle.req_unlock:
            affected_rules.add("UNLOCK_REQUIREMENT")
        if vehicle.group:
            affected_rules.add("FOLDER_MEMBERSHIP")
        rows.append(
            {
                "vehicleId": vehicle.id,
                "hiddenResearch": vehicle.hidden_research,
                "reqUnlock": vehicle.req_unlock or None,
                "folder": vehicle.group,
                "resolutionStatus": resolution.resolution_status.value,
                "costStatus": cost.cost_status.value,
                "reasonCodes": list(cost.incomplete_reason_codes),
                "affectedRuleIds": sorted(affected_rules),
                "additionalSourceData": (
                    _additional_source_data(open_rules)
                    if cost.cost_status is not CostStatus.COMPLETE
                    else None
                ),
            }
        )
    return CostSpecialCaseSummary(
        complete=counts[CostStatus.COMPLETE.value],
        partial=counts[CostStatus.PARTIAL.value],
        unavailable=counts[CostStatus.UNAVAILABLE.value],
        rows=tuple(rows),
    )


def render_cost_special_case_markdown(summary: CostSpecialCaseSummary) -> str:
    lines = [
        "# Graph Cost Special Case Matrix",
        "",
        "Hidden targets use explicit `include_hidden_legacy`; reqUnlock targets use explicit "
        "`assume_external_unlocks`. Partial lines are diagnostic only and never represent totals.",
        "",
        "| Cost status | Count |",
        "|---|---:|",
        f"| Complete | {summary.complete} |",
        f"| Partial | {summary.partial} |",
        f"| Unavailable | {summary.unavailable} |",
        "",
        "| Vehicle | Hidden | reqUnlock | Folder | Resolution | Cost | Reason codes | "
        "Rule IDs | Additional source data |",
        "|---|---:|---|---|---|---|---|---|---|",
    ]
    for row in summary.rows:
        values = (
            row["vehicleId"],
            "yes" if row["hiddenResearch"] else "no",
            row["reqUnlock"] or "—",
            row["folder"] or "—",
            row["resolutionStatus"],
            row["costStatus"],
            ", ".join(row["reasonCodes"]) or "—",
            ", ".join(row["affectedRuleIds"]) or "—",
            row["additionalSourceData"] or "—",
        )
        lines.append(
            "| "
            + " | ".join(str(value).replace("|", "\\|") for value in values)
            + " |"
        )
    lines.append("")
    return "\n".join(lines)


def _cost_category(
    resolution_status: ResolutionStatus,
    graph_result: GraphCostResult,
    legacy_result: Any,
    legacy_error: str | None,
    progress: PlayerProgress,
) -> tuple[str, str]:
    validation_reasons = set(graph_result.incomplete_reason_codes) - {
        "RESOLUTION_BLOCKED",
        "RESOLUTION_UNRESOLVED",
        "RESOLUTION_UNSUPPORTED",
    }
    if validation_reasons:
        if legacy_error is not None:
            return "unsupported", "Neither path provides a comparable valid cost result."
        return (
            "mismatch",
            "Graph cost validation rejected input for which Legacy emitted costs.",
        )
    if resolution_status is ResolutionStatus.UNRESOLVED:
        return (
            "unresolved_expected",
            "Prerequisite resolution is unresolved; graph cost lines are partial only.",
        )
    if resolution_status is ResolutionStatus.UNSUPPORTED:
        return "unsupported", "Prerequisite resolution is unsupported."
    if resolution_status is ResolutionStatus.BLOCKED:
        if legacy_error is not None:
            return "unsupported", "Both paths reject the request; no cost is comparable."
        return "mismatch", "Graph resolution blocks a request for which Legacy emits costs."
    if graph_result.cost_status is CostStatus.UNAVAILABLE:
        if legacy_error is not None:
            return "unsupported", "Neither path provides a comparable cost result."
        return "mismatch", "Graph cost validation rejected a Legacy cost result."
    if legacy_error is not None or legacy_result is None:
        return "mismatch", f"Graph cost completed while Legacy failed: {legacy_error}"

    graph_ids = tuple(item.vehicle_id for item in graph_result.vehicle_cost_lines)
    legacy_ids = tuple(item.vehicle_id for item in legacy_result.vehicle_lines)
    lines_equal = _normalized_graph_lines(graph_result) == _normalized_legacy_lines(
        legacy_result
    )
    totals_equal = _totals_equal(graph_result, legacy_result, progress)
    if graph_ids == legacy_ids and lines_equal and totals_equal:
        return "exact_match", "Ordered vehicle lines and all requested costs are identical."
    if set(graph_ids) == set(legacy_ids) and lines_equal and totals_equal:
        return (
            "equivalent_match",
            "Vehicle cost sets and totals are identical; only representation differs.",
        )
    return "mismatch", "Definitive Legacy and Graph cost results differ."


def _cost_comparison_detail(
    database: VehicleDatabase,
    case: CostShadowCase,
    graph_result: GraphCostResult,
    legacy_result: Any,
    legacy_error: str | None,
    category: str,
    reason: str,
) -> CostShadowComparisonDetail:
    legacy_lines = _legacy_line_dicts(database, legacy_result)
    graph_lines = tuple(item.to_dict() for item in graph_result.vehicle_cost_lines)
    legacy_map = {item["vehicle_id"]: item for item in legacy_lines}
    graph_map = {item["vehicle_id"]: item for item in graph_lines}
    differences: list[dict[str, Any]] = []
    different_rounding: list[str] = []
    for vehicle_id in sorted(set(legacy_map) | set(graph_map)):
        legacy = legacy_map.get(vehicle_id)
        graph = graph_map.get(vehicle_id)
        diff: dict[str, Any] = {"vehicle_id": vehicle_id}
        if legacy is None:
            diff["only_graph"] = graph
        elif graph is None:
            diff["only_legacy"] = legacy
        else:
            for field in ("remaining_rp", "ge", "discounted_sl"):
                if legacy[field] != graph[field]:
                    diff[field] = {"legacy": legacy[field], "graph": graph[field]}
            if legacy["ge"] != graph["ge"]:
                different_rounding.append(vehicle_id)
        if len(diff) > 1:
            differences.append(diff)

    legacy_rp = legacy_result.total_rp if legacy_result is not None else None
    legacy_ge = (
        legacy_result.total_ge_before_owned if legacy_result is not None else None
    )
    legacy_sl = legacy_result.total_sl if legacy_result is not None else None
    return CostShadowComparisonDetail(
        category=category,
        target_vehicle_id=case.target_vehicle_id,
        start_vehicle_id=case.start_vehicle_id,
        progress_scenario=case.to_dict(),
        resolution_status=graph_result.resolution_status.value,
        cost_status=graph_result.cost_status.value,
        legacy_vehicle_cost_lines=legacy_lines,
        graph_vehicle_cost_lines=graph_lines,
        vehicle_differences=tuple(differences),
        rp_difference=_difference(graph_result.total_remaining_rp, legacy_rp),
        ge_difference=_difference(graph_result.total_ge_before_owned, legacy_ge),
        sl_difference=_difference(graph_result.total_sl, legacy_sl),
        different_rounding=tuple(different_rounding),
        evidence={
            "legacyError": legacy_error,
            "graphCost": graph_result.to_dict(),
        },
        explanation_trace=graph_result.explanation_trace,
        reason=reason,
    )


def _legacy_line_dicts(
    database: VehicleDatabase,
    legacy_result: Any,
) -> tuple[dict[str, Any], ...]:
    if legacy_result is None:
        return ()
    return tuple(
        {
            "vehicle_id": line.vehicle_id,
            "reason": line.reason,
            "total_rp": line.total_rp,
            "researched_rp": line.researched_rp,
            "remaining_rp": line.remaining_rp,
            "ge": line.ge,
            "base_sl": database.get(line.vehicle_id).sl,
            "discounted_sl": line.sl,
            "already_owned": line.already_owned,
        }
        for line in legacy_result.vehicle_lines
    )


def _normalized_legacy_lines(legacy_result: Any) -> dict[str, tuple[int, int, int]]:
    return {
        line.vehicle_id: (line.remaining_rp, line.ge, line.sl)
        for line in legacy_result.vehicle_lines
    }


def _normalized_graph_lines(result: GraphCostResult) -> dict[str, tuple[int, int, int]]:
    return {
        line.vehicle_id: (line.remaining_rp, line.ge, line.discounted_sl)
        for line in result.vehicle_cost_lines
    }


def _totals_equal(
    graph: GraphCostResult,
    legacy: Any,
    progress: PlayerProgress,
) -> bool:
    return (
        graph.total_remaining_rp == legacy.total_rp
        and graph.total_ge_before_owned == legacy.total_ge_before_owned
        and graph.total_ge_after_owned == legacy.total_ge_after_owned
        and graph.total_sl == legacy.total_sl
        and graph.owned_ge == progress.owned_ge
        and graph.convertible_rp_shortfall == legacy.convertible_rp_shortfall
    )


def _difference(graph: int | None, legacy: int | None) -> int | None:
    if graph is None or legacy is None:
        return None
    return graph - legacy


def _additional_source_data(rule_ids: tuple[str, ...]) -> str | None:
    if any("FOLDER" in item for item in rule_ids):
        return "Datamine proof for folder research and purchase eligibility."
    if any("UNLOCK" in item for item in rule_ids):
        return "Authoritative unlock fulfillment and acquisition semantics."
    if any("PREDECESSOR" in item for item in rule_ids):
        return "Authoritative AND/OR semantics for multiple predecessors."
    return None
