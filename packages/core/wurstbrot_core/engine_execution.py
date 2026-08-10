from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
from typing import Any, Literal, Mapping, cast

from .database import VehicleDatabase
from .dual_engine import (
    ComparisonStatus,
    DualEngineResult,
    DualEngineRunner,
    LegacyExecutionResult,
)
from .graph_cost import CostStatus, GraphVehicleCostLine
from .graph_pipeline import PipelineStatus, canonicalize, stable_fingerprint
from .models import (
    PlayerProgress,
    RankRequirement,
    SolveOptions,
    SolveResult,
    VehicleCostLine,
)
from .solver import ResearchSolver


class ExecutionMode(str, Enum):
    LEGACY = "legacy"
    SHADOW = "shadow"
    GRAPH_EXPERIMENTAL = "graph_experimental"


class ResultSource(str, Enum):
    LEGACY = "legacy"
    GRAPH = "graph"


class CalculationStatus(str, Enum):
    COMPLETE = "complete"
    PARTIAL = "partial"
    UNAVAILABLE = "unavailable"


class FallbackReason(str, Enum):
    GRAPH_FEATURE_DISABLED = "graph_feature_disabled"
    GRAPH_INTERNAL_ERROR = "graph_internal_error"
    GRAPH_UNAVAILABLE = "graph_unavailable"
    GRAPH_INVALID_INPUT = "graph_invalid_input"
    GRAPH_PARTIAL = "graph_partial"
    GRAPH_BLOCKED = "graph_blocked"
    COMPARISON_NOT_EXACT = "comparison_not_exact"
    ADAPTER_CONTRACT_VIOLATION = "adapter_contract_violation"


EXECUTION_FINGERPRINT_VERSION = "calculation-execution-v1"


@dataclass(frozen=True)
class EngineFeatureFlags:
    """Process-local flags. Nothing is persisted or enabled automatically."""

    graph_experimental_enabled: bool = False

    @classmethod
    def explicit_graph_experimental(cls) -> EngineFeatureFlags:
        return cls(graph_experimental_enabled=True)


class ExperimentalGraphDisabledError(ValueError):
    pass


class ResultAdapterContractError(ValueError):
    pass


@dataclass(frozen=True)
class CalculationExecutionResult:
    requested_mode: ExecutionMode
    result_source: ResultSource | None
    calculation_status: CalculationStatus
    result: SolveResult | None
    graph_status: PipelineStatus | None
    comparison_status: ComparisonStatus | None
    shadow_comparison_exists: bool
    fallback_applied: bool
    fallback_reason: FallbackReason | None
    experimental: bool
    diagnostics: dict[str, Any]
    fingerprint_version: str
    fingerprint: str

    def to_dict(self) -> dict[str, Any]:
        return {
            # Accuracy 8 review aliases keep the original Python API stable while
            # exposing the names required by the machine-readable execution contract.
            "requested_engine": self.requested_mode.value,
            "requested_mode": self.requested_mode.value,
            "result_source": (
                self.result_source.value if self.result_source is not None else None
            ),
            "calculation_status": self.calculation_status.value,
            "result": (
                serialize_solve_result(self.result) if self.result is not None else None
            ),
            "pipeline_status": (
                self.graph_status.value if self.graph_status is not None else None
            ),
            "graph_status": (
                self.graph_status.value if self.graph_status is not None else None
            ),
            "comparison_status": (
                self.comparison_status.value
                if self.comparison_status is not None
                else None
            ),
            "shadow_comparison_exists": self.shadow_comparison_exists,
            "fallback_used": self.fallback_applied,
            "fallback_applied": self.fallback_applied,
            "fallback_reason": (
                self.fallback_reason.value if self.fallback_reason is not None else None
            ),
            "experimental": self.experimental,
            "diagnostics": canonicalize(self.diagnostics),
            "fingerprint_version": self.fingerprint_version,
            "fingerprint": self.fingerprint,
        }


class GraphCalculationResultAdapter:
    """Map a complete graph result to the established user-facing SolveResult."""

    version = "1.0.0-experimental"

    _reason_mapping = {
        "target": "direct_path",
        "direct_path": "direct_path",
        "rank_unlock": "rank_unlock",
        "start_vehicle": "start_vehicle",
        "unlock_requirement": "direct_path",
    }

    def __init__(self, database: VehicleDatabase) -> None:
        self.database = database

    def adapt(self, dual_result: DualEngineResult) -> SolveResult:
        graph = dual_result.graph_result
        resolution = graph.prerequisite_resolution
        cost = graph.cost_result
        if graph.pipeline_status is not PipelineStatus.COMPLETE:
            raise ResultAdapterContractError("Graph pipeline is not complete.")
        if resolution is None or cost is None:
            raise ResultAdapterContractError("Complete graph result lacks components.")
        if cost.cost_status is not CostStatus.COMPLETE:
            raise ResultAdapterContractError("Graph cost result is not complete.")
        if any(
            value is None
            for value in (
                cost.total_remaining_rp,
                cost.total_ge_before_owned,
                cost.total_ge_after_owned,
                cost.total_sl,
                cost.convertible_rp_shortfall,
            )
        ):
            raise ResultAdapterContractError("Complete graph totals contain null.")
        legacy_payload = dual_result.legacy_result.result
        if dual_result.legacy_result.status != "complete" or legacy_payload is None:
            raise ResultAdapterContractError(
                "An exact complete graph result requires the compared Legacy result."
            )

        required_ids = resolution.required_vehicle_ids
        line_ids = tuple(item.vehicle_id for item in cost.vehicle_cost_lines)
        if len(required_ids) != len(set(required_ids)):
            raise ResultAdapterContractError("Required vehicle IDs are duplicated.")
        if required_ids != line_ids:
            raise ResultAdapterContractError(
                "Required vehicle order and cost-line order differ."
            )

        lines = tuple(self._vehicle_line(item) for item in cost.vehicle_cost_lines)
        rank_requirements = tuple(
            RankRequirement(
                rank=item.rank,
                required=item.required_count,
                available_before=item.satisfied_count,
                available_after=item.satisfied_count + len(item.selected_vehicle_ids),
                added_vehicle_ids=item.selected_vehicle_ids,
            )
            for item in resolution.rank_requirements
        )
        result = SolveResult(
            start_vehicle_id=resolution.start_vehicle_id,
            target_vehicle_id=resolution.target_vehicle_id,
            vehicle_lines=lines,
            rank_requirements=rank_requirements,
            required_vehicle_ids=required_ids,
            total_rp=cast(int, cost.total_remaining_rp),
            total_ge_before_owned=cast(int, cost.total_ge_before_owned),
            total_ge_after_owned=cast(int, cost.total_ge_after_owned),
            total_sl=cast(int, cost.total_sl),
            convertible_rp_shortfall=cast(int, cost.convertible_rp_shortfall),
            # Accuracy 8 does not introduce a new user Explain contract. Preserve the
            # established warning strings while all numeric and path values come from Graph.
            warnings=tuple(legacy_payload["warnings"]),
        )
        self._validate_result(result, cost.owned_ge)
        return result

    def _vehicle_line(self, item: GraphVehicleCostLine) -> VehicleCostLine:
        vehicle = self.database.vehicles.get(item.vehicle_id)
        if vehicle is None:
            raise ResultAdapterContractError(
                f"Unknown graph cost vehicle: {item.vehicle_id}"
            )
        reason = self._reason_mapping.get(item.reason)
        if reason is None:
            raise ResultAdapterContractError(
                f"Unsupported graph cost reason: {item.reason}"
            )
        return VehicleCostLine(
            vehicle_id=item.vehicle_id,
            name=vehicle.name,
            reason=cast(
                Literal["direct_path", "rank_unlock", "start_vehicle"],
                reason,
            ),
            total_rp=item.total_rp,
            researched_rp=item.researched_rp,
            remaining_rp=item.remaining_rp,
            ge=item.ge,
            sl=item.discounted_sl,
            already_owned=item.already_purchased or vehicle.reserve,
        )

    @staticmethod
    def _validate_result(result: SolveResult, owned_ge: int) -> None:
        if result.required_vehicle_ids != tuple(
            item.vehicle_id for item in result.vehicle_lines
        ):
            raise ResultAdapterContractError("Adapted vehicle IDs are inconsistent.")
        if result.total_rp != sum(item.remaining_rp for item in result.vehicle_lines):
            raise ResultAdapterContractError("Adapted RP total is inconsistent.")
        if result.total_ge_before_owned != sum(
            item.ge for item in result.vehicle_lines
        ):
            raise ResultAdapterContractError("Adapted GE total is inconsistent.")
        if result.total_ge_after_owned != max(
            result.total_ge_before_owned - owned_ge, 0
        ):
            raise ResultAdapterContractError("Adapted owned-GE subtraction is inconsistent.")
        if result.total_sl != sum(item.sl for item in result.vehicle_lines):
            raise ResultAdapterContractError("Adapted SL total is inconsistent.")


class CalculationEngine:
    """Select Legacy, Shadow, or explicitly enabled Graph Experimental execution."""

    version = "1.0.0-experimental"

    def __init__(
        self,
        database: VehicleDatabase,
        *,
        feature_flags: EngineFeatureFlags | None = None,
        legacy_solver: ResearchSolver | None = None,
        dual_runner: DualEngineRunner | None = None,
        graph_adapter: GraphCalculationResultAdapter | None = None,
    ) -> None:
        self.database = database
        self.feature_flags = feature_flags or EngineFeatureFlags()
        self.legacy_solver = legacy_solver or ResearchSolver(database)
        self.dual_runner = dual_runner or DualEngineRunner(database)
        self.graph_adapter = graph_adapter or GraphCalculationResultAdapter(database)

    def calculate(
        self,
        *,
        target_vehicle_id: str,
        start_vehicle_id: str | None = None,
        progress: PlayerProgress | None = None,
        options: SolveOptions | None = None,
        mode: ExecutionMode | str = ExecutionMode.LEGACY,
    ) -> CalculationExecutionResult:
        progress = progress or PlayerProgress()
        options = options or SolveOptions()
        mode = _coerce_mode(mode)
        if mode is ExecutionMode.LEGACY:
            solved = self.legacy_solver.solve(
                target_vehicle_id=target_vehicle_id,
                start_vehicle_id=start_vehicle_id,
                progress=progress,
                options=options,
            )
            return self._result(
                requested_mode=mode,
                result_source=ResultSource.LEGACY,
                calculation_status=CalculationStatus.COMPLETE,
                result=solved,
                graph_status=None,
                comparison_status=None,
                fallback_applied=False,
                fallback_reason=None,
                diagnostics={"legacyOnlyExecution": True},
            )

        if (
            mode is ExecutionMode.GRAPH_EXPERIMENTAL
            and not self.feature_flags.graph_experimental_enabled
        ):
            return self._feature_disabled_fallback(
                mode=mode,
                target_vehicle_id=target_vehicle_id,
                start_vehicle_id=start_vehicle_id,
                progress=progress,
                options=options,
            )

        try:
            dual = self.dual_runner.run(
                target_vehicle_id=target_vehicle_id,
                start_vehicle_id=start_vehicle_id,
                progress=progress,
                options=options,
            )
        except Exception as exc:
            return self._dual_runner_failure(
                mode=mode,
                target_vehicle_id=target_vehicle_id,
                start_vehicle_id=start_vehicle_id,
                progress=progress,
                options=options,
                exception=exc,
            )
        legacy = _legacy_solve_result(dual.legacy_result)
        if mode is ExecutionMode.SHADOW:
            if legacy is None:
                return self._unavailable(mode, dual, None)
            return self._result(
                requested_mode=mode,
                result_source=ResultSource.LEGACY,
                calculation_status=CalculationStatus.COMPLETE,
                result=legacy,
                graph_status=dual.graph_result.pipeline_status,
                comparison_status=dual.comparison_status,
                fallback_applied=False,
                fallback_reason=None,
                diagnostics={
                    "legacyRemainsUserResult": True,
                    "dualFingerprint": dual.fingerprint,
                },
            )

        invalid_findings = tuple(
            item
            for item in dual.graph_result.input_findings
            if item.category.value == "invalid_input"
        )
        if (
            dual.graph_result.pipeline_status is PipelineStatus.INVALID_INPUT
            or invalid_findings
        ):
            return self._invalid_input_result(mode, dual)

        if (
            dual.graph_result.pipeline_status is PipelineStatus.COMPLETE
            and dual.comparison_status is ComparisonStatus.EXACT_MATCH
        ):
            try:
                graph_result = self.graph_adapter.adapt(dual)
            except ResultAdapterContractError as exc:
                return self._fallback(
                    mode,
                    dual,
                    legacy,
                    FallbackReason.ADAPTER_CONTRACT_VIOLATION,
                    {"adapterErrorType": type(exc).__name__},
                )
            except Exception as exc:
                return self._fallback(
                    mode,
                    dual,
                    legacy,
                    FallbackReason.GRAPH_INTERNAL_ERROR,
                    {
                        "adapterErrorType": type(exc).__name__,
                        "failedStage": "GraphCalculationResultAdapter",
                    },
                )
            return self._result(
                requested_mode=mode,
                result_source=ResultSource.GRAPH,
                calculation_status=CalculationStatus.COMPLETE,
                result=graph_result,
                graph_status=dual.graph_result.pipeline_status,
                comparison_status=dual.comparison_status,
                fallback_applied=False,
                fallback_reason=None,
                diagnostics={
                    "graphResultAccepted": True,
                    "acceptanceRule": "PIPELINE_COMPLETE_AND_EXACT_MATCH",
                    "adapterVersion": self.graph_adapter.version,
                    "dualFingerprint": dual.fingerprint,
                },
            )

        return self._fallback(
            mode,
            dual,
            legacy,
            _fallback_reason(dual),
            {},
        )

    def _feature_disabled_fallback(
        self,
        *,
        mode: ExecutionMode,
        target_vehicle_id: str,
        start_vehicle_id: str | None,
        progress: PlayerProgress,
        options: SolveOptions,
    ) -> CalculationExecutionResult:
        try:
            legacy = self.legacy_solver.solve(
                target_vehicle_id=target_vehicle_id,
                start_vehicle_id=start_vehicle_id,
                progress=progress,
                options=options,
            )
        except Exception as exc:
            return self._result(
                requested_mode=mode,
                result_source=None,
                calculation_status=CalculationStatus.UNAVAILABLE,
                result=None,
                graph_status=None,
                comparison_status=None,
                fallback_applied=False,
                fallback_reason=FallbackReason.GRAPH_FEATURE_DISABLED,
                diagnostics={
                    "graphExecutionSkipped": True,
                    "legacyFallbackAvailable": False,
                    "legacyErrorType": type(exc).__name__,
                    "rawExceptionExposed": False,
                },
            )
        return self._result(
            requested_mode=mode,
            result_source=ResultSource.LEGACY,
            calculation_status=CalculationStatus.COMPLETE,
            result=legacy,
            graph_status=None,
            comparison_status=None,
            fallback_applied=True,
            fallback_reason=FallbackReason.GRAPH_FEATURE_DISABLED,
            diagnostics={
                "graphExecutionSkipped": True,
                "legacyFallbackAvailable": True,
            },
        )

    def _dual_runner_failure(
        self,
        *,
        mode: ExecutionMode,
        target_vehicle_id: str,
        start_vehicle_id: str | None,
        progress: PlayerProgress,
        options: SolveOptions,
        exception: Exception,
    ) -> CalculationExecutionResult:
        diagnostics = {
            "failedStage": "DualEngineRunner",
            "dualRunnerErrorType": type(exception).__name__,
            "rawExceptionExposed": False,
        }
        try:
            legacy = self.legacy_solver.solve(
                target_vehicle_id=target_vehicle_id,
                start_vehicle_id=start_vehicle_id,
                progress=progress,
                options=options,
            )
        except Exception as legacy_exception:
            return self._result(
                requested_mode=mode,
                result_source=None,
                calculation_status=CalculationStatus.UNAVAILABLE,
                result=None,
                graph_status=PipelineStatus.INTERNAL_ERROR,
                comparison_status=ComparisonStatus.INTERNAL_ERROR,
                fallback_applied=False,
                fallback_reason=FallbackReason.GRAPH_INTERNAL_ERROR,
                diagnostics={
                    **diagnostics,
                    "legacyFallbackAvailable": False,
                    "legacyErrorType": type(legacy_exception).__name__,
                },
            )
        return self._result(
            requested_mode=mode,
            result_source=ResultSource.LEGACY,
            calculation_status=CalculationStatus.COMPLETE,
            result=legacy,
            graph_status=PipelineStatus.INTERNAL_ERROR,
            comparison_status=ComparisonStatus.INTERNAL_ERROR,
            fallback_applied=mode is ExecutionMode.GRAPH_EXPERIMENTAL,
            fallback_reason=(
                FallbackReason.GRAPH_INTERNAL_ERROR
                if mode is ExecutionMode.GRAPH_EXPERIMENTAL
                else None
            ),
            diagnostics={
                **diagnostics,
                "legacyFallbackAvailable": True,
                "legacyRemainsUserResult": True,
            },
        )

    def _invalid_input_result(
        self,
        mode: ExecutionMode,
        dual: DualEngineResult,
    ) -> CalculationExecutionResult:
        invalid_rule_ids = tuple(
            sorted(
                {
                    item.rule_id
                    for item in dual.graph_result.input_findings
                    if item.category.value == "invalid_input"
                }
            )
        )
        return self._result(
            requested_mode=mode,
            result_source=None,
            calculation_status=CalculationStatus.UNAVAILABLE,
            result=None,
            graph_status=dual.graph_result.pipeline_status,
            comparison_status=dual.comparison_status,
            fallback_applied=False,
            fallback_reason=FallbackReason.GRAPH_INVALID_INPUT,
            diagnostics={
                "invalidInputRejected": True,
                "legacyResultDiscarded": dual.legacy_result.result is not None,
                "legacyFallbackAvailable": False,
                "affectedRuleIds": list(invalid_rule_ids),
                "dualFingerprint": dual.fingerprint,
            },
        )

    def _fallback(
        self,
        mode: ExecutionMode,
        dual: DualEngineResult,
        legacy: SolveResult | None,
        reason: FallbackReason,
        diagnostics: Mapping[str, Any],
    ) -> CalculationExecutionResult:
        if legacy is None:
            return self._unavailable(mode, dual, reason, diagnostics)
        return self._result(
            requested_mode=mode,
            result_source=ResultSource.LEGACY,
            calculation_status=CalculationStatus.COMPLETE,
            result=legacy,
            graph_status=dual.graph_result.pipeline_status,
            comparison_status=dual.comparison_status,
            fallback_applied=True,
            fallback_reason=reason,
            diagnostics={
                **dict(diagnostics),
                "graphResultDiscarded": True,
                "legacyFallbackAvailable": True,
                "dualFingerprint": dual.fingerprint,
                "affectedRuleIds": list(
                    dual.graph_result.status_contract.affected_rule_ids
                ),
            },
        )

    def _unavailable(
        self,
        mode: ExecutionMode,
        dual: DualEngineResult,
        reason: FallbackReason | None,
        diagnostics: Mapping[str, Any] | None = None,
    ) -> CalculationExecutionResult:
        return self._result(
            requested_mode=mode,
            result_source=None,
            calculation_status=CalculationStatus.UNAVAILABLE,
            result=None,
            graph_status=dual.graph_result.pipeline_status,
            comparison_status=dual.comparison_status,
            fallback_applied=False,
            fallback_reason=reason,
            diagnostics={
                **dict(diagnostics or {}),
                "legacyFallbackAvailable": False,
                "legacyStatus": dual.legacy_result.status,
                "dualFingerprint": dual.fingerprint,
            },
        )

    def _result(
        self,
        *,
        requested_mode: ExecutionMode,
        result_source: ResultSource | None,
        calculation_status: CalculationStatus,
        result: SolveResult | None,
        graph_status: PipelineStatus | None,
        comparison_status: ComparisonStatus | None,
        fallback_applied: bool,
        fallback_reason: FallbackReason | None,
        diagnostics: Mapping[str, Any],
    ) -> CalculationExecutionResult:
        common_diagnostics = {
            "executionEngineVersion": self.version,
            "defaultMode": ExecutionMode.LEGACY.value,
            "graphExperimentalFeatureEnabled": (
                self.feature_flags.graph_experimental_enabled
            ),
            "automaticConfidenceSwitching": False,
            "persistentActivation": False,
            "dataMigrationRequired": False,
            "legacyIsDefaultAndRecommended": True,
            **dict(diagnostics),
        }
        preliminary = CalculationExecutionResult(
            requested_mode=requested_mode,
            result_source=result_source,
            calculation_status=calculation_status,
            result=result,
            graph_status=graph_status,
            comparison_status=comparison_status,
            shadow_comparison_exists=(
                graph_status is not None or comparison_status is not None
            ),
            fallback_applied=fallback_applied,
            fallback_reason=fallback_reason,
            experimental=requested_mode is ExecutionMode.GRAPH_EXPERIMENTAL,
            diagnostics=common_diagnostics,
            fingerprint_version=EXECUTION_FINGERPRINT_VERSION,
            fingerprint="",
        )
        payload = preliminary.to_dict()
        payload.pop("fingerprint")
        return replace(
            preliminary,
            fingerprint=stable_fingerprint(
                payload,
                version=EXECUTION_FINGERPRINT_VERSION,
            ),
        )


def serialize_solve_result(result: SolveResult) -> dict[str, Any]:
    return {
        "start_vehicle_id": result.start_vehicle_id,
        "target_vehicle_id": result.target_vehicle_id,
        "vehicle_lines": [
            {
                "vehicle_id": item.vehicle_id,
                "name": item.name,
                "reason": item.reason,
                "total_rp": item.total_rp,
                "researched_rp": item.researched_rp,
                "remaining_rp": item.remaining_rp,
                "ge": item.ge,
                "sl": item.sl,
                "already_owned": item.already_owned,
            }
            for item in result.vehicle_lines
        ],
        "rank_requirements": [
            {
                "rank": item.rank,
                "required": item.required,
                "available_before": item.available_before,
                "available_after": item.available_after,
                "added_vehicle_ids": list(item.added_vehicle_ids),
            }
            for item in result.rank_requirements
        ],
        "required_vehicle_ids": list(result.required_vehicle_ids),
        "total_rp": result.total_rp,
        "total_ge_before_owned": result.total_ge_before_owned,
        "total_ge_after_owned": result.total_ge_after_owned,
        "total_sl": result.total_sl,
        "convertible_rp_shortfall": result.convertible_rp_shortfall,
        "warnings": list(result.warnings),
    }


def _legacy_solve_result(legacy: LegacyExecutionResult) -> SolveResult | None:
    payload = legacy.result
    if legacy.status != "complete" or payload is None:
        return None
    return SolveResult(
        start_vehicle_id=payload["start_vehicle_id"],
        target_vehicle_id=payload["target_vehicle_id"],
        vehicle_lines=tuple(
            VehicleCostLine(
                vehicle_id=item["vehicle_id"],
                name=item["name"],
                reason=item["reason"],
                total_rp=item["total_rp"],
                researched_rp=item["researched_rp"],
                remaining_rp=item["remaining_rp"],
                ge=item["ge"],
                sl=item["sl"],
                already_owned=item["already_owned"],
            )
            for item in payload["vehicle_lines"]
        ),
        rank_requirements=tuple(
            RankRequirement(
                rank=item["rank"],
                required=item["required"],
                available_before=item["available_before"],
                available_after=item["available_after"],
                added_vehicle_ids=tuple(item["added_vehicle_ids"]),
            )
            for item in payload["rank_requirements"]
        ),
        required_vehicle_ids=tuple(payload["required_vehicle_ids"]),
        total_rp=payload["total_rp"],
        total_ge_before_owned=payload["total_ge_before_owned"],
        total_ge_after_owned=payload["total_ge_after_owned"],
        total_sl=payload["total_sl"],
        convertible_rp_shortfall=payload["convertible_rp_shortfall"],
        warnings=tuple(payload["warnings"]),
    )


def _coerce_mode(mode: ExecutionMode | str) -> ExecutionMode:
    if isinstance(mode, ExecutionMode):
        return mode
    try:
        return ExecutionMode(mode)
    except ValueError as exc:
        raise ValueError(f"Unknown execution mode: {mode}") from exc


def _fallback_reason(dual: DualEngineResult) -> FallbackReason:
    graph_status = dual.graph_result.pipeline_status
    if graph_status is PipelineStatus.INTERNAL_ERROR:
        return FallbackReason.GRAPH_INTERNAL_ERROR
    if graph_status is PipelineStatus.INVALID_INPUT:
        return FallbackReason.GRAPH_INVALID_INPUT
    if graph_status is PipelineStatus.PARTIAL:
        return FallbackReason.GRAPH_PARTIAL
    if graph_status is PipelineStatus.BLOCKED:
        return FallbackReason.GRAPH_BLOCKED
    if graph_status is PipelineStatus.UNAVAILABLE:
        return FallbackReason.GRAPH_UNAVAILABLE
    return FallbackReason.COMPARISON_NOT_EXACT
