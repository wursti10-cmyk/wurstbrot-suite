from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Iterable

from .database import VehicleDatabase
from .economy import ALLOWED_SL_DISCOUNTS, apply_discount, ge_for_remaining_rp
from .graph_resolution import PrerequisiteResolution, ResolutionStatus
from .models import PlayerProgress, SolveOptions, Vehicle, VehicleProgress


class CostStatus(str, Enum):
    COMPLETE = "complete"
    PARTIAL = "partial"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True)
class GraphVehicleCostLine:
    vehicle_id: str
    reason: str
    total_rp: int
    researched_rp: int
    remaining_rp: int
    ge: int
    base_sl: int
    discounted_sl: int
    already_researched: bool
    already_purchased: bool
    cost_applicable: bool
    evidence: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "vehicle_id": self.vehicle_id,
            "reason": self.reason,
            "total_rp": self.total_rp,
            "researched_rp": self.researched_rp,
            "remaining_rp": self.remaining_rp,
            "ge": self.ge,
            "base_sl": self.base_sl,
            "discounted_sl": self.discounted_sl,
            "already_researched": self.already_researched,
            "already_purchased": self.already_purchased,
            "cost_applicable": self.cost_applicable,
            "evidence": _canonical(self.evidence),
        }


@dataclass(frozen=True)
class GraphCostResult:
    target_vehicle_id: str
    start_vehicle_id: str | None
    resolution_status: ResolutionStatus
    cost_status: CostStatus
    vehicle_cost_lines: tuple[GraphVehicleCostLine, ...]
    total_remaining_rp: int | None
    total_ge_before_owned: int | None
    owned_ge: int
    total_ge_after_owned: int | None
    total_sl: int | None
    convertible_rp_available: int | None
    convertible_rp_shortfall: int | None
    sl_discount_percent: int
    rp_per_ge: int
    incomplete_reason_codes: tuple[str, ...]
    partial_remaining_rp: int | None
    partial_ge_before_owned: int | None
    partial_sl: int | None
    warnings: tuple[str, ...]
    evidence: dict[str, Any]
    explanation_trace: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "target_vehicle_id": self.target_vehicle_id,
            "start_vehicle_id": self.start_vehicle_id,
            "resolution_status": self.resolution_status.value,
            "cost_status": self.cost_status.value,
            "vehicle_cost_lines": [item.to_dict() for item in self.vehicle_cost_lines],
            "total_remaining_rp": self.total_remaining_rp,
            "total_ge_before_owned": self.total_ge_before_owned,
            "owned_ge": self.owned_ge,
            "total_ge_after_owned": self.total_ge_after_owned,
            "total_sl": self.total_sl,
            "convertible_rp_available": self.convertible_rp_available,
            "convertible_rp_shortfall": self.convertible_rp_shortfall,
            "sl_discount_percent": self.sl_discount_percent,
            "rp_per_ge": self.rp_per_ge,
            "incomplete_reason_codes": list(self.incomplete_reason_codes),
            "partial_remaining_rp": self.partial_remaining_rp,
            "partial_ge_before_owned": self.partial_ge_before_owned,
            "partial_sl": self.partial_sl,
            "warnings": list(self.warnings),
            "evidence": _canonical(self.evidence),
            "explanation_trace": list(self.explanation_trace),
        }


class GraphCostEngine:
    """Deterministic cost projection over an existing prerequisite resolution.

    The engine never selects prerequisites. Complete totals are emitted only for a
    resolved prerequisite contract. Unresolved input may expose known line costs,
    but those values stay in the explicitly partial fields.
    """

    version = "1.0.0-shadow"

    def __init__(self, database: VehicleDatabase) -> None:
        self.database = database

    def calculate(
        self,
        resolution: PrerequisiteResolution,
        *,
        progress: PlayerProgress | None = None,
        options: SolveOptions | None = None,
    ) -> GraphCostResult:
        progress = progress or PlayerProgress()
        options = options or SolveOptions()
        trace = [
            f"target={resolution.target_vehicle_id}",
            f"resolution={resolution.resolution_status.value}",
        ]

        status_reason = {
            ResolutionStatus.BLOCKED: "RESOLUTION_BLOCKED",
            ResolutionStatus.UNRESOLVED: "RESOLUTION_UNRESOLVED",
            ResolutionStatus.UNSUPPORTED: "RESOLUTION_UNSUPPORTED",
        }.get(resolution.resolution_status)
        if resolution.resolution_status in {
            ResolutionStatus.BLOCKED,
            ResolutionStatus.UNSUPPORTED,
        }:
            return self._unavailable(
                resolution,
                progress,
                options,
                (status_reason,) if status_reason else (),
                trace,
            )

        validation_reasons = self._validate_inputs(resolution, progress, options)
        if validation_reasons:
            trace.extend(f"invalid={item}" for item in validation_reasons)
            return self._unavailable(
                resolution,
                progress,
                options,
                validation_reasons,
                trace,
            )

        warnings: list[str] = []
        lines = tuple(
            self._cost_line(
                vehicle_id,
                self.database.get(vehicle_id),
                progress.for_vehicle(vehicle_id),
                resolution,
                options,
                warnings,
            )
            for vehicle_id in resolution.required_vehicle_ids
        )
        for line in lines:
            trace.append(
                f"vehicle:{line.vehicle_id}=rp:{line.remaining_rp},"
                f"ge:{line.ge},sl:{line.discounted_sl}"
            )

        known_rp = sum(item.remaining_rp for item in lines)
        known_ge = sum(item.ge for item in lines)
        known_sl = sum(item.discounted_sl for item in lines)
        complete = resolution.resolution_status is ResolutionStatus.RESOLVED
        if complete:
            total_rp = known_rp
            total_ge = known_ge
            total_ge_after_owned = max(known_ge - progress.owned_ge, 0)
            total_sl = known_sl
            convertible_shortfall = (
                max(known_rp - progress.convertible_rp, 0)
                if progress.convertible_rp is not None
                else 0
            )
            partial_rp = None
            partial_ge = None
            partial_sl = None
            cost_status = CostStatus.COMPLETE
            reasons: tuple[str, ...] = ()
        else:
            total_rp = None
            total_ge = None
            total_ge_after_owned = None
            total_sl = None
            convertible_shortfall = None
            partial_rp = known_rp
            partial_ge = known_ge
            partial_sl = known_sl
            cost_status = CostStatus.PARTIAL
            reasons = (status_reason or "RESOLUTION_UNRESOLVED",)
            warnings.append(
                "Only costs for explicitly resolved vehicle lines are shown; totals are incomplete."
            )

        trace.append(f"cost_status={cost_status.value}")
        return GraphCostResult(
            target_vehicle_id=resolution.target_vehicle_id,
            start_vehicle_id=resolution.start_vehicle_id,
            resolution_status=resolution.resolution_status,
            cost_status=cost_status,
            vehicle_cost_lines=lines,
            total_remaining_rp=total_rp,
            total_ge_before_owned=total_ge,
            owned_ge=progress.owned_ge,
            total_ge_after_owned=total_ge_after_owned,
            total_sl=total_sl,
            convertible_rp_available=progress.convertible_rp,
            convertible_rp_shortfall=convertible_shortfall,
            sl_discount_percent=options.sl_discount_percent,
            rp_per_ge=self.database.rp_per_ge,
            incomplete_reason_codes=reasons,
            partial_remaining_rp=partial_rp,
            partial_ge_before_owned=partial_ge,
            partial_sl=partial_sl,
            warnings=tuple(sorted(set(warnings))),
            evidence=self._evidence(
                resolution,
                complete_totals=complete,
                partial_line_count=len(lines) if not complete else 0,
            ),
            explanation_trace=_numbered(trace),
        )

    def _validate_inputs(
        self,
        resolution: PrerequisiteResolution,
        progress: PlayerProgress,
        options: SolveOptions,
    ) -> tuple[str, ...]:
        reasons: set[str] = set()
        if not _positive_int(self.database.rp_per_ge):
            reasons.add("INVALID_RP_PER_GE")
        if (
            not isinstance(options.sl_discount_percent, int)
            or isinstance(options.sl_discount_percent, bool)
            or options.sl_discount_percent not in ALLOWED_SL_DISCOUNTS
        ):
            reasons.add("INVALID_SL_DISCOUNT")
        if not _nonnegative_int(progress.owned_ge):
            reasons.add("INVALID_OWNED_GE")
        if progress.convertible_rp is not None and not _nonnegative_int(
            progress.convertible_rp
        ):
            reasons.add("INVALID_CONVERTIBLE_RP")

        required = resolution.required_vehicle_ids
        if len(required) != len(set(required)):
            reasons.add("DUPLICATE_REQUIRED_VEHICLE")
        if set(required) & set(resolution.satisfied_vehicle_ids):
            reasons.add("REQUIRED_SATISFIED_OVERLAP")
        represented = set(required) | set(resolution.satisfied_vehicle_ids)
        if resolution.target_vehicle_id not in represented:
            reasons.add("TARGET_NOT_ACCOUNTED_FOR")

        for vehicle_id in (*required, *resolution.satisfied_vehicle_ids):
            vehicle = self.database.vehicles.get(vehicle_id)
            if vehicle is None:
                reasons.add("UNKNOWN_VEHICLE")
                continue
            if not _nonnegative_int(vehicle.rp):
                reasons.add("INVALID_VEHICLE_RP")
            if not _nonnegative_int(vehicle.sl):
                reasons.add("INVALID_VEHICLE_SL")

        for vehicle_id in required:
            vehicle = self.database.vehicles.get(vehicle_id)
            if vehicle is None or not _nonnegative_int(vehicle.rp):
                continue
            state = progress.for_vehicle(vehicle_id)
            if not _nonnegative_int(state.researched_rp):
                reasons.add("NEGATIVE_OR_INVALID_RESEARCHED_RP")
            elif state.researched_rp > vehicle.rp:
                reasons.add("RESEARCHED_RP_EXCEEDS_TOTAL")
            if not isinstance(state.researched, bool) or not isinstance(
                state.purchased, bool
            ):
                reasons.add("INVALID_PROGRESS_STATUS")
        return tuple(sorted(reasons))

    def _cost_line(
        self,
        vehicle_id: str,
        vehicle: Vehicle,
        state: VehicleProgress,
        resolution: PrerequisiteResolution,
        options: SolveOptions,
        warnings: list[str],
    ) -> GraphVehicleCostLine:
        cost_fulfilled = state.purchased or vehicle.reserve
        already_researched = (
            state.researched
            or state.purchased
            or vehicle.reserve
            or vehicle.rp == 0
            or state.researched_rp == vehicle.rp
        )
        effective_researched_rp = vehicle.rp if already_researched else state.researched_rp
        remaining_rp = 0 if cost_fulfilled or already_researched else (
            vehicle.rp - effective_researched_rp
        )
        ge = ge_for_remaining_rp(remaining_rp, self.database.rp_per_ge)
        discounted_sl = (
            0
            if cost_fulfilled
            else apply_discount(vehicle.sl, options.sl_discount_percent)
        )
        if vehicle.rp == 0:
            warnings.append(f"{vehicle_id}: zero RP is preserved from the database.")
        if vehicle.sl == 0:
            warnings.append(f"{vehicle_id}: zero SL is preserved from the database.")
        if vehicle.reserve:
            warnings.append(f"{vehicle_id}: reserve vehicle has no additional cost.")
        if vehicle.hidden_research:
            warnings.append(
                f"{vehicle_id}: hiddenResearch cost line uses explicit resolution evidence."
            )
        if vehicle.req_unlock:
            warnings.append(
                f"{vehicle_id}: reqUnlock acquisition itself has no numeric cost in this model."
            )
        return GraphVehicleCostLine(
            vehicle_id=vehicle_id,
            reason=self._reason_for(vehicle_id, resolution),
            total_rp=vehicle.rp,
            researched_rp=effective_researched_rp,
            remaining_rp=remaining_rp,
            ge=ge,
            base_sl=vehicle.sl,
            discounted_sl=discounted_sl,
            already_researched=already_researched,
            already_purchased=state.purchased,
            cost_applicable=remaining_rp > 0 or discounted_sl > 0,
            evidence={
                "inputResearchedRp": state.researched_rp,
                "researchedFlag": state.researched,
                "purchasedFlag": state.purchased,
                "reserve": vehicle.reserve,
                "zeroRp": vehicle.rp == 0,
                "zeroSl": vehicle.sl == 0,
                "individualGeRounding": True,
                "slDiscountAppliedPercent": options.sl_discount_percent,
                "unlockToken": vehicle.req_unlock or None,
            },
        )

    @staticmethod
    def _reason_for(
        vehicle_id: str,
        resolution: PrerequisiteResolution,
    ) -> str:
        if vehicle_id == resolution.target_vehicle_id:
            return "target"
        if vehicle_id == resolution.start_vehicle_id:
            return "start_vehicle"
        rank_ids = {
            item
            for requirement in resolution.rank_requirements
            for item in requirement.selected_vehicle_ids
        }
        if vehicle_id in rank_ids:
            return "rank_unlock"
        unlock_ids = {
            item
            for requirement in resolution.unlock_requirements
            for item in requirement.required_vehicle_ids
        }
        if vehicle_id in unlock_ids:
            return "unlock_requirement"
        return "direct_path"

    def _unavailable(
        self,
        resolution: PrerequisiteResolution,
        progress: PlayerProgress,
        options: SolveOptions,
        reasons: Iterable[str | None],
        trace: list[str],
    ) -> GraphCostResult:
        reason_codes = tuple(sorted({item for item in reasons if item}))
        trace.extend(f"incomplete={item}" for item in reason_codes)
        trace.append("cost_status=unavailable")
        return GraphCostResult(
            target_vehicle_id=resolution.target_vehicle_id,
            start_vehicle_id=resolution.start_vehicle_id,
            resolution_status=resolution.resolution_status,
            cost_status=CostStatus.UNAVAILABLE,
            vehicle_cost_lines=(),
            total_remaining_rp=None,
            total_ge_before_owned=None,
            owned_ge=progress.owned_ge,
            total_ge_after_owned=None,
            total_sl=None,
            convertible_rp_available=progress.convertible_rp,
            convertible_rp_shortfall=None,
            sl_discount_percent=options.sl_discount_percent,
            rp_per_ge=self.database.rp_per_ge,
            incomplete_reason_codes=reason_codes,
            partial_remaining_rp=None,
            partial_ge_before_owned=None,
            partial_sl=None,
            warnings=(),
            evidence=self._evidence(
                resolution,
                complete_totals=False,
                partial_line_count=0,
            ),
            explanation_trace=_numbered(trace),
        )

    def _evidence(
        self,
        resolution: PrerequisiteResolution,
        *,
        complete_totals: bool,
        partial_line_count: int,
    ) -> dict[str, Any]:
        return {
            "gameVersion": self.database.game_version,
            "costEngineVersion": self.version,
            "sourceResolutionStatus": resolution.resolution_status.value,
            "sourceResolutionCompatibilityMode": resolution.compatibility_mode,
            "sourceResolutionEvidence": resolution.evidence,
            "sourceResolutionTrace": list(resolution.explanation_trace),
            "sourceBlockingRuleIds": sorted(
                {item.rule_id for item in resolution.blocking_rule_results}
            ),
            "sourceUnresolvedRuleIds": sorted(
                {item.rule_id for item in resolution.unresolved_rule_results}
            ),
            "completeTotalsEmitted": complete_totals,
            "partialLineCount": partial_line_count,
            "ownedGeAppliedAfterVehicleSum": complete_totals,
            "ownedGeAppliedToPartialCosts": False,
            "individualGeRounding": True,
            "allowedSlDiscounts": sorted(ALLOWED_SL_DISCOUNTS),
            "crewCostsIncluded": False,
            "euroCostsIncluded": False,
            "gePackagesIncluded": False,
            "optimizerSelectionPerformed": False,
            "legacySolverModified": False,
        }


def _nonnegative_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _positive_int(value: Any) -> bool:
    return _nonnegative_int(value) and value > 0


def _numbered(trace: Iterable[str]) -> tuple[str, ...]:
    return tuple(f"{index:02d}:{item}" for index, item in enumerate(trace, 1))


def _canonical(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _canonical(value[key]) for key in sorted(value)}
    if isinstance(value, (set, frozenset)):
        return [_canonical(item) for item in sorted(value)]
    if isinstance(value, (list, tuple)):
        return [_canonical(item) for item in value]
    if isinstance(value, Enum):
        return value.value
    return value
