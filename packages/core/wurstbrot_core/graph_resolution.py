from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Iterable, Protocol

from .database import VehicleDatabase
from .graph_evaluation import (
    EvaluationStatus,
    GraphRuleEvaluator,
    RuleEvaluation,
    UnlockClassification,
)
from .models import PlayerProgress, SolveOptions
from .research_graph import EdgeType, GraphNode, NodeType, ResearchGraph
from .solver import ResearchSolver


class ResolutionStatus(str, Enum):
    RESOLVED = "resolved"
    BLOCKED = "blocked"
    UNRESOLVED = "unresolved"
    UNSUPPORTED = "unsupported"


@dataclass(frozen=True)
class RankCompatibilitySelection:
    selected_vehicle_ids: tuple[str, ...]
    selection_reason: str


class RankCompatibilityStrategy(Protocol):
    mode_name: str

    def select(
        self,
        *,
        base_vehicle_ids: set[str],
        country_id: str,
        branch_id: str,
        rank: int,
        required_count: int,
        progress: PlayerProgress,
        options: SolveOptions,
        allow_req_unlock: bool,
    ) -> RankCompatibilitySelection: ...

    def sort_vehicle_ids(self, vehicle_ids: Iterable[str]) -> tuple[str, ...]: ...


class LegacyRankCompatibilityStrategy:
    """Quarantined compatibility bridge for the existing deterministic rank choice.

    The graph resolver itself does not calculate or emit RP, GE or SL. This bridge
    delegates only the missing rank-set selection to the unchanged, cost-aware legacy
    implementation so Shadow Mode can compare complete prerequisite sets before a
    future optimizer owns that responsibility.
    """

    mode_name = "legacy_rank_compatibility"

    def __init__(self, database: VehicleDatabase) -> None:
        self.database = database
        self._solver = ResearchSolver(database)

    def select(
        self,
        *,
        base_vehicle_ids: set[str],
        country_id: str,
        branch_id: str,
        rank: int,
        required_count: int,
        progress: PlayerProgress,
        options: SolveOptions,
        allow_req_unlock: bool,
    ) -> RankCompatibilitySelection:
        selected = self._solver._find_minimum_rank_additions(
            base=set(base_vehicle_ids),
            country_id=country_id,
            branch_id=branch_id,
            rank=rank,
            required_count=required_count,
            progress=progress,
            options=options,
            allow_req_unlock=allow_req_unlock,
        )
        return RankCompatibilitySelection(
            selected_vehicle_ids=self.sort_vehicle_ids(selected),
            selection_reason=(
                "Selected by the quarantined legacy rank-compatibility algorithm; "
                "this is not graph optimizer output."
            ),
        )

    def sort_vehicle_ids(self, vehicle_ids: Iterable[str]) -> tuple[str, ...]:
        return tuple(sorted(set(vehicle_ids), key=self._solver._vehicle_sort_key))


@dataclass(frozen=True)
class RankRequirementResolution:
    rank: int
    required_count: int
    satisfied_count: int
    initial_missing_count: int
    missing_count: int
    candidate_vehicle_ids: tuple[str, ...]
    excluded_candidates: tuple[dict[str, str], ...]
    selected_vehicle_ids: tuple[str, ...]
    compatibility_mode: bool
    evidence: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "rank": self.rank,
            "required_count": self.required_count,
            "satisfied_count": self.satisfied_count,
            "initial_missing_count": self.initial_missing_count,
            "missing_count": self.missing_count,
            "candidate_vehicle_ids": list(self.candidate_vehicle_ids),
            "excluded_candidates": [_canonical(item) for item in self.excluded_candidates],
            "selected_vehicle_ids": list(self.selected_vehicle_ids),
            "compatibility_mode": self.compatibility_mode,
            "evidence": _canonical(self.evidence),
        }


@dataclass(frozen=True)
class FolderRequirementResolution:
    vehicle_id: str
    folder_ids: tuple[str, ...]
    relationship: str
    status: str
    evidence: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "vehicle_id": self.vehicle_id,
            "folder_ids": list(self.folder_ids),
            "relationship": self.relationship,
            "status": self.status,
            "evidence": _canonical(self.evidence),
        }


@dataclass(frozen=True)
class UnlockRequirementResolution:
    vehicle_id: str
    tokens: tuple[str, ...]
    classification: str
    status: str
    required_vehicle_ids: tuple[str, ...]
    evidence: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "vehicle_id": self.vehicle_id,
            "tokens": list(self.tokens),
            "classification": self.classification,
            "status": self.status,
            "required_vehicle_ids": list(self.required_vehicle_ids),
            "evidence": _canonical(self.evidence),
        }


@dataclass(frozen=True)
class PrerequisiteResolution:
    target_vehicle_id: str
    start_vehicle_id: str | None
    required_vehicle_ids: tuple[str, ...]
    satisfied_vehicle_ids: tuple[str, ...]
    blocking_rule_results: tuple[RuleEvaluation, ...]
    unresolved_rule_results: tuple[RuleEvaluation, ...]
    rank_requirements: tuple[RankRequirementResolution, ...]
    folder_requirements: tuple[FolderRequirementResolution, ...]
    unlock_requirements: tuple[UnlockRequirementResolution, ...]
    resolution_status: ResolutionStatus
    evidence: dict[str, Any]
    explanation_trace: tuple[str, ...]
    compatibility_mode: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "target_vehicle_id": self.target_vehicle_id,
            "start_vehicle_id": self.start_vehicle_id,
            "required_vehicle_ids": list(self.required_vehicle_ids),
            "satisfied_vehicle_ids": list(self.satisfied_vehicle_ids),
            "blocking_rule_results": [item.to_dict() for item in self.blocking_rule_results],
            "unresolved_rule_results": [item.to_dict() for item in self.unresolved_rule_results],
            "rank_requirements": [item.to_dict() for item in self.rank_requirements],
            "folder_requirements": [item.to_dict() for item in self.folder_requirements],
            "unlock_requirements": [item.to_dict() for item in self.unlock_requirements],
            "resolution_status": self.resolution_status.value,
            "evidence": _canonical(self.evidence),
            "explanation_trace": list(self.explanation_trace),
            "compatibility_mode": self.compatibility_mode,
        }


class GraphPrerequisiteResolver:
    def __init__(
        self,
        graph: ResearchGraph,
        *,
        rank_compatibility_strategy: RankCompatibilityStrategy | None = None,
    ) -> None:
        self.graph = graph
        self.evaluator = GraphRuleEvaluator(graph)
        self.rank_compatibility_strategy = rank_compatibility_strategy

    def resolve(
        self,
        *,
        target_vehicle_id: str,
        start_vehicle_id: str | None = None,
        progress: PlayerProgress | None = None,
        options: SolveOptions | None = None,
    ) -> PrerequisiteResolution:
        progress = progress or PlayerProgress()
        options = options or SolveOptions()
        trace: list[str] = [f"target={target_vehicle_id}"]
        unsupported: list[str] = []
        compatibility_selection_performed = False

        target = self._vehicle_node_or_none(target_vehicle_id)
        if target is None:
            return self._unsupported(
                target_vehicle_id,
                start_vehicle_id,
                f"Target vehicle {target_vehicle_id!r} is not represented in ResearchGraph.",
            )
        if start_vehicle_id and self._vehicle_node_or_none(start_vehicle_id) is None:
            return self._unsupported(
                target_vehicle_id,
                start_vehicle_id,
                f"Start vehicle {start_vehicle_id!r} is not represented in ResearchGraph.",
            )

        report = self.evaluator.evaluate(
            target_vehicle_id=target_vehicle_id,
            start_vehicle_id=start_vehicle_id,
            progress=progress,
            options=options,
        )
        for item in report.evaluations:
            trace.append(f"evaluation:{item.rule_id}={item.status.value}")

        blocking: list[RuleEvaluation] = []
        unresolved: list[RuleEvaluation] = []
        for rule_id in ("TARGET_VISIBILITY", "START_TREE_COMPATIBILITY"):
            rule = report.by_rule(rule_id)
            if rule.blocking and rule.status is not EvaluationStatus.SATISFIED:
                blocking.append(rule)

        predecessor = report.by_rule("PREDECESSOR_REQUIREMENTS")
        mandatory = tuple(predecessor.evidence.get("mandatoryVehicleIds", (target_vehicle_id,)))
        if predecessor.status is EvaluationStatus.UNRESOLVED:
            unresolved.append(predecessor)

        fulfilled = self._fulfilled_vehicle_ids(
            target,
            progress,
            options,
            start_vehicle_id,
        )
        player_or_start_fulfilled = set(fulfilled)
        required = {vehicle_id for vehicle_id in mandatory if vehicle_id not in fulfilled}
        if target_vehicle_id not in fulfilled:
            required.add(target_vehicle_id)
        if start_vehicle_id and options.include_start_vehicle:
            required.add(start_vehicle_id)
            fulfilled.discard(start_vehicle_id)
        trace.append(
            "predecessor:required=" + ",".join(self._sort_vehicle_ids(required))
        )

        folders: dict[str, FolderRequirementResolution] = {}
        unlocks: dict[str, UnlockRequirementResolution] = {}
        semantically_processed: set[str] = set()

        def process_vehicle_semantics(vehicle_ids: Iterable[str]) -> None:
            pending = list(self._sort_vehicle_ids(vehicle_ids))
            while pending:
                vehicle_id = pending.pop(0)
                if vehicle_id in semantically_processed:
                    continue
                semantically_processed.add(vehicle_id)
                node = self._vehicle_node_or_none(vehicle_id)
                if node is None:
                    unsupported.append(f"Required vehicle {vehicle_id!r} is absent from the graph.")
                    continue
                metadata = dict(node.metadata)
                if (
                    vehicle_id != target_vehicle_id
                    and metadata.get("hiddenResearch")
                    and not options.include_hidden_legacy
                ):
                    hidden_rule = _synthetic_rule(
                        "PREREQUISITE_VISIBILITY",
                        EvaluationStatus.UNRESOLVED,
                        (node.node_id,),
                        {
                            "vehicleId": vehicle_id,
                            "hiddenResearch": True,
                            "includeHiddenLegacy": False,
                        },
                        (
                            "A mandatory hiddenResearch prerequisite has no default "
                            "availability contract."
                        ),
                        blocking=True,
                    )
                    unresolved.append(hidden_rule)
                    trace.append(f"visibility:{vehicle_id}=unresolved")

                vehicle_report = self.evaluator.evaluate(
                    target_vehicle_id=vehicle_id,
                    progress=progress,
                    options=options,
                )
                folder_rule = vehicle_report.by_rule("FOLDER_MEMBERSHIP")
                if folder_rule.status is not EvaluationStatus.NOT_APPLICABLE:
                    folder_ids = tuple(
                        sorted(
                            item.get("folderId", "")
                            for item in folder_rule.evidence.get("folders", ())
                            if item.get("folderId")
                        )
                    )
                    if vehicle_id in fulfilled:
                        relationship = "satisfied_member"
                        folder_status = EvaluationStatus.SATISFIED
                    elif vehicle_id == target_vehicle_id:
                        relationship = "membership_only"
                        folder_status = folder_rule.status
                    else:
                        relationship = "required_member"
                        folder_status = folder_rule.status
                    folders[vehicle_id] = FolderRequirementResolution(
                        vehicle_id=vehicle_id,
                        folder_ids=folder_ids,
                        relationship=relationship,
                        status=folder_status.value,
                        evidence=_canonical(
                            {
                                **folder_rule.evidence,
                                "sourceRuleStatus": folder_rule.status.value,
                                "fulfilledVehicleOverridesEligibility": vehicle_id in fulfilled,
                            }
                        ),
                    )
                    trace.append(
                        f"folder:{vehicle_id}={relationship}/{folder_status.value}"
                    )
                    if (
                        folder_rule.status is EvaluationStatus.UNRESOLVED
                        and vehicle_id not in fulfilled
                    ):
                        unresolved.append(folder_rule)

                unlock_rule = vehicle_report.by_rule("UNLOCK_REQUIREMENT")
                if unlock_rule.status is EvaluationStatus.NOT_APPLICABLE:
                    continue
                classification = str(unlock_rule.evidence.get("classification") or "unknown")
                tokens = tuple(sorted(unlock_rule.evidence.get("tokens", ())))
                internal_required: set[str] = set()
                unlock_status = unlock_rule.status
                unlock_evidence = dict(unlock_rule.evidence)
                if vehicle_id in fulfilled:
                    classification = UnlockClassification.FULFILLED_BY_PROGRESS.value
                    unlock_status = EvaluationStatus.SATISFIED
                    unlock_evidence.update(
                        {
                            "sourceRuleStatus": unlock_rule.status.value,
                            "fulfilledVehicleId": vehicle_id,
                        }
                    )
                elif classification == UnlockClassification.INTERNALLY_RESOLVABLE.value:
                    fulfilled_internal_ids: list[str] = []
                    for token in tokens:
                        internal_id = token.removeprefix("vehicle:")
                        if internal_id in fulfilled:
                            fulfilled_internal_ids.append(internal_id)
                            continue
                        try:
                            closure = self.graph.predecessor_closure(internal_id)
                        except Exception as exc:
                            unresolved_rule = _synthetic_rule(
                                "UNLOCK_INTERNAL_PREREQUISITE",
                                EvaluationStatus.UNRESOLVED,
                                (node.node_id,),
                                {"token": token, "error": str(exc)},
                                "The internal unlock prerequisite cannot be traversed uniquely.",
                                blocking=True,
                            )
                            unresolved.append(unresolved_rule)
                            continue
                        additions = {item for item in closure if item not in fulfilled}
                        internal_required.update(additions)
                        new_ids = additions - required
                        required.update(additions)
                        pending.extend(self._sort_vehicle_ids(new_ids))
                        pending = list(self._sort_vehicle_ids(pending))
                    if fulfilled_internal_ids and not internal_required:
                        unlock_status = EvaluationStatus.SATISFIED
                        unlock_evidence.update(
                            {
                                "sourceRuleStatus": unlock_rule.status.value,
                                "fulfilledInternalVehicleIds": sorted(
                                    fulfilled_internal_ids
                                ),
                            }
                        )
                elif unlock_status is EvaluationStatus.UNRESOLVED:
                    unresolved.append(unlock_rule)
                elif unlock_status is EvaluationStatus.UNSATISFIED:
                    blocking.append(unlock_rule)
                unlocks[vehicle_id] = UnlockRequirementResolution(
                    vehicle_id=vehicle_id,
                    tokens=tokens,
                    classification=classification,
                    status=(
                        "required"
                        if internal_required
                        else unlock_status.value
                    ),
                    required_vehicle_ids=self._sort_vehicle_ids(internal_required),
                    evidence=_canonical(unlock_evidence),
                )
                trace.append(
                    f"unlock:{vehicle_id}={classification}/{unlocks[vehicle_id].status}"
                )

        semantic_vehicle_ids = {
            target_vehicle_id,
            *required,
            *(fulfilled & set(mandatory)),
        }
        if start_vehicle_id:
            semantic_vehicle_ids.add(start_vehicle_id)
        process_vehicle_semantics(semantic_vehicle_ids)

        reserves = {
            node.entity_id
            for node in self._vehicle_nodes()
            if node.country_id == target.country_id
            and node.branch_id == target.branch_id
            and dict(node.metadata).get("reserve")
        }
        rank_base_fulfilled = player_or_start_fulfilled | reserves
        satisfied_for_result = fulfilled | reserves
        ranks: list[RankRequirementResolution] = []
        if not blocking and predecessor.status is not EvaluationStatus.UNRESOLVED:
            rank_nodes = {
                int(dict(node.metadata).get("sourceRank", -1)): node
                for node in self.graph.nodes
                if node.node_type is NodeType.RANK
                and node.country_id == target.country_id
                and node.branch_id == target.branch_id
            }
            target_rank = int(dict(target.metadata).get("rank", 0))
            first_rank = 1
            if start_vehicle_id:
                start = self._vehicle_node_or_none(start_vehicle_id)
                if start is not None:
                    first_rank = int(dict(start.metadata).get("rank", 1))

            for rank in range(first_rank, target_rank):
                rank_node = rank_nodes.get(rank)
                if rank_node is None:
                    continue
                required_count = int(dict(rank_node.metadata).get("requiredVehicles", 0))
                if required_count <= 0:
                    continue
                base = rank_base_fulfilled | required
                satisfied_count = self._count_rank(base, rank)
                initial_missing = max(required_count - satisfied_count, 0)
                candidates, excluded = self._rank_candidates(
                    target,
                    rank,
                    base,
                    progress,
                    options,
                )
                selected: tuple[str, ...] = ()
                selection_reason = "No selection was needed."
                if initial_missing:
                    if self.rank_compatibility_strategy is None:
                        unresolved.append(
                            _synthetic_rule(
                                f"RANK_SELECTION_REQUIRED_{rank}",
                                EvaluationStatus.UNRESOLVED,
                                (rank_node.node_id, target.node_id),
                                {
                                    "rank": rank,
                                    "requiredCount": required_count,
                                    "satisfiedCount": satisfied_count,
                                    "candidateVehicleIds": candidates,
                                    "selectionPerformed": False,
                                },
                                (
                                    "A rank combination is required, but no compatibility "
                                    "strategy was enabled."
                                ),
                                blocking=True,
                            )
                        )
                        selection_reason = "No rank selection strategy was enabled."
                    else:
                        compatibility_selection_performed = True
                        try:
                            selection = self.rank_compatibility_strategy.select(
                                base_vehicle_ids=set(base),
                                country_id=target.country_id or "",
                                branch_id=target.branch_id or "",
                                rank=rank,
                                required_count=required_count,
                                progress=progress,
                                options=options,
                                allow_req_unlock=(
                                    bool(start_vehicle_id) or bool(rank_base_fulfilled)
                                ),
                            )
                        except Exception as exc:
                            unsupported.append(
                                f"Rank {rank} compatibility selection failed: {exc}"
                            )
                            selection_reason = str(exc)
                        else:
                            selected = tuple(selection.selected_vehicle_ids)
                            selection_reason = selection.selection_reason
                            unknown = [
                                item
                                for item in selected
                                if self._vehicle_node_or_none(item) is None
                            ]
                            if unknown:
                                unsupported.append(
                                    f"Rank {rank} strategy selected unknown vehicles: {unknown!r}"
                                )
                            additions = set(selected) - rank_base_fulfilled
                            required.update(additions)
                            process_vehicle_semantics(additions)
                final_count = self._count_rank(rank_base_fulfilled | required, rank)
                missing = max(required_count - final_count, 0)
                if (
                    initial_missing
                    and self.rank_compatibility_strategy is not None
                    and missing
                ):
                    unsupported.append(
                        f"Rank {rank} compatibility selection leaves {missing} "
                        "requirement(s) missing."
                    )
                ranks.append(
                    RankRequirementResolution(
                        rank=rank,
                        required_count=required_count,
                        satisfied_count=satisfied_count,
                        initial_missing_count=initial_missing,
                        missing_count=missing,
                        candidate_vehicle_ids=candidates,
                        excluded_candidates=excluded,
                        selected_vehicle_ids=tuple(
                            item
                            for item in self._sort_vehicle_ids(selected)
                            if int(
                                dict(
                                    self.graph.node_map[
                                        ResearchGraph.vehicle_node_id(item)
                                    ].metadata
                                ).get("rank", 0)
                            )
                            == rank
                        ),
                        compatibility_mode=self.rank_compatibility_strategy is not None,
                        evidence={
                            "rankNodeId": rank_node.node_id,
                            "selectionReason": selection_reason,
                            "selectionPerformed": bool(selected),
                            "optimizerOutput": False,
                        },
                    )
                )
                trace.append(
                    f"rank:{rank}=required:{required_count},before:{satisfied_count},"
                    f"selected:{','.join(selected)},missing:{missing}"
                )

        unresolved = _unique_rules(unresolved)
        blocking.extend(item for item in unresolved if item.blocking)
        blocking = _unique_rules(blocking)
        deterministically_blocked = any(
            item.blocking and item.status is EvaluationStatus.UNSATISFIED
            for item in blocking
        )
        if unsupported:
            status = ResolutionStatus.UNSUPPORTED
        elif deterministically_blocked:
            status = ResolutionStatus.BLOCKED
        elif unresolved:
            status = ResolutionStatus.UNRESOLVED
        else:
            status = ResolutionStatus.RESOLVED
        trace.append(f"resolution={status.value}")

        required.difference_update(fulfilled)
        ordered_required = self._sort_vehicle_ids(required)
        ordered_satisfied = self._sort_vehicle_ids(satisfied_for_result - required)
        numbered_trace = tuple(f"{index:02d}:{item}" for index, item in enumerate(trace, 1))
        compatibility_mode = self.rank_compatibility_strategy is not None
        return PrerequisiteResolution(
            target_vehicle_id=target_vehicle_id,
            start_vehicle_id=start_vehicle_id,
            required_vehicle_ids=ordered_required,
            satisfied_vehicle_ids=ordered_satisfied,
            blocking_rule_results=tuple(blocking),
            unresolved_rule_results=tuple(unresolved),
            rank_requirements=tuple(ranks),
            folder_requirements=tuple(folders[key] for key in sorted(folders)),
            unlock_requirements=tuple(unlocks[key] for key in sorted(unlocks)),
            resolution_status=status,
            evidence={
                "gameVersion": self.graph.game_version,
                "mandatoryPredecessorVehicleIds": list(mandatory),
                "unsupportedReasons": sorted(set(unsupported)),
                "rankCompatibilityStrategy": (
                    self.rank_compatibility_strategy.mode_name
                    if self.rank_compatibility_strategy is not None
                    else None
                ),
                "graphCostCalculationPerformed": False,
                "costValuesEmitted": False,
                "legacyCompatibilityModeEnabled": compatibility_mode,
                "legacyCompatibilitySelectionPerformed": (
                    compatibility_selection_performed
                ),
                "optimizerSelectionPerformed": False,
            },
            explanation_trace=numbered_trace,
            compatibility_mode=compatibility_mode,
        )

    def _vehicle_node_or_none(self, vehicle_id: str) -> GraphNode | None:
        return self.graph.node_map.get(ResearchGraph.vehicle_node_id(vehicle_id))

    def _vehicle_nodes(self) -> tuple[GraphNode, ...]:
        return tuple(node for node in self.graph.nodes if node.node_type is NodeType.VEHICLE)

    def _fulfilled_vehicle_ids(
        self,
        target: GraphNode,
        progress: PlayerProgress,
        options: SolveOptions,
        start_vehicle_id: str | None,
    ) -> set[str]:
        result: set[str] = set()
        for vehicle_id, state in progress.vehicles.items():
            if not state.owned:
                continue
            node = self._vehicle_node_or_none(vehicle_id)
            if (
                node is None
                or node.country_id != target.country_id
                or node.branch_id != target.branch_id
            ):
                continue
            try:
                result.update(self.graph.predecessor_closure(vehicle_id))
            except Exception:
                result.add(vehicle_id)
        if start_vehicle_id:
            start = self._vehicle_node_or_none(start_vehicle_id)
            if (
                start is not None
                and start.country_id == target.country_id
                and start.branch_id == target.branch_id
            ):
                try:
                    closure = set(self.graph.predecessor_closure(start_vehicle_id))
                except Exception:
                    closure = {start_vehicle_id}
                if options.include_start_vehicle:
                    closure.discard(start_vehicle_id)
                result.update(closure)
        return result

    def _rank_candidates(
        self,
        target: GraphNode,
        rank: int,
        base: set[str],
        progress: PlayerProgress,
        options: SolveOptions,
    ) -> tuple[tuple[str, ...], tuple[dict[str, str], ...]]:
        candidates: list[str] = []
        excluded: list[dict[str, str]] = []
        for node in self._vehicle_nodes():
            metadata = dict(node.metadata)
            if (
                node.country_id != target.country_id
                or node.branch_id != target.branch_id
                or int(metadata.get("rank", 0)) != rank
                or node.entity_id in base
            ):
                continue
            if metadata.get("premium"):
                excluded.append({"vehicle_id": node.entity_id, "reason": "premium"})
            elif metadata.get("special"):
                excluded.append({"vehicle_id": node.entity_id, "reason": "special"})
            elif metadata.get("hiddenResearch") and not options.include_hidden_legacy:
                excluded.append({"vehicle_id": node.entity_id, "reason": "hiddenResearch"})
            elif reason := self._unlock_exclusion_reason(
                node,
                progress,
                options,
            ):
                excluded.append({"vehicle_id": node.entity_id, "reason": reason})
            else:
                closure_reason: str | None = None
                try:
                    closure = self.graph.predecessor_closure(node.entity_id)
                except Exception:
                    closure_reason = "predecessor_graph_unresolved"
                else:
                    for predecessor_id in closure[:-1]:
                        if predecessor_id in base:
                            continue
                        predecessor = self._vehicle_node_or_none(predecessor_id)
                        if predecessor is None:
                            closure_reason = "predecessor_graph_unresolved"
                            break
                        predecessor_metadata = dict(predecessor.metadata)
                        if (
                            predecessor_metadata.get("hiddenResearch")
                            and not options.include_hidden_legacy
                        ):
                            closure_reason = "predecessor_hiddenResearch"
                            break
                        unlock_reason = self._unlock_exclusion_reason(
                            predecessor,
                            progress,
                            options,
                        )
                        if unlock_reason:
                            closure_reason = f"predecessor_{unlock_reason}"
                            break
                if closure_reason:
                    excluded.append(
                        {"vehicle_id": node.entity_id, "reason": closure_reason}
                    )
                else:
                    candidates.append(node.entity_id)
        return (
            self._sort_vehicle_ids(candidates),
            tuple(sorted(excluded, key=lambda item: (item["reason"], item["vehicle_id"]))),
        )

    def _unlock_exclusion_reason(
        self,
        node: GraphNode,
        progress: PlayerProgress,
        options: SolveOptions,
    ) -> str | None:
        token = str(dict(node.metadata).get("reqUnlock") or "")
        if not token:
            return None
        if token in progress.fulfilled_unlocks or options.assume_external_unlocks:
            return None
        if token.startswith("vehicle:"):
            internal_id = token.removeprefix("vehicle:")
            if self._vehicle_node_or_none(internal_id) is not None:
                return None
            return "reqUnlock_unknown"
        return "reqUnlock_unresolved"

    def _count_rank(self, vehicle_ids: set[str], rank: int) -> int:
        return sum(
            1
            for vehicle_id in vehicle_ids
            if (node := self._vehicle_node_or_none(vehicle_id)) is not None
            and int(dict(node.metadata).get("rank", 0)) == rank
        )

    def _sort_vehicle_ids(self, vehicle_ids: Iterable[str]) -> tuple[str, ...]:
        values = set(vehicle_ids)
        if self.rank_compatibility_strategy is not None:
            return self.rank_compatibility_strategy.sort_vehicle_ids(values)
        return tuple(sorted(values, key=self._graph_vehicle_sort_key))

    def _graph_vehicle_sort_key(self, vehicle_id: str) -> tuple[Any, ...]:
        node = self._vehicle_node_or_none(vehicle_id)
        if node is None:
            return (10_000, 10_000, 10_000.0, vehicle_id)
        metadata = dict(node.metadata)
        return (
            int(metadata.get("rank", 0)),
            int(metadata.get("column", 0)),
            float(metadata.get("order", 0.0)),
            vehicle_id,
        )

    def _unsupported(
        self,
        target_vehicle_id: str,
        start_vehicle_id: str | None,
        explanation: str,
    ) -> PrerequisiteResolution:
        return PrerequisiteResolution(
            target_vehicle_id=target_vehicle_id,
            start_vehicle_id=start_vehicle_id,
            required_vehicle_ids=(),
            satisfied_vehicle_ids=(),
            blocking_rule_results=(),
            unresolved_rule_results=(),
            rank_requirements=(),
            folder_requirements=(),
            unlock_requirements=(),
            resolution_status=ResolutionStatus.UNSUPPORTED,
            evidence={
                "gameVersion": self.graph.game_version,
                "unsupportedReasons": [explanation],
                "graphCostCalculationPerformed": False,
                "costValuesEmitted": False,
                "legacyCompatibilityModeEnabled": (
                    self.rank_compatibility_strategy is not None
                ),
                "legacyCompatibilitySelectionPerformed": False,
                "optimizerSelectionPerformed": False,
            },
            explanation_trace=(f"01:{explanation}", "02:resolution=unsupported"),
            compatibility_mode=self.rank_compatibility_strategy is not None,
        )


def _synthetic_rule(
    rule_id: str,
    status: EvaluationStatus,
    affected_node_ids: Iterable[str],
    evidence: dict[str, Any],
    explanation: str,
    *,
    blocking: bool,
) -> RuleEvaluation:
    return RuleEvaluation(
        rule_id=rule_id,
        status=status,
        affected_node_ids=tuple(sorted(set(affected_node_ids))),
        evidence=_canonical(evidence),
        explanation=explanation,
        source_edge_ids=(),
        blocking=blocking,
    )


def _unique_rules(rules: Iterable[RuleEvaluation]) -> list[RuleEvaluation]:
    by_payload = {
        (
            item.rule_id,
            item.status.value,
            item.affected_node_ids,
            item.source_edge_ids,
            item.explanation,
        ): item
        for item in rules
    }
    return [by_payload[key] for key in sorted(by_payload)]


def _canonical(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _canonical(value[key]) for key in sorted(value)}
    if isinstance(value, (set, frozenset)):
        return [_canonical(item) for item in sorted(value)]
    if isinstance(value, (list, tuple)):
        return [_canonical(item) for item in value]
    return value
