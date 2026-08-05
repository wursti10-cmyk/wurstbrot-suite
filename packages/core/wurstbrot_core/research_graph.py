from __future__ import annotations

import json
from collections import Counter, defaultdict, deque
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
    FOLDER_MEMBER = "folder_member"
    UNLOCK_REQUIREMENT = "unlock_requirement"
    RANK_REQUIREMENT = "rank_requirement"
    FOLDER = "folder_member"
    UNLOCK = "unlock_requirement"


class DiagnosticCategory(str, Enum):
    EXPECTED = "expected"
    ATTENTION = "attention"
    INVALID = "invalid"


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
            "metadata": _json_value(dict(self.metadata)),
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

    @property
    def edge_id(self) -> str:
        canonical = json.dumps(dict(self.metadata), ensure_ascii=False, sort_keys=True)
        suffix = sha256(canonical.encode("utf-8")).hexdigest()[:12]
        return f"{self.edge_type.value}:{self.source}->{self.target}:{suffix}"

    def sort_key(self) -> tuple[str, str, str, str]:
        return (
            self.edge_type.value,
            self.source,
            self.target,
            json.dumps(dict(self.metadata), ensure_ascii=False, sort_keys=True),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.edge_id,
            "source": self.source,
            "target": self.target,
            "type": self.edge_type.value,
            "metadata": _json_value(dict(self.metadata)),
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
    root_nodes_by_type: dict[str, int]
    leaf_nodes_by_type: dict[str, int]
    isolated_node_count: int
    isolated_nodes_by_type: dict[str, int]
    components_by_nation: dict[str, int]
    components_by_vehicle_type: dict[str, int]
    components_by_node_type: dict[str, int]
    components_by_vehicle_class: dict[str, int]
    components_without_regular_vehicle_root: int
    special_only_components: int
    diagnostic_categories: dict[str, str]

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
            "rootNodesByType": self.root_nodes_by_type,
            "leafNodesByType": self.leaf_nodes_by_type,
            "isolatedNodeCount": self.isolated_node_count,
            "isolatedNodesByType": self.isolated_nodes_by_type,
            "componentsByNation": self.components_by_nation,
            "componentsByVehicleType": self.components_by_vehicle_type,
            "componentsByNodeType": self.components_by_node_type,
            "componentsByVehicleClass": self.components_by_vehicle_class,
            "componentsWithoutRegularVehicleRoot": self.components_without_regular_vehicle_root,
            "specialOnlyComponents": self.special_only_components,
            "diagnosticCategories": self.diagnostic_categories,
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
        components = _components(self.nodes, self.edges)
        node_types = [item.value for item in NodeType]
        roots_by_type = {
            node_type: sum(
                indegree[node.node_id] == 0 and node.node_type.value == node_type
                for node in self.nodes
            )
            for node_type in node_types
        }
        leaves_by_type = {
            node_type: sum(
                outdegree[node.node_id] == 0 and node.node_type.value == node_type
                for node in self.nodes
            )
            for node_type in node_types
        }
        isolated = {
            node.node_id
            for node in self.nodes
            if indegree[node.node_id] == 0 and outdegree[node.node_id] == 0
        }
        component_statistics = _component_statistics(components, self.node_map, self._incoming)
        no_regular_root = component_statistics.pop("withoutRegularVehicleRoot")
        special_only = component_statistics.pop("specialOnly")
        return GraphDiagnostics(
            node_count=len(self.nodes),
            edge_count=len(self.edges),
            root_node_count=sum(value == 0 for value in indegree.values()),
            leaf_node_count=sum(value == 0 for value in outdegree.values()),
            vehicle_node_count=sum(node.node_type is NodeType.VEHICLE for node in self.nodes),
            folder_node_count=sum(node.node_type is NodeType.FOLDER for node in self.nodes),
            unlock_node_count=sum(node.node_type is NodeType.UNLOCK for node in self.nodes),
            rank_node_count=sum(node.node_type is NodeType.RANK for node in self.nodes),
            disconnected_components=len(components),
            cycles=cycles,
            longest_path=None if cycles else _longest_path(indegree, self._outgoing),
            average_branching_factor=round(
                len(self.edges) / non_leaf_count if non_leaf_count else 0.0,
                6,
            ),
            root_nodes_by_type=roots_by_type,
            leaf_nodes_by_type=leaves_by_type,
            isolated_node_count=len(isolated),
            isolated_nodes_by_type={
                node_type: sum(
                    node.node_id in isolated and node.node_type.value == node_type
                    for node in self.nodes
                )
                for node_type in node_types
            },
            components_by_nation=component_statistics["nation"],
            components_by_vehicle_type=component_statistics["vehicleType"],
            components_by_node_type=component_statistics["nodeType"],
            components_by_vehicle_class=component_statistics["vehicleClass"],
            components_without_regular_vehicle_root=no_regular_root,
            special_only_components=special_only,
            diagnostic_categories={
                "cycles": (
                    DiagnosticCategory.INVALID.value
                    if cycles
                    else DiagnosticCategory.EXPECTED.value
                ),
                "disconnectedComponents": DiagnosticCategory.EXPECTED.value,
                "isolatedNodes": (
                    DiagnosticCategory.ATTENTION.value
                    if isolated
                    else DiagnosticCategory.EXPECTED.value
                ),
                "componentsWithoutRegularVehicleRoot": (
                    DiagnosticCategory.ATTENTION.value
                    if no_regular_root
                    else DiagnosticCategory.EXPECTED.value
                ),
                "specialOnlyComponents": DiagnosticCategory.EXPECTED.value,
            },
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
                        ("premium", vehicle.premium),
                        ("special", vehicle.special),
                        ("hiddenResearch", vehicle.hidden_research),
                        ("reqUnlock", vehicle.req_unlock),
                        ("group", vehicle.group),
                        ("groupIndex", vehicle.group_index),
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

        for folder_id, declared_member_ids in database.raw_groups.items():
            folder_node_id = f"folder:{folder_id}"
            members = tuple(
                member_id for member_id in declared_member_ids if member_id in database.vehicles
            )
            missing_members = tuple(
                member_id for member_id in declared_member_ids if member_id not in database.vehicles
            )
            country_ids = sorted({database.get(member).country_id for member in members})
            branch_ids = sorted({database.get(member).branch_id for member in members})
            nodes.append(
                GraphNode(
                    node_id=folder_node_id,
                    node_type=NodeType.FOLDER,
                    entity_id=folder_id,
                    country_id=country_ids[0] if len(country_ids) == 1 else None,
                    branch_id=branch_ids[0] if len(branch_ids) == 1 else None,
                    metadata=(
                        ("memberCount", len(members)),
                        ("declaredMemberCount", len(declared_member_ids)),
                        ("missingMemberIds", missing_members),
                    ),
                )
            )
            edges.extend(
                GraphEdge(
                    source=folder_node_id,
                    target=ResearchGraph.vehicle_node_id(member_id),
                    edge_type=EdgeType.FOLDER_MEMBER,
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
                    edge_type=EdgeType.UNLOCK_REQUIREMENT,
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


def _components(
    nodes: Iterable[GraphNode], edges: Iterable[GraphEdge]
) -> tuple[frozenset[str], ...]:
    adjacent: defaultdict[str, set[str]] = defaultdict(set)
    for edge in edges:
        adjacent[edge.source].add(edge.target)
        adjacent[edge.target].add(edge.source)
    remaining = {node.node_id for node in nodes}
    components: list[frozenset[str]] = []
    while remaining:
        first = min(remaining)
        remaining.remove(first)
        members = {first}
        queue = [first]
        while queue:
            current = queue.pop()
            neighbours = adjacent[current] & remaining
            remaining.difference_update(neighbours)
            members.update(neighbours)
            queue.extend(neighbours)
        components.append(frozenset(members))
    return tuple(components)


def _component_statistics(
    components: Iterable[frozenset[str]],
    node_map: dict[str, GraphNode],
    incoming: dict[str, list[GraphEdge]],
) -> dict[str, Any]:
    nation: Counter[str] = Counter()
    vehicle_type: Counter[str] = Counter()
    node_type: Counter[str] = Counter()
    vehicle_class: Counter[str] = Counter()
    without_regular_root = 0
    special_only = 0

    for component in components:
        nodes = [node_map[node_id] for node_id in component]
        vehicles = [node for node in nodes if node.node_type is NodeType.VEHICLE]
        for value in {node.country_id for node in vehicles if node.country_id}:
            nation[value] += 1
        for value in {node.branch_id for node in vehicles if node.branch_id}:
            vehicle_type[value] += 1
        for value in {node.node_type.value for node in nodes}:
            node_type[value] += 1

        classes: set[str] = set()
        regular_roots = 0
        special_flags: list[bool] = []
        for vehicle in vehicles:
            metadata = dict(vehicle.metadata)
            is_special = bool(
                metadata.get("premium")
                or metadata.get("special")
                or metadata.get("hiddenResearch")
                or metadata.get("reqUnlock")
            )
            special_flags.append(is_special)
            if not is_special:
                classes.add("regular")
            for key in ("premium", "hiddenResearch", "reqUnlock", "reserve"):
                if metadata.get(key):
                    classes.add(key)
            predecessor_edges = [
                edge
                for edge in incoming.get(vehicle.node_id, ())
                if edge.edge_type is EdgeType.PREDECESSOR
            ]
            if not is_special and not predecessor_edges:
                regular_roots += 1
        for value in classes:
            vehicle_class[value] += 1
        if regular_roots == 0:
            without_regular_root += 1
        if vehicles and special_flags and all(special_flags):
            special_only += 1

    return {
        "nation": dict(sorted(nation.items())),
        "vehicleType": dict(sorted(vehicle_type.items())),
        "nodeType": dict(sorted(node_type.items())),
        "vehicleClass": {
            key: vehicle_class[key]
            for key in ("regular", "premium", "hiddenResearch", "reqUnlock", "reserve")
        },
        "withoutRegularVehicleRoot": without_regular_root,
        "specialOnly": special_only,
    }


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


def _json_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _json_value(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_json_value(item) for item in value]
    return value
