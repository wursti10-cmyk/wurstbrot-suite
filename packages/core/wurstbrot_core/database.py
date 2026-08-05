from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from .models import Vehicle


class DatabaseError(ValueError):
    pass


class VehicleDatabase:
    def __init__(
        self,
        *,
        game_version: str,
        rp_per_ge: int,
        vehicles: dict[str, Vehicle],
        predecessors: dict[str, str | None],
        groups: dict[str, list[str]],
        rank_unlock: dict,
        raw_groups: dict[str, list[str]] | None = None,
    ) -> None:
        self.game_version = game_version
        self.rp_per_ge = rp_per_ge
        self.vehicles = vehicles
        self.predecessors = predecessors
        self.groups = groups
        self.raw_groups = raw_groups if raw_groups is not None else groups
        self.rank_unlock = rank_unlock

    @classmethod
    def from_json(cls, path: str | Path) -> "VehicleDatabase":
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        if raw.get("schemaVersion") != 1:
            raise DatabaseError(
                f"Nicht unterstützte schemaVersion: {raw.get('schemaVersion')!r}"
            )

        vehicles: dict[str, Vehicle] = {}
        for item in raw.get("vehicles", []):
            vehicle = Vehicle(
                id=item["id"],
                name=item.get("name", item["id"]),
                country_id=item["countryId"],
                branch_id=item["branchId"],
                rank=int(item["rank"]),
                rp=int(item.get("rp", 0)),
                sl=int(item.get("sl", 0)),
                reserve=bool(item.get("reserve", False)),
                premium=bool(item.get("premium", False)),
                special=bool(item.get("special", False)),
                hidden_research=bool(item.get("hiddenResearch", False)),
                req_unlock=str(item.get("reqUnlock") or ""),
                group=item.get("group"),
                group_index=int(item.get("groupIndex", 0) or 0),
                column=int(item.get("column", 0) or 0),
                order=float(item.get("order", 0) or 0),
            )
            if vehicle.id in vehicles:
                raise DatabaseError(f"Doppelte Fahrzeug-ID: {vehicle.id}")
            vehicles[vehicle.id] = vehicle

        predecessors = {
            vehicle_id: predecessor
            for vehicle_id, predecessor in raw.get("predecessors", {}).items()
            if vehicle_id in vehicles
        }
        for vehicle_id in vehicles:
            predecessors.setdefault(vehicle_id, None)

        invalid = [
            (vehicle_id, predecessor)
            for vehicle_id, predecessor in predecessors.items()
            if predecessor is not None and predecessor not in vehicles
        ]
        if invalid:
            raise DatabaseError(f"Ungültige Vorgänger: {invalid[:5]}")

        economy = raw.get("economy", {})
        rp_per_ge = int(economy.get("rpPerGE", 45))
        if rp_per_ge <= 0:
            raise DatabaseError("rpPerGE muss größer als 0 sein.")

        raw_groups = {
            str(key): list(values)
            for key, values in raw.get("groups", {}).items()
            if isinstance(values, list)
        }
        database = cls(
            game_version=str(raw.get("gameVersion", "unbekannt")),
            rp_per_ge=rp_per_ge,
            vehicles=vehicles,
            predecessors=predecessors,
            groups={
                key: [vehicle_id for vehicle_id in values if vehicle_id in vehicles]
                for key, values in raw_groups.items()
            },
            raw_groups=raw_groups,
            rank_unlock=raw.get("rankUnlock", {}),
        )
        database._validate_cycles()
        return database

    def _validate_cycles(self) -> None:
        for start in self.vehicles:
            seen: set[str] = set()
            current: str | None = start
            while current is not None:
                if current in seen:
                    raise DatabaseError(f"Zyklus im Forschungsgraph bei {current}")
                seen.add(current)
                current = self.predecessors.get(current)

    def get(self, vehicle_id: str) -> Vehicle:
        try:
            return self.vehicles[vehicle_id]
        except KeyError as exc:
            raise DatabaseError(f"Unbekanntes Fahrzeug: {vehicle_id}") from exc

    def closure(self, vehicle_id: str) -> tuple[str, ...]:
        result: list[str] = []
        seen: set[str] = set()
        current: str | None = vehicle_id
        while current is not None:
            if current in seen:
                raise DatabaseError(f"Zyklus beim Pfad zu {vehicle_id}")
            seen.add(current)
            result.append(current)
            current = self.predecessors.get(current)
        result.reverse()
        return tuple(result)

    def tree_vehicles(self, country_id: str, branch_id: str) -> tuple[Vehicle, ...]:
        return tuple(
            sorted(
                (
                    vehicle
                    for vehicle in self.vehicles.values()
                    if vehicle.country_id == country_id
                    and vehicle.branch_id == branch_id
                ),
                key=lambda vehicle: (
                    vehicle.rank,
                    vehicle.column,
                    vehicle.order,
                    vehicle.id,
                ),
            )
        )

    def rank_requirement(
        self, country_id: str, branch_id: str, rank: int
    ) -> int:
        return int(
            self.rank_unlock
            .get(country_id, {})
            .get(branch_id, {})
            .get(str(rank), 0)
            or 0
        )
