from __future__ import annotations

import json
from collections import defaultdict, deque
from dataclasses import dataclass
from enum import Enum
from hashlib import sha256
from pathlib import Path
from typing import Any, Iterable

from .database import DatabaseError, VehicleDatabase


class NodeType(str, Enum):
    VEHICLE = "vehicle"
    FOLDER = "folder"
    UNLOCK = "unlock"
    RANK = "rank"


class EdgeType(str, Enum):
    PREDECESSOR = "predecessor"
    FOLDER = "folder"
    UNLOCK = "unlock"
    RANK_REQUIREMENT = "rank_requirement"


@dataclass(frozen=True)
class GraphNode:
    node_id: str
    node_type: NodeType
    entity_id: str
    country_id: str | None = None
    branch_id: str | None = None
    metadata: tuple[tuple[str, Any], ...] = ()

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "id": self.node_id,
            "type": self.node_type.value,
            "entityId": self.entity_id,
            "metadata": dict(self.metadata),
        }
        if self.country_id is not None:
            result["countryId"] = self.country_id
        if self.branch_id is not None:
            result["branchId"] = self.branch_id
        return result


@dataclass(frozen=True)
class GraphEdge:
    source: str
    target: str
    edge_type: EdgeType
    metadata: tuple[tuple[str, Any], ...] = ()

    def sort_key(self) -> tuple[str, str, str, str]:
        return (
            self.edge_type.value,
            self.source,
            self.target,
            json.dumps(dict(self.metadata), ensure_ascii=False, sort_keys=True),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "target": self.target,
            "type": self.edge_type.value,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class GraphDiagnostics:
    node_count: int
    edge_count: int
    root_node_count: int
    leaf_node_count: int
    vehicle_node_count: int
    folder_node_count: int
    unlock_node_count: int
    rank_node_count: int
    disconnected_components: int
    cycles: int
    longest_path: int | None
    average_branching_factor: float

    @property
    def is_dag(self) -> bool:
        return self.cycles == 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "nodeCount": self.node_count,
            "edgeCount": self.edge_count,
            "rootNodeCount": self.root_node_count,
            "leafNodeCount": self.leaf_node_count,
            "vehicleNodeCount": self.vehicle_node_count,
            "folderNodeCount": self.folder_node_count,
            "unlockNodeCount": self.unlock_node_count,
            "rankNodeCount": self.rank_node_count,
            "disconnectedComponents": self.disconnected_components,
            "cycles": self.cycles,
            "isDag": self.is_dag,
            "longestPath": self.longest_path,
            "averageBranchingFactor": self.average_branching_factor,
        }


class ResearchGraph:
    """Immutable typed graph; it does not calculate research costs."""

    def __init__(
        self,
        *,
        game_version: str,
        nodes: Iterable[GraphNode],
        edges: Iterable[GraphEdge],
    ) -> None:
        ordered_nodes = tuple(sorted(nodes, key=lambda item: item.node_id))
        ordered_edges = tuple(sorted(edges, key=GraphEdge.sort_key))
        node_map = {node.node_id: node for node in ordered_nodes}
        if len(node_map) != len(ordered_nodes):
            raise ValueError("Graph node IDs must be unique.")
        for edge in ordered_edges:
            if edge.source not in node_map or edge.target not in node_map:
                raise ValueError(f"Graph edge references an unknown node: {edge}")

        self.game_version = game_version
        self.nodes = ordered_nodes
        self.edges = ordered_edges
        self.node_map = node_map
        self._incoming: defaultdict[str, list[GraphEdge]] = defaultdict(list)
        self._outgoing: defaultdict[str, list[GraphEdge]] = defaultdict(list)
        for edge in ordered_edges:
            self._incoming[edge.target].append(edge)
            self._outgoing[edge.source].append(edge)

    @staticmethod
    def vehicle_node_id(vehicle_id: str) -> str:
        return f"vehicle:{vehicle_id}"

    def incoming(self, node_id: str, edge_type: EdgeType | None = None) -> tuple[GraphEdge, ...]:
        return tuple(
            edge
            for edge in self._incoming.get(node_id, ())
            if edge_type is None or edge.edge_type is edge_type
        )

    def predecessor_closure(self, vehicle_id: str) -> tuple[str, ...]:
        """Return the legacy single-parent closure through graph edges."""
        result: list[str] = []
        seen: set[str] = set()
        current = self.vehicle_node_id(vehicle_id)
        if current not in self.node_map:
            raise DatabaseError(f"Unbekanntes Fahrzeug: {vehicle_id}")

        while True:
            if current in seen:
                raise DatabaseError(f"Zyklus beim Graphpfad zu {vehicle_id}")
            seen.add(current)
            result.append(self.node_map[current].entity_id)
            incoming = self.incoming(current, EdgeType.PREDECESSOR)
            if not incoming:
                break
            if len(incoming) > 1:
                raise DatabaseError(f"Mehrere Vorgänger für {self.node_map[current].entity_id}")
            current = incoming[0].source

        result.reverse()
        return tuple(result)

    def diagnostics(self) -> GraphDiagnostics:
        indegree = {node.node_id: len(self._incoming[node.node_id]) for node in self.nodes}
        outdegree = {node.node_id: len(self._outgoing[node.node_id]) for node in self.nodes}
        cycles = _cycle_component_count(self.nodes, self._outgoing)
        non_leaf_count = sum(value > 0 for value in outdegree.values())
        return GraphDiagnostics(
            node_count=len(self.nodes),
            edge_count=len(self.edges),
            root_node_count=sum(value == 0 for value in indegree.values()),
            leaf_node_count=sum(value == 0 for value in outdegree.values()),
            vehicle_node_count=sum(node.node_type is NodeType.VEHICLE for node in self.nodes),
            folder_node_count=sum(node.node_type is NodeType.FOLDER for node in self.nodes),
            unlock_node_count=sum(node.node_type is NodeType.UNLOCK for node in self.nodes),
            rank_node_count=sum(node.node_type is NodeType.RANK for node in self.nodes),
            disconnected_components=_component_count(self.nodes, self.edges),
            cycles=cycles,
            longest_path=None if cycles else _longest_path(indegree, self._outgoing),
            average_branching_factor=round(
                len(self.edges) / non_leaf_count if non_leaf_count else 0.0,
                6,
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schemaVersion": 1,
            "gameVersion": self.game_version,
            "nodes": [node.to_dict() for node in self.nodes],
            "edges": [edge.to_dict() for edge in self.edges],
            "diagnostics": self.diagnostics().to_dict(),
        }

    def write_json(self, path: str | Path) -> Path:
        output = Path(path)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps(self.to_dict(), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return output


class ResearchGraphBuilder:
    """Translate schema-v1 database structures into the parallel typed graph."""

    @classmethod
    def from_database(cls, database: VehicleDatabase) -> ResearchGraph:
        nodes: list[GraphNode] = []
        edges: list[GraphEdge] = []

        for vehicle in database.vehicles.values():
            nodes.append(
                GraphNode(
                    node_id=ResearchGraph.vehicle_node_id(vehicle.id),
                    node_type=NodeType.VEHICLE,
                    entity_id=vehicle.id,
                    country_id=vehicle.country_id,
                    branch_id=vehicle.branch_id,
                    metadata=(
                        ("rank", vehicle.rank),
                        ("reserve", vehicle.reserve),
                        ("hiddenResearch", vehicle.hidden_research),
                    ),
                )
            )

        for vehicle_id, predecessor_id in database.predecessors.items():
            if predecessor_id is not None:
                edges.append(
                    GraphEdge(
                        source=ResearchGraph.vehicle_node_id(predecessor_id),
                        target=ResearchGraph.vehicle_node_id(vehicle_id),
                        edge_type=EdgeType.PREDECESSOR,
                    )
                )

        for folder_id, member_ids in database.groups.items():
            folder_node_id = f"folder:{folder_id}"
            members = tuple(member_id for member_id in member_ids if member_id in database.vehicles)
            country_ids = sorted({database.get(member).country_id for member in members})
            branch_ids = sorted({database.get(member).branch_id for member in members})
            nodes.append(
                GraphNode(
                    node_id=folder_node_id,
                    node_type=NodeType.FOLDER,
                    entity_id=folder_id,
                    country_id=country_ids[0] if len(country_ids) == 1 else None,
                    branch_id=branch_ids[0] if len(branch_ids) == 1 else None,
                    metadata=(("memberCount", len(members)),),
                )
            )
            edges.extend(
                GraphEdge(
                    source=folder_node_id,
                    target=ResearchGraph.vehicle_node_id(member_id),
                    edge_type=EdgeType.FOLDER,
                    metadata=(("groupIndex", index),),
                )
                for index, member_id in enumerate(members)
            )

        unlock_nodes: dict[str, str] = {}
        for vehicle in database.vehicles.values():
            if not vehicle.req_unlock:
                continue
            unlock_node_id = unlock_nodes.setdefault(
                vehicle.req_unlock,
                f"unlock:{sha256(vehicle.req_unlock.encode('utf-8')).hexdigest()}",
            )
            edges.append(
                GraphEdge(
                    source=unlock_node_id,
                    target=ResearchGraph.vehicle_node_id(vehicle.id),
                    edge_type=EdgeType.UNLOCK,
                )
            )
        nodes.extend(
            GraphNode(
                node_id=node_id,
                node_type=NodeType.UNLOCK,
                entity_id=unlock,
                metadata=(("external", True),),
            )
            for unlock, node_id in unlock_nodes.items()
        )

        for country_id, branches in database.rank_unlock.items():
            if not isinstance(branches, dict):
                continue
            for branch_id, requirements in branches.items():
                if not isinstance(requirements, dict):
                    continue
                for source_rank_raw, required_raw in requirements.items():
                    try:
                        source_rank = int(source_rank_raw)
                        required = int(required_raw or 0)
                    except (TypeError, ValueError):
                        continue
                    rank_node_id = f"rank:{country_id}:{branch_id}:{source_rank}"
                    nodes.append(
                        GraphNode(
                            node_id=rank_node_id,
                            node_type=NodeType.RANK,
                            entity_id=f"{country_id}/{branch_id}/{source_rank}",
                            country_id=country_id,
                            branch_id=branch_id,
                            metadata=(
                                ("sourceRank", source_rank),
                                ("targetRank", source_rank + 1),
                                ("requiredVehicles", required),
                            ),
                        )
                    )
                    for vehicle in database.tree_vehicles(country_id, branch_id):
                        if vehicle.rank == source_rank + 1:
                            edges.append(
                                GraphEdge(
                                    source=rank_node_id,
                                    target=ResearchGraph.vehicle_node_id(vehicle.id),
                                    edge_type=EdgeType.RANK_REQUIREMENT,
                                    metadata=(("requiredVehicles", required),),
                                )
                            )

        return ResearchGraph(game_version=database.game_version, nodes=nodes, edges=edges)


def _component_count(nodes: Iterable[GraphNode], edges: Iterable[GraphEdge]) -> int:
    adjacent: defaultdict[str, set[str]] = defaultdict(set)
    for edge in edges:
        adjacent[edge.source].add(edge.target)
        adjacent[edge.target].add(edge.source)
    remaining = {node.node_id for node in nodes}
    components = 0
    while remaining:
        components += 1
        queue = [remaining.pop()]
        while queue:
            current = queue.pop()
            neighbours = adjacent[current] & remaining
            remaining.difference_update(neighbours)
            queue.extend(neighbours)
    return components


def _cycle_component_count(
    nodes: Iterable[GraphNode],
    outgoing: dict[str, list[GraphEdge]],
) -> int:
    index = 0
    indices: dict[str, int] = {}
    lowlinks: dict[str, int] = {}
    stack: list[str] = []
    on_stack: set[str] = set()
    cycles = 0

    def visit(node_id: str) -> None:
        nonlocal index, cycles
        indices[node_id] = index
        lowlinks[node_id] = index
        index += 1
        stack.append(node_id)
        on_stack.add(node_id)

        for edge in outgoing.get(node_id, ()):
            target = edge.target
            if target not in indices:
                visit(target)
                lowlinks[node_id] = min(lowlinks[node_id], lowlinks[target])
            elif target in on_stack:
                lowlinks[node_id] = min(lowlinks[node_id], indices[target])

        if lowlinks[node_id] != indices[node_id]:
            return
        component: list[str] = []
        while True:
            member = stack.pop()
            on_stack.remove(member)
            component.append(member)
            if member == node_id:
                break
        self_loop = any(edge.target == node_id for edge in outgoing.get(node_id, ()))
        if len(component) > 1 or self_loop:
            cycles += 1

    for node in nodes:
        if node.node_id not in indices:
            visit(node.node_id)
    return cycles


def _longest_path(
    indegree: dict[str, int],
    outgoing: dict[str, list[GraphEdge]],
) -> int:
    remaining = dict(indegree)
    queue = deque(sorted(node_id for node_id, degree in remaining.items() if degree == 0))
    distance = {node_id: 0 for node_id in remaining}
    while queue:
        current = queue.popleft()
        for edge in outgoing.get(current, ()):
            distance[edge.target] = max(distance[edge.target], distance[current] + 1)
            remaining[edge.target] -= 1
            if remaining[edge.target] == 0:
                queue.append(edge.target)
    return max(distance.values(), default=0)
