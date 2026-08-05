from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


@dataclass(frozen=True)
class Vehicle:
    id: str
    name: str
    country_id: str
    branch_id: str
    rank: int
    rp: int
    sl: int
    reserve: bool = False
    premium: bool = False
    special: bool = False
    hidden_research: bool = False
    req_unlock: str = ""
    group: str | None = None
    group_index: int = 0
    column: int = 0
    order: float = 0.0


@dataclass
class VehicleProgress:
    researched_rp: int = 0
    researched: bool = False
    purchased: bool = False

    @property
    def owned(self) -> bool:
        return self.researched and self.purchased


@dataclass
class PlayerProgress:
    vehicles: dict[str, VehicleProgress] = field(default_factory=dict)
    convertible_rp: int | None = None
    owned_ge: int = 0

    def for_vehicle(self, vehicle_id: str) -> VehicleProgress:
        return self.vehicles.get(vehicle_id, VehicleProgress())


@dataclass(frozen=True)
class SolveOptions:
    optimize_for: Literal["ge", "rp", "sl", "vehicles"] = "ge"
    include_start_vehicle: bool = False
    include_hidden_legacy: bool = False
    sl_discount_percent: int = 0


@dataclass(frozen=True)
class VehicleCostLine:
    vehicle_id: str
    name: str
    reason: Literal["direct_path", "rank_unlock", "start_vehicle"]
    total_rp: int
    researched_rp: int
    remaining_rp: int
    ge: int
    sl: int
    already_owned: bool


@dataclass(frozen=True)
class RankRequirement:
    rank: int
    required: int
    available_before: int
    available_after: int
    added_vehicle_ids: tuple[str, ...]


@dataclass(frozen=True)
class SolveResult:
    start_vehicle_id: str | None
    target_vehicle_id: str
    vehicle_lines: tuple[VehicleCostLine, ...]
    rank_requirements: tuple[RankRequirement, ...]
    required_vehicle_ids: tuple[str, ...]
    total_rp: int
    total_ge_before_owned: int
    total_ge_after_owned: int
    total_sl: int
    convertible_rp_shortfall: int
    warnings: tuple[str, ...]
