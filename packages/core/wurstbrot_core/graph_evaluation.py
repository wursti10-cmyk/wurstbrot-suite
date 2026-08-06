from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from enum import Enum
from typing import Any, Iterable

from .models import PlayerProgress, SolveOptions
from .research_graph import EdgeType, GraphEdge, GraphNode, NodeType, ResearchGraph


class EvaluationStatus(str, Enum):
    SATISFIED = "satisfied"
    UNSATISFIED = "unsatisfied"
    NOT_APPLICABLE = "not_applicable"
    UNRESOLVED = "unresolved"


class UnlockClassification(str, Enum):
    INTERNALLY_RESOLVABLE = "internally_resolvable"
    FULFILLED_BY_PROGRESS = "fulfilled_by_progress"
    EXTERNAL_ASSUMED_SATISFIED = "external_assumed_satisfied"
    EXTERNAL_NOT_CHECKABLE = "external_not_checkable"
    UNKNOWN = "unknown"
    CONTRADICTORY = "contradictory"


@dataclass(frozen=True)
class RuleEvaluation:
    rule_id: str
    status: EvaluationStatus
    affected_node_ids: tuple[str, ...]
    evidence: dict[str, Any]
    explanation: str
    source_edge_ids: tuple[str, ...]
    blocking: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "status": self.status.value,
            "affected_node_ids": list(self.affected_node_ids),
            "evidence": _canonical(self.evidence),
            "explanation": self.explanation,
            "source_edge_ids": list(self.source_edge_ids),
            "blocking": self.blocking,
        }


@dataclass(frozen=True)
class GraphEvaluationReport:
    target_vehicle_id: str
    evaluations: tuple[RuleEvaluation, ...]

    @property
    def counts(self) -> dict[str, int]:
        counts = Counter(item.status.value for item in self.evaluations)
        return {status.value: counts[status.value] for status in EvaluationStatus}

    @property
    def blocking(self) -> bool:
        return any(
            item.blocking and item.status is not EvaluationStatus.SATISFIED
            for item in self.evaluations
        )

    def by_rule(self, rule_id: str) -> RuleEvaluation:
        return next(item for item in self.evaluations if item.rule_id == rule_id)

    def to_dict(self) -> dict[str, Any]:
        return {
            "targetVehicleId": self.target_vehicle_id,
            "counts": self.counts,
            "blocking": self.blocking,
            "evaluations": [item.to_dict() for item in self.evaluations],
        }


class GraphRuleEvaluator:
    version = "1.0.0-shadow"

    def __init__(self, graph: ResearchGraph) -> None:
        self.graph = graph

    def evaluate(
        self,
        *,
        target_vehicle_id: str,
        progress: PlayerProgress | None = None,
        options: SolveOptions | None = None,
        start_vehicle_id: str | None = None,
        assumed_external_unlocks: Iterable[str] = (),
    ) -> GraphEvaluationReport:
        progress = progress or PlayerProgress()
        options = options or SolveOptions()
        target = self._vehicle_node(target_vehicle_id)
        explicit_unlocks = set(assumed_external_unlocks)
        if options.assume_external_unlocks:
            explicit_unlocks.update(
                self.graph.node_map[edge.source].entity_id
                for edge in self.graph.incoming(
                    target.node_id, EdgeType.UNLOCK_REQUIREMENT
                )
            )
        fulfilled = self._fulfilled_vehicle_ids(target, progress, options, start_vehicle_id)
        predecessor = self._evaluate_predecessors(target, fulfilled)
        evaluations = [
            self._evaluate_visibility(target, options),
            self._evaluate_start(target, start_vehicle_id),
            predecessor,
            self._evaluate_folder(target, progress),
            self._evaluate_unlock(target, progress, frozenset(explicit_unlocks)),
        ]
        evaluations.extend(
            self._evaluate_ranks(
                target,
                fulfilled,
                predecessor.evidence.get("requiredVehicleIds", ()),
                options,
                start_vehicle_id,
            )
        )
        return GraphEvaluationReport(
            target_vehicle_id=target_vehicle_id,
            evaluations=tuple(evaluations),
        )

    def _evaluate_start(
        self, target: GraphNode, start_vehicle_id: str | None
    ) -> RuleEvaluation:
        if start_vehicle_id is None:
            return _evaluation(
                "START_TREE_COMPATIBILITY",
                EvaluationStatus.NOT_APPLICABLE,
                (target.node_id,),
                {"startVehicleId": None},
                "No start vehicle was supplied.",
            )
        start = self._vehicle_node(start_vehicle_id)
        compatible = (
            start.country_id == target.country_id
            and start.branch_id == target.branch_id
        )
        return _evaluation(
            "START_TREE_COMPATIBILITY",
            EvaluationStatus.SATISFIED if compatible else EvaluationStatus.UNSATISFIED,
            (start.node_id, target.node_id),
            {
                "startVehicleId": start.entity_id,
                "targetVehicleId": target.entity_id,
                "sameCountry": start.country_id == target.country_id,
                "sameVehicleType": start.branch_id == target.branch_id,
            },
            "Start and target are in the same research tree."
            if compatible
            else "Start and target must share country and vehicle type.",
            blocking=not compatible,
        )

    def _vehicle_node(self, vehicle_id: str) -> GraphNode:
        node_id = ResearchGraph.vehicle_node_id(vehicle_id)
        try:
            return self.graph.node_map[node_id]
        except KeyError as exc:
            raise ValueError(f"Unknown graph vehicle: {vehicle_id}") from exc

    def _vehicle_nodes(self) -> tuple[GraphNode, ...]:
        return tuple(node for node in self.graph.nodes if node.node_type is NodeType.VEHICLE)

    def _fulfilled_vehicle_ids(
        self,
        target: GraphNode,
        progress: PlayerProgress,
        options: SolveOptions,
        start_vehicle_id: str | None,
    ) -> set[str]:
        fulfilled: set[str] = set()
        for vehicle_id, state in progress.vehicles.items():
            if not state.owned:
                continue
            node = self.graph.node_map.get(ResearchGraph.vehicle_node_id(vehicle_id))
            if node and node.country_id == target.country_id and node.branch_id == target.branch_id:
                try:
                    fulfilled.update(self.graph.predecessor_closure(vehicle_id))
                except Exception:
                    fulfilled.add(vehicle_id)
        if start_vehicle_id:
            start = self._vehicle_node(start_vehicle_id)
            if start.country_id != target.country_id or start.branch_id != target.branch_id:
                return fulfilled
            try:
                start_closure = set(self.graph.predecessor_closure(start_vehicle_id))
                if options.include_start_vehicle:
                    start_closure.discard(start_vehicle_id)
                fulfilled.update(start_closure)
            except Exception:
                pass
        return fulfilled

    def _evaluate_visibility(self, target: GraphNode, options: SolveOptions) -> RuleEvaluation:
        hidden = bool(dict(target.metadata).get("hiddenResearch"))
        if not hidden:
            return _evaluation(
                "TARGET_VISIBILITY",
                EvaluationStatus.NOT_APPLICABLE,
                (target.node_id,),
                {"hiddenResearch": False},
                "The target is not marked hiddenResearch.",
            )
        satisfied = options.include_hidden_legacy
        return _evaluation(
            "TARGET_VISIBILITY",
            EvaluationStatus.SATISFIED if satisfied else EvaluationStatus.UNSATISFIED,
            (target.node_id,),
            {"hiddenResearch": True, "includeHiddenLegacy": satisfied},
            (
                "Hidden target access was explicitly enabled."
                if satisfied
                else "The legacy contract rejects hiddenResearch targets by default."
            ),
            blocking=not satisfied,
        )

    def _evaluate_predecessors(self, target: GraphNode, fulfilled: set[str]) -> RuleEvaluation:
        ordered: list[str] = []
        edges: list[GraphEdge] = []
        unresolved_edges: list[GraphEdge] = []
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(node_id: str) -> None:
            if node_id in visiting:
                unresolved_edges.extend(self.graph.incoming(node_id, EdgeType.PREDECESSOR))
                return
            if node_id in visited:
                return
            visiting.add(node_id)
            incoming = self.graph.incoming(node_id, EdgeType.PREDECESSOR)
            if len(incoming) > 1:
                unresolved_edges.extend(incoming)
            for edge in incoming:
                edges.append(edge)
                visit(edge.source)
            visiting.remove(node_id)
            visited.add(node_id)
            ordered.append(self.graph.node_map[node_id].entity_id)

        visit(target.node_id)
        affected = tuple(ResearchGraph.vehicle_node_id(item) for item in ordered)
        edge_ids = tuple(sorted({edge.edge_id for edge in edges}))
        if unresolved_edges:
            return _evaluation(
                "PREDECESSOR_REQUIREMENTS",
                EvaluationStatus.UNRESOLVED,
                affected,
                {
                    "mandatoryVehicleIds": ordered,
                    "conflictingEdgeIds": sorted(edge.edge_id for edge in unresolved_edges),
                },
                "Multiple predecessors or a cycle cannot be resolved without AND/OR semantics.",
                edge_ids,
                True,
            )
        required = tuple(
            item for item in ordered if item == target.entity_id or item not in fulfilled
        )
        missing_predecessors = tuple(item for item in ordered[:-1] if item not in fulfilled)
        if not edges:
            status = EvaluationStatus.NOT_APPLICABLE
            explanation = "The target is a predecessor root."
        elif missing_predecessors:
            status = EvaluationStatus.UNSATISFIED
            explanation = "One or more mandatory predecessors are not fulfilled."
        else:
            status = EvaluationStatus.SATISFIED
            explanation = "All mandatory predecessors are fulfilled."
        return _evaluation(
            "PREDECESSOR_REQUIREMENTS",
            status,
            affected,
            {
                "mandatoryVehicleIds": ordered,
                "fulfilledVehicleIds": sorted(set(ordered) & fulfilled),
                "missingPredecessorIds": missing_predecessors,
                "requiredVehicleIds": required,
            },
            explanation,
            edge_ids,
            bool(missing_predecessors),
        )

    def _evaluate_folder(self, target: GraphNode, progress: PlayerProgress) -> RuleEvaluation:
        incoming = self.graph.incoming(target.node_id, EdgeType.FOLDER_MEMBER)
        if not incoming:
            return _evaluation(
                "FOLDER_MEMBERSHIP",
                EvaluationStatus.NOT_APPLICABLE,
                (target.node_id,),
                {"folderIds": []},
                "The target is not a folder member.",
            )
        folder_nodes = [self.graph.node_map[edge.source] for edge in incoming]
        problems: list[str] = []
        evidence_folders: list[dict[str, Any]] = []
        target_metadata = dict(target.metadata)
        for edge, folder in zip(incoming, folder_nodes):
            folder_metadata = dict(folder.metadata)
            edge_index = dict(edge.metadata).get("groupIndex")
            missing = tuple(folder_metadata.get("missingMemberIds", ()))
            member_edges = [
                item
                for item in self.graph.edges
                if item.source == folder.node_id and item.edge_type is EdgeType.FOLDER_MEMBER
            ]
            hidden_members = sorted(
                self.graph.node_map[item.target].entity_id
                for item in member_edges
                if dict(self.graph.node_map[item.target].metadata).get("hiddenResearch")
            )
            contradictory_members = sorted(
                self.graph.node_map[item.target].entity_id
                for item in member_edges
                if dict(self.graph.node_map[item.target].metadata).get("groupIndex")
                != dict(item.metadata).get("groupIndex")
            )
            if missing:
                problems.append("missing_member")
            if hidden_members:
                problems.append("hidden_member_semantics")
            if contradictory_members:
                problems.append("contradictory_order")
            if target_metadata.get("group") not in (None, folder.entity_id):
                problems.append("conflicting_membership")
            if target_metadata.get("groupIndex") != edge_index:
                problems.append("contradictory_order")
            evidence_folders.append(
                {
                    "folderId": folder.entity_id,
                    "groupIndex": edge_index,
                    "memberCount": folder_metadata.get("memberCount", 0),
                    "missingMemberIds": missing,
                    "hiddenMemberIds": hidden_members,
                    "contradictoryMemberIds": contradictory_members,
                }
            )
        if len(incoming) > 1:
            problems.append("multiple_folders")
        status = EvaluationStatus.UNRESOLVED if problems else EvaluationStatus.SATISFIED
        return _evaluation(
            "FOLDER_MEMBERSHIP",
            status,
            tuple(sorted({target.node_id, *(edge.source for edge in incoming)})),
            {
                "folders": evidence_folders,
                "problems": sorted(set(problems)),
                "owned": progress.for_vehicle(target.entity_id).owned,
                "researchEffect": "none_beyond_predecessor_edges",
                "purchaseEffect": "none_proven",
                "rankEffect": "none",
                "costEffect": "none",
            },
            (
                "Folder membership is consistent and has no independent eligibility effect."
                if not problems
                else "Folder source data is ambiguous; no eligibility rule is inferred."
            ),
            tuple(edge.edge_id for edge in incoming),
            False,
        )

    def _evaluate_unlock(
        self,
        target: GraphNode,
        progress: PlayerProgress,
        assumed_external_unlocks: frozenset[str],
    ) -> RuleEvaluation:
        incoming = self.graph.incoming(target.node_id, EdgeType.UNLOCK_REQUIREMENT)
        if not incoming:
            return _evaluation(
                "UNLOCK_REQUIREMENT",
                EvaluationStatus.NOT_APPLICABLE,
                (target.node_id,),
                {"classification": None},
                "The target has no reqUnlock condition.",
            )
        tokens = tuple(sorted({self.graph.node_map[edge.source].entity_id for edge in incoming}))
        if len(tokens) > 1:
            classification = UnlockClassification.CONTRADICTORY
            status = EvaluationStatus.UNRESOLVED
            explanation = "Multiple different unlock conditions affect the same vehicle."
        else:
            token = tokens[0]
            internal_id = token.removeprefix("vehicle:")
            internal_node = self.graph.node_map.get(ResearchGraph.vehicle_node_id(internal_id))
            if internal_node is not None:
                classification = UnlockClassification.INTERNALLY_RESOLVABLE
                owned = progress.for_vehicle(internal_id).owned
                status = EvaluationStatus.SATISFIED if owned else EvaluationStatus.UNSATISFIED
                explanation = (
                    "The referenced internal vehicle is owned."
                    if owned
                    else "The referenced internal vehicle is not owned."
                )
            elif token in progress.fulfilled_unlocks:
                classification = UnlockClassification.FULFILLED_BY_PROGRESS
                status = EvaluationStatus.SATISFIED
                explanation = "PlayerProgress explicitly records the unlock as fulfilled."
            elif token in assumed_external_unlocks:
                classification = UnlockClassification.EXTERNAL_ASSUMED_SATISFIED
                status = EvaluationStatus.SATISFIED
                explanation = "The caller explicitly assumed the external unlock is fulfilled."
            elif _looks_external(token):
                classification = UnlockClassification.EXTERNAL_NOT_CHECKABLE
                status = EvaluationStatus.UNRESOLVED
                explanation = "The external unlock token has no observable PlayerProgress state."
            else:
                classification = UnlockClassification.UNKNOWN
                status = EvaluationStatus.UNRESOLVED
                explanation = "The unlock token has no defined internal or external semantics."
        return _evaluation(
            "UNLOCK_REQUIREMENT",
            status,
            tuple(sorted({target.node_id, *(edge.source for edge in incoming)})),
            {"classification": classification.value, "tokens": tokens},
            explanation,
            tuple(edge.edge_id for edge in incoming),
            status in {EvaluationStatus.UNSATISFIED, EvaluationStatus.UNRESOLVED},
        )

    def _evaluate_ranks(
        self,
        target: GraphNode,
        fulfilled: set[str],
        required_vehicle_ids: Iterable[str],
        options: SolveOptions,
        start_vehicle_id: str | None,
    ) -> list[RuleEvaluation]:
        target_rank = int(dict(target.metadata).get("rank", 0))
        first_rank = 1
        if start_vehicle_id:
            first_rank = int(dict(self._vehicle_node(start_vehicle_id).metadata).get("rank", 1))
        evaluations: list[RuleEvaluation] = []
        reserves = {
            node.entity_id
            for node in self._vehicle_nodes()
            if node.country_id == target.country_id
            and node.branch_id == target.branch_id
            and dict(node.metadata).get("reserve")
        }
        planned = fulfilled | reserves | set(required_vehicle_ids)
        rank_nodes = {
            int(dict(node.metadata).get("sourceRank", -1)): node
            for node in self.graph.nodes
            if node.node_type is NodeType.RANK
            and node.country_id == target.country_id
            and node.branch_id == target.branch_id
        }
        for rank in range(first_rank, target_rank):
            rank_node = rank_nodes.get(rank)
            if rank_node is None:
                continue
            required = int(dict(rank_node.metadata).get("requiredVehicles", 0))
            if required <= 0:
                continue
            existing: list[str] = []
            candidates: list[str] = []
            excluded: list[dict[str, str]] = []
            for node in self._vehicle_nodes():
                metadata = dict(node.metadata)
                if (
                    node.country_id != target.country_id
                    or node.branch_id != target.branch_id
                    or int(metadata.get("rank", 0)) != rank
                ):
                    continue
                vehicle_id = node.entity_id
                if vehicle_id in planned:
                    existing.append(vehicle_id)
                elif metadata.get("premium"):
                    excluded.append({"vehicleId": vehicle_id, "reason": "premium"})
                elif metadata.get("special"):
                    excluded.append({"vehicleId": vehicle_id, "reason": "special"})
                elif metadata.get("hiddenResearch") and not options.include_hidden_legacy:
                    excluded.append({"vehicleId": vehicle_id, "reason": "hiddenResearch"})
                elif metadata.get("reqUnlock"):
                    excluded.append({"vehicleId": vehicle_id, "reason": "reqUnlock_unresolved"})
                else:
                    candidates.append(vehicle_id)
            existing.sort()
            candidates.sort()
            excluded.sort(key=lambda item: (item["reason"], item["vehicleId"]))
            missing = max(required - len(existing), 0)
            status = EvaluationStatus.SATISFIED if missing == 0 else EvaluationStatus.UNSATISFIED
            source_edges = tuple(
                edge.edge_id
                for edge in self.graph.edges
                if edge.source == rank_node.node_id and edge.edge_type is EdgeType.RANK_REQUIREMENT
            )
            evaluations.append(
                _evaluation(
                    f"RANK_REQUIREMENT_{rank}",
                    status,
                    tuple(
                        sorted(
                            {
                                rank_node.node_id,
                                *(ResearchGraph.vehicle_node_id(item) for item in existing),
                            }
                        )
                    ),
                    {
                        "rank": rank,
                        "requiredVehicleCount": required,
                        "qualifyingVehicleIds": existing,
                        "missingVehicleCount": missing,
                        "candidateVehicleIds": candidates,
                        "excludedCandidates": excluded,
                        "selectionPerformed": False,
                    },
                    (
                        "The rank requirement is already satisfied."
                        if missing == 0
                        else (
                            "Additional qualifying vehicles are required; "
                            "no candidate is selected."
                        )
                    ),
                    source_edges,
                    missing > 0,
                )
            )
        if not evaluations:
            evaluations.append(
                _evaluation(
                    "RANK_REQUIREMENT",
                    EvaluationStatus.NOT_APPLICABLE,
                    (target.node_id,),
                    {"applicableRanks": []},
                    "No positive rank gate applies before the target.",
                )
            )
        return evaluations


def _looks_external(token: str) -> bool:
    return bool(re.fullmatch(r"(?:ch_heli_unlocked_.+|unlocked_.+|isr_.+_unlocked)", token))


def _canonical(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _canonical(value[key]) for key in sorted(value)}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_canonical(item) for item in value]
    return value


def _evaluation(
    rule_id: str,
    status: EvaluationStatus,
    affected_node_ids: Iterable[str],
    evidence: dict[str, Any],
    explanation: str,
    source_edge_ids: Iterable[str] = (),
    blocking: bool = False,
) -> RuleEvaluation:
    return RuleEvaluation(
        rule_id=rule_id,
        status=status,
        affected_node_ids=tuple(sorted(set(affected_node_ids))),
        evidence=_canonical(evidence),
        explanation=explanation,
        source_edge_ids=tuple(sorted(set(source_edge_ids))),
        blocking=blocking,
    )
