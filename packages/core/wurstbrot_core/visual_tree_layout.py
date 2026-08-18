from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from typing import Iterable

from .database import DatabaseError, VehicleDatabase
from .models import SolveResult, Vehicle


LAYOUT_CONTRACT_VERSION = "visual-tech-tree-layout-v1"
HIGHLIGHT_CONTRACT_VERSION = "visual-tech-tree-highlight-v1"


FIELD_EVIDENCE = {
    "nation": {
        "classification": "A",
        "source": "normalized vehicles.countryId",
        "confidence": "direct",
    },
    "vehicleType": {
        "classification": "A",
        "source": "shop country branch container via vehicles.branchId",
        "confidence": "direct",
    },
    "rank": {
        "classification": "A",
        "source": "normalized vehicles.rank",
        "confidence": "direct",
    },
    "column": {
        "classification": "B",
        "source": "zero-based index of the source shop range column",
        "confidence": "deterministic",
    },
    "order": {
        "classification": "B",
        "source": "source shop order within a column",
        "confidence": "deterministic",
    },
    "predecessor": {
        "classification": "B",
        "source": "normalized predecessors (explicit reqAir or deterministic source sequence)",
        "confidence": "deterministic",
    },
    "successors": {
        "classification": "B",
        "source": "reverse index of normalized predecessors",
        "confidence": "deterministic",
    },
    "folder": {
        "classification": "A",
        "source": "normalized groups from source shop folders",
        "confidence": "direct",
    },
    "groupIndex": {
        "classification": "B",
        "source": "zero-based member index in the source shop folder",
        "confidence": "deterministic",
    },
    "hiddenResearch": {
        "classification": "A",
        "source": "normalized vehicles.hiddenResearch",
        "confidence": "direct",
    },
    "reqUnlock": {
        "classification": "A",
        "source": "normalized vehicles.reqUnlock",
        "confidence": "direct",
    },
    "visualSlot": {
        "classification": "B",
        "source": "rank/column-local sort by normalized order and vehicle id",
        "confidence": "deterministic",
    },
}


def _vehicle_key(vehicle: Vehicle) -> tuple[int, int, float, str]:
    return (vehicle.rank, vehicle.column, vehicle.order, vehicle.id)


@dataclass(frozen=True)
class LayoutNode:
    vehicle_id: str
    name: str
    country_id: str
    branch_id: str
    rank: int
    column: int
    order: float
    visual_slot: int
    predecessor_id: str | None
    successor_ids: tuple[str, ...]
    group_id: str | None
    group_index: int
    hidden_research: bool
    req_unlock: str
    reserve: bool
    premium: bool
    special: bool


@dataclass(frozen=True)
class LayoutEdge:
    source_vehicle_id: str
    target_vehicle_id: str
    edge_type: str = "research_predecessor"
    evidence: str = "normalized_predecessors"


@dataclass(frozen=True)
class LayoutFolder:
    group_id: str
    declared_member_ids: tuple[str, ...]
    present_member_ids: tuple[str, ...]
    missing_member_ids: tuple[str, ...]
    complete_in_normalized_data: bool


@dataclass(frozen=True)
class VisualTreeLayout:
    contract_version: str
    game_version: str
    country_id: str
    branch_id: str
    flow_direction: str
    ranks: tuple[int, ...]
    columns: tuple[int, ...]
    nodes: tuple[LayoutNode, ...]
    edges: tuple[LayoutEdge, ...]
    folders: tuple[LayoutFolder, ...]
    evidence: dict[str, dict[str, str]]
    limitations: tuple[str, ...]
    fingerprint: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class VisualTreeHighlight:
    contract_version: str
    layout_fingerprint: str
    start_vehicle_id: str | None
    target_vehicle_id: str
    user_result_source: str
    calculation_status: str
    fallback_reason: str | None
    complete: bool
    node_states: dict[str, tuple[str, ...]]
    required_edge_ids: tuple[str, ...]
    unresolved_vehicle_ids: tuple[str, ...]
    unresolved_folder_ids: tuple[str, ...]
    fingerprint: str

    def to_dict(self) -> dict:
        return asdict(self)


def _fingerprint(payload: dict) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def build_visual_tree_layout(
    database: VehicleDatabase,
    *,
    country_id: str,
    branch_id: str,
) -> VisualTreeLayout:
    vehicles = database.tree_vehicles(country_id, branch_id)
    if not vehicles:
        raise DatabaseError(f"Leerer oder unbekannter Forschungsbaum: {country_id}/{branch_id}")

    vehicle_ids = {vehicle.id for vehicle in vehicles}
    successors: dict[str, list[str]] = {vehicle.id: [] for vehicle in vehicles}
    edges: list[LayoutEdge] = []
    for vehicle in vehicles:
        predecessor_id = database.predecessors.get(vehicle.id)
        if predecessor_id is None:
            continue
        if predecessor_id not in vehicle_ids:
            raise DatabaseError(
                f"Baumübergreifender Vorgänger in {country_id}/{branch_id}: "
                f"{predecessor_id} -> {vehicle.id}"
            )
        successors[predecessor_id].append(vehicle.id)
        edges.append(LayoutEdge(predecessor_id, vehicle.id))

    slot_by_id: dict[str, int] = {}
    for rank in sorted({vehicle.rank for vehicle in vehicles}):
        for column in sorted({vehicle.column for vehicle in vehicles}):
            members = sorted(
                (
                    vehicle
                    for vehicle in vehicles
                    if vehicle.rank == rank and vehicle.column == column
                ),
                key=lambda vehicle: (vehicle.order, vehicle.id),
            )
            for slot, vehicle in enumerate(members):
                slot_by_id[vehicle.id] = slot

    nodes = tuple(
        LayoutNode(
            vehicle_id=vehicle.id,
            name=vehicle.name,
            country_id=vehicle.country_id,
            branch_id=vehicle.branch_id,
            rank=vehicle.rank,
            column=vehicle.column,
            order=vehicle.order,
            visual_slot=slot_by_id[vehicle.id],
            predecessor_id=database.predecessors.get(vehicle.id),
            successor_ids=tuple(
                sorted(successors[vehicle.id], key=lambda item: _vehicle_key(database.get(item)))
            ),
            group_id=vehicle.group,
            group_index=vehicle.group_index,
            hidden_research=vehicle.hidden_research,
            req_unlock=vehicle.req_unlock,
            reserve=vehicle.reserve,
            premium=vehicle.premium,
            special=vehicle.special,
        )
        for vehicle in vehicles
    )

    folders: list[LayoutFolder] = []
    for group_id in sorted({vehicle.group for vehicle in vehicles if vehicle.group}):
        declared = tuple(database.raw_groups.get(group_id, ()))
        present = tuple(vehicle_id for vehicle_id in declared if vehicle_id in vehicle_ids)
        missing = tuple(vehicle_id for vehicle_id in declared if vehicle_id not in vehicle_ids)
        folders.append(
            LayoutFolder(
                group_id=group_id,
                declared_member_ids=declared,
                present_member_ids=present,
                missing_member_ids=missing,
                complete_in_normalized_data=not missing,
            )
        )

    base_payload = {
        "contract_version": LAYOUT_CONTRACT_VERSION,
        "game_version": database.game_version,
        "country_id": country_id,
        "branch_id": branch_id,
        "flow_direction": "top_to_bottom",
        "ranks": sorted({vehicle.rank for vehicle in vehicles}),
        "columns": sorted({vehicle.column for vehicle in vehicles}),
        "nodes": [asdict(node) for node in nodes],
        "edges": [
            asdict(edge)
            for edge in sorted(
                edges,
                key=lambda edge: (edge.target_vehicle_id, edge.source_vehicle_id),
            )
        ],
        "folders": [asdict(folder) for folder in folders],
        "evidence": FIELD_EVIDENCE,
        "limitations": [
            "premium_and_special_vehicles_are_filtered_by_the_existing_converter",
            "rankPosXY_and_fakeReqUnitPosXY_are_sparse_helicopter_metadata_"
            "and_not_layout_authority",
            "folder_membership_does_not_define_hidden_folder_acquisition_semantics",
            "reqUnlock_is_visible_evidence_and_never_an_invented_vehicle_edge",
        ],
    }
    return VisualTreeLayout(
        contract_version=LAYOUT_CONTRACT_VERSION,
        game_version=database.game_version,
        country_id=country_id,
        branch_id=branch_id,
        flow_direction="top_to_bottom",
        ranks=tuple(base_payload["ranks"]),
        columns=tuple(base_payload["columns"]),
        nodes=nodes,
        edges=tuple(
            sorted(edges, key=lambda edge: (edge.target_vehicle_id, edge.source_vehicle_id))
        ),
        folders=tuple(folders),
        evidence=FIELD_EVIDENCE,
        limitations=tuple(base_payload["limitations"]),
        fingerprint=_fingerprint(base_payload),
    )


def build_visual_tree_highlight(
    layout: VisualTreeLayout,
    result: SolveResult,
    *,
    user_result_source: str,
    calculation_status: str,
    fallback_reason: str | None = None,
    unresolved_vehicle_ids: Iterable[str] = (),
    unresolved_folder_ids: Iterable[str] = (),
) -> VisualTreeHighlight:
    nodes = {node.vehicle_id: node for node in layout.nodes}
    if result.target_vehicle_id not in nodes:
        raise ValueError("Das Solver-Ziel gehört nicht zum Layout.")
    if result.start_vehicle_id is not None and result.start_vehicle_id not in nodes:
        raise ValueError("Der Solver-Start gehört nicht zum Layout.")

    required = set(result.required_vehicle_ids)
    unknown_required = sorted(required - nodes.keys())
    if unknown_required:
        raise ValueError(f"Solver-Ergebnis enthält layoutfremde Fahrzeuge: {unknown_required}")

    line_reasons = {line.vehicle_id: line.reason for line in result.vehicle_lines}
    direct_path = {
        line.vehicle_id for line in result.vehicle_lines if line.reason == "direct_path"
    }
    path_nodes = set(direct_path)
    if result.start_vehicle_id is not None:
        path_nodes.add(result.start_vehicle_id)

    unresolved_vehicles = tuple(sorted(set(unresolved_vehicle_ids)))
    unknown_unresolved = sorted(set(unresolved_vehicles) - nodes.keys())
    if unknown_unresolved:
        raise ValueError(f"Unbekannte unresolved-Fahrzeuge: {unknown_unresolved}")
    unresolved_folders = tuple(sorted(set(unresolved_folder_ids)))
    known_folders = {folder.group_id for folder in layout.folders}
    unknown_folders = sorted(set(unresolved_folders) - known_folders)
    if unknown_folders:
        raise ValueError(f"Unbekannte unresolved-Folder: {unknown_folders}")

    node_states: dict[str, tuple[str, ...]] = {}
    for node in layout.nodes:
        states: list[str] = []
        if node.vehicle_id == result.start_vehicle_id:
            states.append("start_a")
        if node.vehicle_id == result.target_vehicle_id:
            states.append("target_b")
        reason = line_reasons.get(node.vehicle_id)
        if reason is not None:
            states.append(f"required_{reason}")
        else:
            states.append("not_required")
        if node.group_id:
            states.append("folder_member")
        if node.hidden_research:
            states.append("hidden_research")
        if node.vehicle_id in unresolved_vehicles or node.group_id in unresolved_folders:
            states.append("partial_unresolved")
        node_states[node.vehicle_id] = tuple(states)

    required_edge_ids = tuple(
        f"{edge.source_vehicle_id}->{edge.target_vehicle_id}"
        for edge in layout.edges
        if edge.source_vehicle_id in path_nodes and edge.target_vehicle_id in direct_path
    )
    complete = (
        calculation_status == "complete"
        and fallback_reason is None
        and not unresolved_vehicles
        and not unresolved_folders
    )
    base_payload = {
        "contract_version": HIGHLIGHT_CONTRACT_VERSION,
        "layout_fingerprint": layout.fingerprint,
        "start_vehicle_id": result.start_vehicle_id,
        "target_vehicle_id": result.target_vehicle_id,
        "user_result_source": user_result_source,
        "calculation_status": calculation_status,
        "fallback_reason": fallback_reason,
        "complete": complete,
        "node_states": node_states,
        "required_edge_ids": required_edge_ids,
        "unresolved_vehicle_ids": unresolved_vehicles,
        "unresolved_folder_ids": unresolved_folders,
    }
    return VisualTreeHighlight(
        contract_version=HIGHLIGHT_CONTRACT_VERSION,
        layout_fingerprint=layout.fingerprint,
        start_vehicle_id=result.start_vehicle_id,
        target_vehicle_id=result.target_vehicle_id,
        user_result_source=user_result_source,
        calculation_status=calculation_status,
        fallback_reason=fallback_reason,
        complete=complete,
        node_states=node_states,
        required_edge_ids=required_edge_ids,
        unresolved_vehicle_ids=unresolved_vehicles,
        unresolved_folder_ids=unresolved_folders,
        fingerprint=_fingerprint(base_payload),
    )
