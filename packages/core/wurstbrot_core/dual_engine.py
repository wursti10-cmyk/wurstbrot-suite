from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
from typing import Any

from .database import DatabaseError, VehicleDatabase
from .graph_adapter import GraphDatabaseAdapter
from .graph_pipeline import (
    GraphCalculationPipeline,
    GraphPipelineResult,
    PipelineStatus,
    canonicalize,
    serialize_options,
    serialize_progress,
    stable_fingerprint,
)
from .graph_resolution import LegacyRankCompatibilityStrategy
from .models import PlayerProgress, SolveOptions, SolveResult
from .solver import ResearchSolver, SolveError


class ComparisonStatus(str, Enum):
    EXACT_MATCH = "exact_match"
    EQUIVALENT_MATCH = "equivalent_match"
    UNRESOLVED_EXPECTED = "unresolved_expected"
    UNSUPPORTED = "unsupported"
    INPUT_CONTRACT_DIFFERENCE = "input_contract_difference"
    MISMATCH = "mismatch"
    INTERNAL_ERROR = "internal_error"


DUAL_FINGERPRINT_VERSION = "dual-engine-comparison-v1"
LEGACY_FINGERPRINT_VERSION = "legacy-result-v1"


COMPARABLE_FIELDS = (
    "required_vehicle_ids",
    "rank_requirements",
    "vehicle_cost_lines.total_rp",
    "vehicle_cost_lines.researched_rp",
    "vehicle_cost_lines.remaining_rp",
    "vehicle_cost_lines.ge",
    "vehicle_cost_lines.sl",
    "total_rp",
    "total_ge_before_owned",
    "total_ge_after_owned",
    "total_sl",
    "convertible_rp_shortfall",
    "result_status",
)


EXCLUDED_FIELDS = (
    {
        "field": "satisfied_vehicle_ids",
        "reason": "Legacy SolveResult does not expose a structured satisfied set.",
    },
    {
        "field": "folder_requirements",
        "reason": "Legacy SolveResult does not expose structured folder requirements.",
    },
    {
        "field": "unlock_requirements",
        "reason": "Legacy exposes unlocks only as warning text, not a comparable contract.",
    },
    {
        "field": "evaluation_results",
        "reason": "Rule-level evaluation exists only in the additive graph pipeline.",
    },
)


@dataclass(frozen=True)
class LegacyExecutionResult:
    status: str
    result: dict[str, Any] | None
    error_code: str | None
    error_type: str | None
    error_message: str | None
    fingerprint_version: str
    fingerprint: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "result": canonicalize(self.result),
            "error_code": self.error_code,
            "error_type": self.error_type,
            "error_message": self.error_message,
            "fingerprint_version": self.fingerprint_version,
            "fingerprint": self.fingerprint,
        }


@dataclass(frozen=True)
class ComparisonDifference:
    field: str
    legacy_value: Any
    graph_value: Any
    contract_rule: str
    rule_ids: tuple[str, ...]
    explanation: str
    representation_only: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "field": self.field,
            "legacy_value": canonicalize(self.legacy_value),
            "graph_value": canonicalize(self.graph_value),
            "contract_rule": self.contract_rule,
            "rule_ids": list(self.rule_ids),
            "explanation": self.explanation,
            "representation_only": self.representation_only,
        }


@dataclass(frozen=True)
class DualEngineResult:
    target_vehicle_id: str
    start_vehicle_id: str | None
    request: dict[str, Any]
    legacy_result: LegacyExecutionResult
    graph_result: GraphPipelineResult
    comparison_status: ComparisonStatus
    differences: tuple[ComparisonDifference, ...]
    comparable_fields: tuple[str, ...]
    excluded_fields: tuple[dict[str, str], ...]
    diagnostics: dict[str, Any]
    fingerprint_version: str
    fingerprint: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "target_vehicle_id": canonicalize(self.target_vehicle_id),
            "start_vehicle_id": canonicalize(self.start_vehicle_id),
            "request": canonicalize(self.request),
            "legacy_result": self.legacy_result.to_dict(),
            "graph_result": self.graph_result.to_dict(),
            "comparison_status": self.comparison_status.value,
            "differences": [item.to_dict() for item in self.differences],
            "comparable_fields": list(self.comparable_fields),
            "excluded_fields": [canonicalize(item) for item in self.excluded_fields],
            "diagnostics": canonicalize(self.diagnostics),
            "fingerprint_version": self.fingerprint_version,
            "fingerprint": self.fingerprint,
        }


class DualEngineRunner:
    """Execute Legacy and graph engines without changing the productive result source."""

    version = "1.0.0-shadow"

    def __init__(
        self,
        source: VehicleDatabase | GraphDatabaseAdapter,
        *,
        pipeline: GraphCalculationPipeline | None = None,
    ) -> None:
        if isinstance(source, GraphDatabaseAdapter):
            self.database = source.database
            pipeline_source: VehicleDatabase | GraphDatabaseAdapter = source
        elif isinstance(source, VehicleDatabase):
            self.database = source
            pipeline_source = source
        else:
            raise TypeError("DualEngineRunner requires VehicleDatabase or adapter.")
        self.legacy_solver = ResearchSolver(self.database)
        self.pipeline = pipeline or GraphCalculationPipeline(
            pipeline_source,
            rank_compatibility_strategy=LegacyRankCompatibilityStrategy(self.database),
        )

    def run(
        self,
        *,
        target_vehicle_id: str,
        start_vehicle_id: str | None = None,
        progress: PlayerProgress | None = None,
        options: SolveOptions | None = None,
    ) -> DualEngineResult:
        progress = progress if progress is not None else PlayerProgress()
        options = options if options is not None else SolveOptions()
        legacy = self._run_legacy(
            target_vehicle_id=target_vehicle_id,
            start_vehicle_id=start_vehicle_id,
            progress=progress,
            options=options,
        )
        graph = self.pipeline.run(
            target_vehicle_id=target_vehicle_id,
            start_vehicle_id=start_vehicle_id,
            progress=progress,
            options=options,
        )
        status, differences = self._compare(legacy, graph)
        open_rule_ids = tuple(
            sorted(
                {
                    *graph.status_contract.affected_rule_ids,
                    *(item.rule_id for item in graph.input_findings),
                }
            )
        )
        request = {
            "progress": serialize_progress(progress),
            "options": serialize_options(options),
        }
        diagnostics = {
            "dualEngineVersion": self.version,
            "productiveResultSource": "legacy",
            "productiveCallerUsesGraphResult": False,
            "legacyStatus": legacy.status,
            "graphStatus": graph.pipeline_status.value,
            "comparisonStatus": status.value,
            "ruleIds": list(open_rule_ids),
            "legacyFingerprint": legacy.fingerprint,
            "graphFingerprint": graph.fingerprint,
            "differenceCount": len(differences),
            "evidence": graph.evidence,
            "explanationTrace": list(graph.explanation_trace),
            "nonExactComparison": (
                None
                if status is ComparisonStatus.EXACT_MATCH
                else _non_exact_diagnostics(
                    legacy=legacy,
                    graph=graph,
                    differences=differences,
                    request=request,
                )
            ),
        }
        preliminary = DualEngineResult(
            target_vehicle_id=target_vehicle_id,
            start_vehicle_id=start_vehicle_id,
            request=request,
            legacy_result=legacy,
            graph_result=graph,
            comparison_status=status,
            differences=differences,
            comparable_fields=COMPARABLE_FIELDS,
            excluded_fields=EXCLUDED_FIELDS,
            diagnostics=diagnostics,
            fingerprint_version=DUAL_FINGERPRINT_VERSION,
            fingerprint="",
        )
        payload = preliminary.to_dict()
        payload.pop("fingerprint")
        return replace(
            preliminary,
            fingerprint=stable_fingerprint(payload, version=DUAL_FINGERPRINT_VERSION),
        )

    def _run_legacy(
        self,
        *,
        target_vehicle_id: str,
        start_vehicle_id: str | None,
        progress: PlayerProgress,
        options: SolveOptions,
    ) -> LegacyExecutionResult:
        try:
            solved = self.legacy_solver.solve(
                target_vehicle_id=target_vehicle_id,
                start_vehicle_id=start_vehicle_id,
                progress=progress,
                options=options,
            )
        except (DatabaseError, SolveError, ValueError) as exc:
            return _legacy_execution(
                status="error",
                result=None,
                error_code="LEGACY_INPUT_OR_SOLVE_ERROR",
                error_type=type(exc).__name__,
                error_message=str(exc),
            )
        except Exception as exc:
            return _legacy_execution(
                status="internal_error",
                result=None,
                error_code="LEGACY_INTERNAL_ERROR",
                error_type=type(exc).__name__,
                error_message=None,
            )
        return _legacy_execution(
            status="complete",
            result=_serialize_solve_result(solved),
            error_code=None,
            error_type=None,
            error_message=None,
        )

    def _compare(
        self,
        legacy: LegacyExecutionResult,
        graph: GraphPipelineResult,
    ) -> tuple[ComparisonStatus, tuple[ComparisonDifference, ...]]:
        if (
            legacy.status == "internal_error"
            or graph.pipeline_status is PipelineStatus.INTERNAL_ERROR
        ):
            return (
                ComparisonStatus.INTERNAL_ERROR,
                (
                    _difference(
                        "result_status",
                        legacy.status,
                        graph.pipeline_status.value,
                        "INTERNAL_ERROR_IS_NOT_UNRESOLVED",
                        graph.status_contract.affected_rule_ids,
                        (
                            "An engine failed internally; the result cannot be "
                            "classified as unresolved."
                        ),
                    ),
                ),
            )

        input_findings = tuple(
            item
            for item in graph.input_findings
            if item.category.value == "invalid_input"
        )
        if graph.pipeline_status is PipelineStatus.INVALID_INPUT or any(
            not item.blocking for item in input_findings
        ):
            return (
                ComparisonStatus.INPUT_CONTRACT_DIFFERENCE,
                tuple(
                    _difference(
                        item.source_field,
                        legacy.status,
                        item.to_dict(),
                        "GRAPH_INPUT_CONTRACT",
                        (item.rule_id,),
                        item.message,
                    )
                    for item in input_findings
                ),
            )

        if graph.pipeline_status is PipelineStatus.PARTIAL:
            return (
                ComparisonStatus.UNRESOLVED_EXPECTED,
                (
                    _difference(
                        "result_status",
                        legacy.status,
                        "partial",
                        "UNRESOLVED_RULE_PRESERVATION",
                        graph.status_contract.affected_rule_ids,
                        "Graph prerequisites remain unresolved; complete costs are unavailable.",
                    ),
                ),
            )
        if graph.pipeline_status is PipelineStatus.UNAVAILABLE:
            status = (
                ComparisonStatus.INPUT_CONTRACT_DIFFERENCE
                if graph.status_contract.cause == "datamine_error"
                else ComparisonStatus.UNSUPPORTED
            )
            return (
                status,
                (
                    _difference(
                        "result_status",
                        legacy.status,
                        "unavailable",
                        graph.status_contract.cause.upper(),
                        graph.status_contract.affected_rule_ids,
                        graph.status_contract.explanation,
                    ),
                ),
            )
        if graph.pipeline_status is PipelineStatus.BLOCKED:
            status = (
                ComparisonStatus.UNSUPPORTED
                if legacy.status == "error"
                else ComparisonStatus.MISMATCH
            )
            return (
                status,
                (
                    _difference(
                        "result_status",
                        legacy.status,
                        "blocked",
                        "BLOCKING_RULE",
                        graph.status_contract.affected_rule_ids,
                        graph.status_contract.explanation,
                    ),
                ),
            )
        if legacy.status != "complete" or legacy.result is None:
            return (
                ComparisonStatus.MISMATCH,
                (
                    _difference(
                        "result_status",
                        legacy.status,
                        graph.pipeline_status.value,
                        "COMPLETE_RESULT_PARITY",
                        graph.status_contract.affected_rule_ids,
                        "Graph completed while Legacy did not return a result.",
                    ),
                ),
            )

        differences = self._complete_differences(legacy.result, graph)
        if not differences:
            return ComparisonStatus.EXACT_MATCH, ()
        if all(item.representation_only for item in differences):
            return ComparisonStatus.EQUIVALENT_MATCH, differences
        return ComparisonStatus.MISMATCH, differences

    @staticmethod
    def _complete_differences(
        legacy: dict[str, Any],
        graph: GraphPipelineResult,
    ) -> tuple[ComparisonDifference, ...]:
        resolution = graph.prerequisite_resolution
        cost = graph.cost_result
        if resolution is None or cost is None:
            return (
                _difference(
                    "graph_contract",
                    "complete",
                    "missing component result",
                    "PIPELINE_COMPONENT_CONTRACT",
                    (),
                    "A complete graph pipeline must expose resolution and cost results.",
                ),
            )
        differences: list[ComparisonDifference] = []
        legacy_ids = tuple(legacy["required_vehicle_ids"])
        graph_ids = resolution.required_vehicle_ids
        if legacy_ids != graph_ids:
            same_set = set(legacy_ids) == set(graph_ids)
            differences.append(
                _difference(
                    "required_vehicle_ids",
                    legacy_ids,
                    graph_ids,
                    "PREREQUISITE_SET_PARITY",
                    graph.status_contract.affected_rule_ids,
                    (
                        "Required vehicle sets match but their representation differs."
                        if same_set
                        else "Required vehicle sets differ."
                    ),
                    representation_only=same_set,
                )
            )

        legacy_ranks = tuple(_normalize_legacy_rank(item) for item in legacy["rank_requirements"])
        graph_ranks = tuple(_normalize_graph_rank(item) for item in resolution.rank_requirements)
        if legacy_ranks != graph_ranks:
            differences.append(
                _difference(
                    "rank_requirements",
                    legacy_ranks,
                    graph_ranks,
                    "RANK_REQUIREMENT_PARITY",
                    ("RANK_REQUIREMENT",),
                    "Structured rank requirements differ.",
                )
            )

        legacy_lines = {item["vehicle_id"]: item for item in legacy["vehicle_lines"]}
        graph_lines = {item.vehicle_id: item.to_dict() for item in cost.vehicle_cost_lines}
        for vehicle_id in sorted(set(legacy_lines) | set(graph_lines)):
            legacy_line = legacy_lines.get(vehicle_id)
            graph_line = graph_lines.get(vehicle_id)
            if legacy_line is None or graph_line is None:
                differences.append(
                    _difference(
                        f"vehicle_cost_lines.{vehicle_id}",
                        legacy_line,
                        graph_line,
                        "VEHICLE_COST_LINE_SET_PARITY",
                        (),
                        "A vehicle cost line exists in only one engine.",
                    )
                )
                continue
            for legacy_field, graph_field in (
                ("total_rp", "total_rp"),
                ("researched_rp", "researched_rp"),
                ("remaining_rp", "remaining_rp"),
                ("ge", "ge"),
                ("sl", "discounted_sl"),
            ):
                if legacy_line[legacy_field] != graph_line[graph_field]:
                    differences.append(
                        _difference(
                            f"vehicle_cost_lines.{vehicle_id}.{legacy_field}",
                            legacy_line[legacy_field],
                            graph_line[graph_field],
                            "VEHICLE_COST_LINE_PARITY",
                            (),
                            "Per-vehicle numeric cost differs.",
                        )
                    )

        for legacy_field, graph_value in (
            ("total_rp", cost.total_remaining_rp),
            ("total_ge_before_owned", cost.total_ge_before_owned),
            ("total_ge_after_owned", cost.total_ge_after_owned),
            ("total_sl", cost.total_sl),
            ("convertible_rp_shortfall", cost.convertible_rp_shortfall),
        ):
            if legacy[legacy_field] != graph_value:
                differences.append(
                    _difference(
                        legacy_field,
                        legacy[legacy_field],
                        graph_value,
                        "TOTAL_COST_PARITY",
                        (),
                        "Complete Legacy and Graph totals differ.",
                    )
                )
        return tuple(
            sorted(
                differences,
                key=lambda item: (
                    item.field,
                    item.contract_rule,
                    str(item.legacy_value),
                    str(item.graph_value),
                ),
            )
        )


def _legacy_execution(
    *,
    status: str,
    result: dict[str, Any] | None,
    error_code: str | None,
    error_type: str | None,
    error_message: str | None,
) -> LegacyExecutionResult:
    payload = {
        "status": status,
        "result": result,
        "error_code": error_code,
        "error_type": error_type,
        "error_message": error_message,
    }
    return LegacyExecutionResult(
        status=status,
        result=result,
        error_code=error_code,
        error_type=error_type,
        error_message=error_message,
        fingerprint_version=LEGACY_FINGERPRINT_VERSION,
        fingerprint=stable_fingerprint(payload, version=LEGACY_FINGERPRINT_VERSION),
    )


def _serialize_solve_result(result: SolveResult) -> dict[str, Any]:
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


def _normalize_legacy_rank(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "rank": item["rank"],
        "required": item["required"],
        "available_before": item["available_before"],
        "available_after": item["available_after"],
        "added_vehicle_ids": list(item["added_vehicle_ids"]),
    }


def _normalize_graph_rank(item: Any) -> dict[str, Any]:
    return {
        "rank": item.rank,
        "required": item.required_count,
        "available_before": item.satisfied_count,
        "available_after": item.satisfied_count + len(item.selected_vehicle_ids),
        "added_vehicle_ids": list(item.selected_vehicle_ids),
    }


def _difference(
    field: str,
    legacy_value: Any,
    graph_value: Any,
    contract_rule: str,
    rule_ids: tuple[str, ...] | list[str],
    explanation: str,
    *,
    representation_only: bool = False,
) -> ComparisonDifference:
    return ComparisonDifference(
        field=field,
        legacy_value=canonicalize(legacy_value),
        graph_value=canonicalize(graph_value),
        contract_rule=contract_rule,
        rule_ids=tuple(sorted(set(rule_ids))),
        explanation=explanation,
        representation_only=representation_only,
    )


def _non_exact_diagnostics(
    *,
    legacy: LegacyExecutionResult,
    graph: GraphPipelineResult,
    differences: tuple[ComparisonDifference, ...],
    request: dict[str, Any],
) -> dict[str, Any]:
    legacy_payload = legacy.result or {}
    resolution = graph.prerequisite_resolution
    cost = graph.cost_result
    legacy_ids = tuple(legacy_payload.get("required_vehicle_ids", ()))
    graph_ids = resolution.required_vehicle_ids if resolution is not None else ()
    legacy_lines = legacy_payload.get("vehicle_lines", ())
    graph_lines = (
        tuple(item.to_dict() for item in cost.vehicle_cost_lines)
        if cost is not None
        else ()
    )
    vehicle_differences = tuple(
        item.to_dict()
        for item in differences
        if item.field.startswith("vehicle_cost_lines")
    )
    total_fields = {
        "total_rp",
        "total_ge_before_owned",
        "total_ge_after_owned",
        "total_sl",
        "convertible_rp_shortfall",
    }
    total_differences = tuple(
        item.to_dict() for item in differences if item.field in total_fields
    )
    comparison_performed = (
        legacy.status == "complete"
        and graph.pipeline_status is PipelineStatus.COMPLETE
    )
    return {
        "targetVehicleId": graph.target_vehicle_id,
        "startVehicleId": graph.start_vehicle_id,
        "options": request["options"],
        "playerProgress": request["progress"],
        "legacyStatus": legacy.status,
        "graphStatus": graph.pipeline_status.value,
        "vehicleSetDifferences": {
            "legacyVehicleIds": list(legacy_ids),
            "graphVehicleIds": list(graph_ids),
            "onlyLegacy": sorted(set(legacy_ids) - set(graph_ids)),
            "onlyGraph": sorted(set(graph_ids) - set(legacy_ids)),
            "comparisonPerformed": comparison_performed,
        },
        "vehicleCostLineDifferences": {
            "legacyLines": list(legacy_lines),
            "graphLines": list(graph_lines),
            "differences": list(vehicle_differences),
            "comparisonPerformed": comparison_performed,
        },
        "totalDifferences": {
            "differences": list(total_differences),
            "comparisonPerformed": comparison_performed,
        },
        "contractRules": sorted({item.contract_rule for item in differences}),
        "ruleIds": sorted(
            {
                *graph.status_contract.affected_rule_ids,
                *(rule_id for item in differences for rule_id in item.rule_ids),
            }
        ),
        "evidence": graph.evidence,
        "explanationTrace": list(graph.explanation_trace),
        "fingerprints": {
            "legacy": legacy.fingerprint,
            "graph": graph.fingerprint,
        },
    }
