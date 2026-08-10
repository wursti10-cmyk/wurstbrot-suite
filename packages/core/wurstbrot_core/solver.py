from __future__ import annotations

from dataclasses import replace
from heapq import heappop, heappush
from itertools import count

from .database import DatabaseError, VehicleDatabase
from .economy import ALLOWED_SL_DISCOUNTS, apply_discount, ge_for_remaining_rp
from .models import (
    PlayerProgress,
    RankRequirement,
    SolveOptions,
    SolveResult,
    Vehicle,
    VehicleCostLine,
    VehicleProgress,
)


class SolveError(ValueError):
    pass


def _nonnegative_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


class ResearchSolver:
    def __init__(self, database: VehicleDatabase) -> None:
        self.db = database

    def solve(
        self,
        *,
        target_vehicle_id: str,
        start_vehicle_id: str | None = None,
        progress: PlayerProgress | None = None,
        options: SolveOptions | None = None,
    ) -> SolveResult:
        progress = progress or PlayerProgress()
        options = options or SolveOptions()

        self._validate_input_contract(progress, options)

        target = self.db.get(target_vehicle_id)
        start = self.db.get(start_vehicle_id) if start_vehicle_id else None

        if start and (
            start.country_id != target.country_id
            or start.branch_id != target.branch_id
        ):
            raise SolveError("Start und Ziel müssen im selben Forschungsbaum liegen.")

        if target.hidden_research and not options.include_hidden_legacy:
            raise SolveError(
                f"{target.name} ist ein ausgeblendetes Altbestandsfahrzeug."
            )

        direct_path = list(self.db.closure(target.id))

        # Vehicles marked owned imply their mandatory predecessors. Vehicle A may
        # be in another line of the same tree: owning A proves its own prerequisite
        # chain and all lower rank gates, but not the target line's predecessors.
        owned = self._expanded_owned(progress, target.country_id, target.branch_id)
        if start:
            start_closure = set(self.db.closure(start.id))
            if options.include_start_vehicle:
                owned.update(start_closure - {start.id})
            else:
                owned.update(start_closure)

        direct_required = [
            vehicle_id for vehicle_id in direct_path if vehicle_id not in owned
        ]
        owned.update(
            vehicle.id
            for vehicle in self.db.tree_vehicles(target.country_id, target.branch_id)
            if vehicle.reserve
        )

        required: set[str] = set(direct_required)
        reasons: dict[str, str] = {
            vehicle_id: "direct_path" for vehicle_id in direct_required
        }

        rank_requirements: list[RankRequirement] = []
        # If the player can already research/own vehicle A, all rank gates below
        # A's rank have necessarily been passed in-game. Rechecking them would
        # invent obsolete costs. A's own rank still matters when B is in a later rank.
        first_rank_to_check = start.rank if start else 1
        for rank in range(first_rank_to_check, target.rank):
            needed = self.db.rank_requirement(
                target.country_id, target.branch_id, rank
            )
            if needed <= 0:
                continue

            before_set = owned | required
            available_before = self._count_rank(before_set, rank)
            added: set[str] = set()

            if available_before < needed:
                added = self._find_minimum_rank_additions(
                    base=before_set,
                    country_id=target.country_id,
                    branch_id=target.branch_id,
                    rank=rank,
                    required_count=needed,
                    progress=progress,
                    options=options,
                    allow_req_unlock=bool(start) or bool(owned),
                )
                required.update(added)
                for vehicle_id in added:
                    reasons.setdefault(vehicle_id, "rank_unlock")

            available_after = self._count_rank(owned | required, rank)
            if available_after < needed:
                raise SolveError(
                    f"Rang {rank + 1} kann nicht geöffnet werden: "
                    f"{available_after}/{needed} Fahrzeuge."
                )

            rank_requirements.append(
                RankRequirement(
                    rank=rank,
                    required=needed,
                    available_before=available_before,
                    available_after=available_after,
                    added_vehicle_ids=tuple(
                        sorted(
                            (
                                vehicle_id
                                for vehicle_id in added
                                if self.db.get(vehicle_id).rank == rank
                            ),
                            key=self._vehicle_sort_key,
                        )
                    ),
                )
            )

        if start and options.include_start_vehicle:
            reasons[start.id] = "start_vehicle"
            required.add(start.id)

        ordered_required = sorted(required, key=self._vehicle_sort_key)
        lines: list[VehicleCostLine] = []
        warnings: list[str] = []

        for vehicle_id in ordered_required:
            vehicle = self.db.get(vehicle_id)
            vehicle_progress = progress.for_vehicle(vehicle_id)
            already_owned = vehicle_progress.owned or vehicle_id in owned

            researched_rp = vehicle_progress.researched_rp
            remaining_rp = 0 if already_owned else max(vehicle.rp - researched_rp, 0)
            ge = ge_for_remaining_rp(remaining_rp, self.db.rp_per_ge)
            sl = 0 if already_owned else apply_discount(
                vehicle.sl, options.sl_discount_percent
            )

            if vehicle.req_unlock:
                warnings.append(
                    f"{vehicle.name}: zusätzliche Freischaltung {vehicle.req_unlock}"
                )
            if vehicle.hidden_research:
                warnings.append(f"{vehicle.name}: Altbestandsfahrzeug")

            lines.append(
                VehicleCostLine(
                    vehicle_id=vehicle.id,
                    name=vehicle.name,
                    reason=reasons.get(vehicle_id, "rank_unlock"),
                    total_rp=vehicle.rp,
                    researched_rp=researched_rp,
                    remaining_rp=remaining_rp,
                    ge=ge,
                    sl=sl,
                    already_owned=already_owned,
                )
            )

        total_rp = sum(line.remaining_rp for line in lines)
        total_ge = sum(line.ge for line in lines)
        total_sl = sum(line.sl for line in lines)
        convertible_shortfall = (
            max(total_rp - progress.convertible_rp, 0)
            if progress.convertible_rp is not None
            else 0
        )

        return SolveResult(
            start_vehicle_id=start.id if start else None,
            target_vehicle_id=target.id,
            vehicle_lines=tuple(lines),
            rank_requirements=tuple(rank_requirements),
            required_vehicle_ids=tuple(line.vehicle_id for line in lines),
            total_rp=total_rp,
            total_ge_before_owned=total_ge,
            total_ge_after_owned=max(total_ge - progress.owned_ge, 0),
            total_sl=total_sl,
            convertible_rp_shortfall=convertible_shortfall,
            warnings=tuple(dict.fromkeys(warnings)),
        )

    def _expanded_owned(
        self,
        progress: PlayerProgress,
        country_id: str,
        branch_id: str,
    ) -> set[str]:
        result: set[str] = set()
        for vehicle_id, state in progress.vehicles.items():
            if not state.owned or vehicle_id not in self.db.vehicles:
                continue
            vehicle = self.db.get(vehicle_id)
            if vehicle.country_id == country_id and vehicle.branch_id == branch_id:
                result.update(self.db.closure(vehicle_id))
        return result

    def _count_rank(self, vehicle_ids: set[str], rank: int) -> int:
        return sum(
            1
            for vehicle_id in vehicle_ids
            if vehicle_id in self.db.vehicles
            and self.db.get(vehicle_id).rank == rank
        )

    def _vehicle_sort_key(self, vehicle_id: str) -> tuple:
        vehicle = self.db.get(vehicle_id)
        return (
            vehicle.rank,
            vehicle.column,
            vehicle.order,
            vehicle.id,
        )

    def _candidate_cost(
        self,
        vehicle_ids: set[str],
        base: set[str],
        progress: PlayerProgress,
        options: SolveOptions,
    ) -> tuple[int, int, int, tuple[str, ...]]:
        new_ids = vehicle_ids - base
        rp = 0
        ge = 0
        sl = 0

        for vehicle_id in new_ids:
            vehicle = self.db.get(vehicle_id)
            state = progress.for_vehicle(vehicle_id)
            if state.owned or vehicle.reserve:
                continue
            researched_rp = state.researched_rp
            remaining_rp = max(vehicle.rp - researched_rp, 0)
            rp += remaining_rp
            ge += ge_for_remaining_rp(remaining_rp, self.db.rp_per_ge)
            sl += apply_discount(vehicle.sl, options.sl_discount_percent)

        if options.optimize_for == "sl":
            primary = sl
        elif options.optimize_for == "vehicles":
            primary = len(new_ids)
        elif options.optimize_for == "rp":
            primary = rp
        else:
            primary = ge

        # Deterministic tie breakers.
        return (primary, ge, sl, tuple(sorted(new_ids)))

    def _validate_input_contract(
        self,
        progress: PlayerProgress,
        options: SolveOptions,
    ) -> None:
        """Enforce the evidence-backed version-1.0 user input contract."""
        if not isinstance(progress, PlayerProgress):
            raise SolveError("PlayerProgress ist ungültig.")
        if not _nonnegative_int(progress.owned_ge):
            raise SolveError("owned_ge muss eine nicht-negative Ganzzahl sein.")
        if progress.convertible_rp is not None and not _nonnegative_int(
            progress.convertible_rp
        ):
            raise SolveError(
                "convertible_rp muss null oder eine nicht-negative Ganzzahl sein."
            )
        if not isinstance(progress.fulfilled_unlocks, (set, frozenset)) or any(
            not isinstance(item, str) or not item
            for item in progress.fulfilled_unlocks
        ):
            raise SolveError(
                "fulfilled_unlocks darf nur nichtleere Zeichenketten enthalten."
            )
        if not isinstance(progress.vehicles, dict):
            raise SolveError("progress.vehicles muss eine Zuordnung sein.")

        for vehicle_id, state in sorted(
            progress.vehicles.items(), key=lambda item: str(item[0])
        ):
            if vehicle_id not in self.db.vehicles:
                raise SolveError(
                    f"PlayerProgress enthält ein unbekanntes Fahrzeug: {vehicle_id}"
                )
            if not isinstance(state, VehicleProgress):
                raise SolveError(
                    f"Ungültiger Fortschrittsstatus für {vehicle_id}."
                )
            vehicle = self.db.get(vehicle_id)
            if not _nonnegative_int(state.researched_rp):
                raise SolveError(
                    f"researched_rp für {vehicle_id} muss eine nicht-negative "
                    "Ganzzahl sein."
                )
            if state.researched_rp > vehicle.rp:
                raise SolveError(
                    f"researched_rp für {vehicle_id} überschreitet die Fahrzeug-RP."
                )
            if not isinstance(state.researched, bool) or not isinstance(
                state.purchased, bool
            ):
                raise SolveError(
                    f"researched und purchased für {vehicle_id} müssen boolesch sein."
                )
            if state.purchased and not state.researched:
                raise SolveError(
                    f"Ein gekauftes Fahrzeug muss als erforscht markiert sein: {vehicle_id}"
                )
            if state.researched and state.researched_rp != vehicle.rp:
                raise SolveError(
                    f"researched=True für {vehicle_id} erfordert exakt "
                    f"{vehicle.rp} researched_rp."
                )

        if not isinstance(options, SolveOptions):
            raise SolveError("SolveOptions ist ungültig.")
        if not isinstance(options.optimize_for, str) or options.optimize_for not in {
            "ge",
            "rp",
            "sl",
            "vehicles",
        }:
            raise SolveError("optimize_for muss ge, rp, sl oder vehicles sein.")
        for field_name in (
            "include_start_vehicle",
            "include_hidden_legacy",
            "assume_external_unlocks",
        ):
            if not isinstance(getattr(options, field_name), bool):
                raise SolveError(f"{field_name} muss boolesch sein.")
        if (
            not isinstance(options.sl_discount_percent, int)
            or isinstance(options.sl_discount_percent, bool)
            or options.sl_discount_percent not in ALLOWED_SL_DISCOUNTS
        ):
            raise SolveError("SL-Rabatt muss 0, 30 oder 50 Prozent betragen.")

    def _find_minimum_rank_additions(
        self,
        *,
        base: set[str],
        country_id: str,
        branch_id: str,
        rank: int,
        required_count: int,
        progress: PlayerProgress,
        options: SolveOptions,
        allow_req_unlock: bool,
    ) -> set[str]:
        candidates = [
            vehicle
            for vehicle in self.db.tree_vehicles(country_id, branch_id)
            if vehicle.rank == rank
            and vehicle.id not in base
            and (options.include_hidden_legacy or not vehicle.hidden_research)
            and (allow_req_unlock or not vehicle.req_unlock)
        ]

        if not candidates:
            return set()

        # Uniform-cost search over unique prerequisite closures.
        counter = count()
        heap: list[tuple[tuple, int, frozenset[str]]] = []
        start_state = frozenset()
        heappush(
            heap,
            (self._candidate_cost(set(), base, progress, options), next(counter), start_state),
        )
        visited: set[frozenset[str]] = set()

        # A safety limit prevents pathological explosion while keeping normal
        # War Thunder trees exact for the small number of vehicles needed per rank.
        max_states = 75_000
        processed = 0

        while heap:
            _, _, state = heappop(heap)
            if state in visited:
                continue
            visited.add(state)
            processed += 1
            if processed > max_states:
                raise SolveError(
                    "Rangoptimierung hat das Sicherheitslimit erreicht."
                )

            combined = base | set(state)
            if self._count_rank(combined, rank) >= required_count:
                return set(state)

            for candidate in candidates:
                if candidate.id in combined:
                    continue
                closure = {
                    vehicle_id
                    for vehicle_id in self.db.closure(candidate.id)
                    if vehicle_id not in base
                    and (
                        options.include_hidden_legacy
                        or not self.db.get(vehicle_id).hidden_research
                    )
                }
                next_state = frozenset(set(state) | closure)
                if next_state in visited:
                    continue
                heappush(
                    heap,
                    (
                        self._candidate_cost(
                            set(next_state), base, progress, options
                        ),
                        next(counter),
                        next_state,
                    ),
                )

        return set()
