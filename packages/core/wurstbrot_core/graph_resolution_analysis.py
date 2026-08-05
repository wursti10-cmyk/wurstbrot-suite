from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any, Iterable

from .database import VehicleDatabase
from .graph_resolution import (
    GraphPrerequisiteResolver,
    PrerequisiteResolution,
    RankCompatibilityStrategy,
    ResolutionStatus,
)
from .models import PlayerProgress, SolveOptions, VehicleProgress
from .research_graph import ResearchGraph
from .solver import ResearchSolver


@dataclass(frozen=True)
class ShadowCase:
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
class ShadowComparisonDetail:
    category: str
    target_vehicle_id: str
    start_vehicle_id: str | None
    player_progress_scenario: dict[str, Any]
    legacy_vehicle_ids: tuple[str, ...]
    graph_vehicle_ids: tuple[str, ...]
    only_legacy: tuple[str, ...]
    only_graph: tuple[str, ...]
    divergent_rules: tuple[str, ...]
    evidence: dict[str, Any]
    explanation_trace: tuple[str, ...]
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "category": self.category,
            "target_vehicle_id": self.target_vehicle_id,
            "start_vehicle_id": self.start_vehicle_id,
            "player_progress_scenario": self.player_progress_scenario,
            "legacy_vehicle_ids": list(self.legacy_vehicle_ids),
            "graph_vehicle_ids": list(self.graph_vehicle_ids),
            "only_legacy": list(self.only_legacy),
            "only_graph": list(self.only_graph),
            "divergent_rules": list(self.divergent_rules),
            "evidence": self.evidence,
            "explanation_trace": list(self.explanation_trace),
            "reason": self.reason,
        }


@dataclass(frozen=True)
class ShadowComparisonSummary:
    exact_match: int
    equivalent_match: int
    unresolved_expected: int
    unsupported: int
    mismatch: int
    scenario_count: int
    details: tuple[ShadowComparisonDetail, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "exact_match": self.exact_match,
            "equivalent_match": self.equivalent_match,
            "unresolved_expected": self.unresolved_expected,
            "unsupported": self.unsupported,
            "mismatch": self.mismatch,
            "scenario_count": self.scenario_count,
            "details": [item.to_dict() for item in self.details],
        }


@dataclass(frozen=True)
class ResolutionSpecialCaseSummary:
    previous_resolved: int
    current_resolved: int
    unresolved: int
    unsupported: int
    mismatch: int
    rows: tuple[dict[str, Any], ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "previous": {
                "exact_or_resolved": self.previous_resolved,
                "unresolved": sum(
                    row["previousCategory"] == "unresolved_expected" for row in self.rows
                ),
                "unsupported": sum(
                    row["previousCategory"] == "unsupported" for row in self.rows
                ),
            },
            "current": {
                "exact_or_resolved": self.current_resolved,
                "unresolved": self.unresolved,
                "unsupported": self.unsupported,
                "mismatch": self.mismatch,
            },
            "rows": list(self.rows),
        }


def run_shadow_comparison(
    database: VehicleDatabase,
    graph: ResearchGraph,
    cases: Iterable[ShadowCase],
    *,
    rank_compatibility_strategy: RankCompatibilityStrategy | None = None,
) -> ShadowComparisonSummary:
    legacy = ResearchSolver(database)
    resolver = GraphPrerequisiteResolver(
        graph,
        rank_compatibility_strategy=rank_compatibility_strategy,
    )
    counts: Counter[str] = Counter()
    details: list[ShadowComparisonDetail] = []
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
        legacy_ids: tuple[str, ...] = ()
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
        else:
            legacy_ids = legacy_result.required_vehicle_ids

        resolution = resolver.resolve(
            target_vehicle_id=case.target_vehicle_id,
            start_vehicle_id=case.start_vehicle_id,
            progress=progress,
            options=options,
        )
        graph_ids = resolution.required_vehicle_ids
        if resolution.resolution_status is ResolutionStatus.UNRESOLVED:
            category = "unresolved_expected"
            reason = "Graph resolution preserves at least one unresolved prerequisite."
        elif resolution.resolution_status is ResolutionStatus.UNSUPPORTED:
            category = "unsupported"
            reason = "Graph or compatibility input does not support a reliable comparison."
        elif resolution.resolution_status is ResolutionStatus.BLOCKED:
            if legacy_error is not None:
                category = "unsupported"
                reason = "Both paths reject the request, so no prerequisite set is comparable."
            else:
                category = "mismatch"
                reason = (
                    "Graph resolution blocks a request for which Legacy produced prerequisites."
                )
        elif legacy_error is not None:
            category = "mismatch"
            reason = f"Graph resolved while Legacy failed: {legacy_error}"
        elif graph_ids == legacy_ids:
            category = "exact_match"
            reason = "Ordered prerequisite vehicle IDs are identical."
        elif set(graph_ids) == set(legacy_ids):
            category = "equivalent_match"
            reason = "Prerequisite sets are equal; only deterministic representation differs."
        else:
            category = "mismatch"
            reason = "Resolved prerequisite vehicle sets differ."
        counts[category] += 1
        if category != "exact_match":
            details.append(_comparison_detail(case, resolution, category, reason, legacy_ids))

    return ShadowComparisonSummary(
        exact_match=counts["exact_match"],
        equivalent_match=counts["equivalent_match"],
        unresolved_expected=counts["unresolved_expected"],
        unsupported=counts["unsupported"],
        mismatch=counts["mismatch"],
        scenario_count=len(ordered_cases),
        details=tuple(details),
    )


def build_full_shadow_cases(database: VehicleDatabase) -> tuple[ShadowCase, ...]:
    cases = [
        ShadowCase(
            scenario_id=f"regular_empty_progress:{vehicle.id}",
            target_vehicle_id=vehicle.id,
            start_vehicle_id=database.predecessors.get(vehicle.id),
        )
        for vehicle in sorted(database.vehicles.values(), key=lambda item: item.id)
        if not vehicle.hidden_research
        and not vehicle.req_unlock
        and database.predecessors.get(vehicle.id)
    ]
    cases.extend(build_player_progress_scenarios(database))
    return tuple(cases)


def build_player_progress_scenarios(database: VehicleDatabase) -> tuple[ShadowCase, ...]:
    regular_targets = [
        vehicle
        for vehicle in sorted(database.vehicles.values(), key=lambda item: item.id)
        if not vehicle.hidden_research
        and not vehicle.req_unlock
        and database.predecessors.get(vehicle.id)
    ]
    if not regular_targets:
        return ()
    base = database.vehicles.get("germ_leopard_2a7v", regular_targets[0])
    predecessor_id = database.predecessors.get(base.id)
    if predecessor_id is None:
        base = regular_targets[0]
        predecessor_id = database.predecessors[base.id]
    tree = database.tree_vehicles(base.country_id, base.branch_id)
    second_progress_id = next(
        vehicle.id
        for vehicle in tree
        if vehicle.id not in {base.id, predecessor_id}
        and not vehicle.hidden_research
        and not vehicle.req_unlock
    )

    rank_target, rank_required, rank_vehicles = _rank_scenario_source(database)
    reserve_count = sum(vehicle.reserve for vehicle in rank_vehicles)
    owned_needed = max(rank_required - reserve_count, 0)
    owned_rank_ids = tuple(
        vehicle.id for vehicle in rank_vehicles if not vehicle.reserve
    )
    satisfied_rank_ids = owned_rank_ids[:owned_needed]
    partial_rank_ids = owned_rank_ids[: max(owned_needed - 1, 0)]

    folder_target = next(
        vehicle
        for vehicle in sorted(database.vehicles.values(), key=lambda item: item.id)
        if vehicle.group
        and vehicle.rank == 1
        and not vehicle.hidden_research
        and not vehicle.req_unlock
    )
    hidden = next(
        vehicle
        for vehicle in sorted(database.vehicles.values(), key=lambda item: item.id)
        if vehicle.hidden_research
    )
    external = next(
        vehicle
        for vehicle in sorted(database.vehicles.values(), key=lambda item: item.id)
        if vehicle.req_unlock
    )

    owned = lambda ids: PlayerProgress(  # noqa: E731 - compact deterministic fixture factory
        vehicles={
            vehicle_id: VehicleProgress(researched=True, purchased=True)
            for vehicle_id in ids
        }
    )
    return (
        ShadowCase("no_progress", base.id),
        ShadowCase(
            "start_vehicle_owned",
            base.id,
            predecessor_id,
            owned((predecessor_id,)),
        ),
        ShadowCase(
            "start_researched_not_purchased",
            base.id,
            progress=PlayerProgress(
                vehicles={
                    predecessor_id: VehicleProgress(researched=True, purchased=False)
                }
            ),
        ),
        ShadowCase(
            "target_partially_researched",
            base.id,
            predecessor_id,
            PlayerProgress(vehicles={base.id: VehicleProgress(researched_rp=1)}),
        ),
        ShadowCase(
            "single_predecessor_owned",
            base.id,
            progress=owned((predecessor_id,)),
        ),
        ShadowCase(
            "multiple_progress_vehicles_owned",
            base.id,
            progress=owned((predecessor_id, second_progress_id)),
        ),
        ShadowCase(
            "rank_satisfied",
            rank_target.id,
            progress=owned(satisfied_rank_ids),
        ),
        ShadowCase(
            "rank_partial",
            rank_target.id,
            progress=owned(partial_rank_ids),
        ),
        ShadowCase(
            "folder_member_owned",
            folder_target.id,
            progress=owned((folder_target.id,)),
        ),
        ShadowCase(
            "hidden_allowed",
            hidden.id,
            options=SolveOptions(include_hidden_legacy=True),
        ),
        ShadowCase("hidden_disallowed", hidden.id),
        ShadowCase(
            "external_unlock_assumed",
            external.id,
            options=SolveOptions(assume_external_unlocks=True),
        ),
        ShadowCase("external_unlock_not_assumed", external.id),
    )


def build_resolution_special_case_matrix(
    database: VehicleDatabase,
    graph: ResearchGraph,
    *,
    rank_compatibility_strategy: RankCompatibilityStrategy | None = None,
) -> ResolutionSpecialCaseSummary:
    rows: list[dict[str, Any]] = []
    counts: Counter[str] = Counter()
    for vehicle in sorted(database.vehicles.values(), key=lambda item: item.id):
        if not vehicle.hidden_research and not vehicle.req_unlock:
            continue
        previous = "unsupported" if vehicle.hidden_research else "unresolved_expected"
        options = SolveOptions(
            include_hidden_legacy=vehicle.hidden_research,
            assume_external_unlocks=bool(vehicle.req_unlock),
        )
        case = ShadowCase(
            scenario_id=f"special_explicit_evidence:{vehicle.id}",
            target_vehicle_id=vehicle.id,
            options=options,
        )
        comparison = run_shadow_comparison(
            database,
            graph,
            (case,),
            rank_compatibility_strategy=rank_compatibility_strategy,
        )
        current = _single_category(comparison)
        counts[current] += 1
        detail = comparison.details[0].to_dict() if comparison.details else None
        if detail is None:
            reason = "Ordered prerequisite vehicle IDs are identical."
        elif current == "unresolved_expected":
            rules = ", ".join(detail["divergent_rules"]) or "unclassified prerequisite"
            reason = (
                f"Unresolved rule(s): {rules}; explicit evidence does not resolve "
                "the remaining source ambiguity."
            )
        else:
            reason = detail["reason"]
        rows.append(
            {
                "vehicleId": vehicle.id,
                "hiddenResearch": vehicle.hidden_research,
                "reqUnlock": vehicle.req_unlock or None,
                "folder": vehicle.group,
                "previousCategory": previous,
                "currentCategory": current,
                "explicitEvidence": (
                    "include_hidden_legacy"
                    if vehicle.hidden_research
                    else "assume_external_unlocks"
                ),
                "reason": reason,
            }
        )
    return ResolutionSpecialCaseSummary(
        previous_resolved=0,
        current_resolved=counts["exact_match"] + counts["equivalent_match"],
        unresolved=counts["unresolved_expected"],
        unsupported=counts["unsupported"],
        mismatch=counts["mismatch"],
        rows=tuple(rows),
    )


def render_resolution_special_case_markdown(
    summary: ResolutionSpecialCaseSummary,
) -> str:
    lines = [
        "# Graph Prerequisite Special Case Comparison",
        "",
        "Each current comparison uses explicit evidence: hidden targets enable "
        "`include_hidden_legacy`; reqUnlock targets enable `assume_external_unlocks`. "
        "Folder ambiguity and missing source semantics remain unresolved.",
        "",
        "| Metric | Accuracy 3 | Accuracy 4 |",
        "|---|---:|---:|",
        f"| Exact/resolved | {summary.previous_resolved} | {summary.current_resolved} |",
        (
            "| Unresolved | "
            f"{sum(row['previousCategory'] == 'unresolved_expected' for row in summary.rows)} "
            f"| {summary.unresolved} |"
        ),
        (
            "| Unsupported | "
            f"{sum(row['previousCategory'] == 'unsupported' for row in summary.rows)} "
            f"| {summary.unsupported} |"
        ),
        f"| Mismatch | 0 | {summary.mismatch} |",
        "",
        "| Vehicle | hiddenResearch | reqUnlock | Folder | Previous | Current | "
        "Explicit evidence | Reason |",
        "|---|---:|---|---|---|---|---|---|",
    ]
    for row in summary.rows:
        values = (
            row["vehicleId"],
            "yes" if row["hiddenResearch"] else "no",
            row["reqUnlock"] or "—",
            row["folder"] or "—",
            row["previousCategory"],
            row["currentCategory"],
            row["explicitEvidence"],
            row["reason"],
        )
        lines.append("| " + " | ".join(str(value).replace("|", "\\|") for value in values) + " |")
    lines.append("")
    return "\n".join(lines)


def _comparison_detail(
    case: ShadowCase,
    resolution: PrerequisiteResolution,
    category: str,
    reason: str,
    legacy_ids: tuple[str, ...],
) -> ShadowComparisonDetail:
    graph_ids = resolution.required_vehicle_ids
    divergent_rules = {
        item.rule_id
        for item in (
            *resolution.blocking_rule_results,
            *resolution.unresolved_rule_results,
        )
    }
    divergent_rules.update(
        f"RANK_REQUIREMENT_{item.rank}"
        for item in resolution.rank_requirements
        if item.missing_count
    )
    return ShadowComparisonDetail(
        category=category,
        target_vehicle_id=case.target_vehicle_id,
        start_vehicle_id=case.start_vehicle_id,
        player_progress_scenario=case.to_dict(),
        legacy_vehicle_ids=legacy_ids,
        graph_vehicle_ids=graph_ids,
        only_legacy=tuple(sorted(set(legacy_ids) - set(graph_ids))),
        only_graph=tuple(sorted(set(graph_ids) - set(legacy_ids))),
        divergent_rules=tuple(sorted(divergent_rules)),
        evidence={
            "resolution": resolution.evidence,
            "rankRequirements": [item.to_dict() for item in resolution.rank_requirements],
        },
        explanation_trace=resolution.explanation_trace,
        reason=reason,
    )


def _rank_scenario_source(
    database: VehicleDatabase,
) -> tuple[Any, int, tuple[Any, ...]]:
    for country_id in sorted(database.rank_unlock):
        branches = database.rank_unlock[country_id]
        if not isinstance(branches, dict):
            continue
        for branch_id in sorted(branches):
            requirements = branches[branch_id]
            if not isinstance(requirements, dict):
                continue
            for rank_raw in sorted(requirements, key=lambda value: int(value)):
                required = int(requirements[rank_raw] or 0)
                rank = int(rank_raw)
                if required <= 0:
                    continue
                source = tuple(
                    vehicle
                    for vehicle in database.tree_vehicles(country_id, branch_id)
                    if vehicle.rank == rank
                    and not vehicle.hidden_research
                    and not vehicle.req_unlock
                    and not vehicle.premium
                    and not vehicle.special
                )
                targets = tuple(
                    vehicle
                    for vehicle in database.tree_vehicles(country_id, branch_id)
                    if vehicle.rank == rank + 1
                    and not vehicle.hidden_research
                    and not vehicle.req_unlock
                )
                reserve_count = sum(vehicle.reserve for vehicle in source)
                non_reserve_count = sum(not vehicle.reserve for vehicle in source)
                if targets and reserve_count < required <= reserve_count + non_reserve_count:
                    return targets[0], required, source
    raise ValueError("Sample database has no representative positive rank gate.")


def _single_category(summary: ShadowComparisonSummary) -> str:
    for category in (
        "exact_match",
        "equivalent_match",
        "unresolved_expected",
        "unsupported",
        "mismatch",
    ):
        if getattr(summary, category) == 1:
            return category
    raise AssertionError("Single-case comparison did not yield exactly one category.")
