from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, replace
from enum import Enum
from typing import Any, Iterable

from .database import VehicleDatabase
from .graph_adapter import GraphDatabaseAdapter
from .graph_cost import ALLOWED_SL_DISCOUNTS, CostStatus, GraphCostEngine, GraphCostResult
from .graph_evaluation import (
    EvaluationStatus,
    GraphEvaluationReport,
    GraphRuleEvaluator,
)
from .graph_resolution import (
    GraphPrerequisiteResolver,
    PrerequisiteResolution,
    RankCompatibilityStrategy,
    ResolutionStatus,
)
from .models import PlayerProgress, SolveOptions, VehicleProgress
from .research_graph import ResearchGraph, ResearchGraphBuilder


class PipelineStatus(str, Enum):
    COMPLETE = "complete"
    PARTIAL = "partial"
    BLOCKED = "blocked"
    UNAVAILABLE = "unavailable"
    INVALID_INPUT = "invalid_input"
    INTERNAL_ERROR = "internal_error"


class ValidationCategory(str, Enum):
    INVALID_INPUT = "invalid_input"
    DATAMINE_ERROR = "datamine_error"


class ValidationSeverity(str, Enum):
    ERROR = "error"
    WARNING = "warning"


INPUT_VALIDATION_RULE_IDS = (
    "INPUT_ASSUME_EXTERNAL_INVALID",
    "INPUT_CONVERTIBLE_RP_INVALID",
    "INPUT_FULFILLED_UNLOCK_INVALID",
    "INPUT_INCLUDE_HIDDEN_INVALID",
    "INPUT_INCLUDE_START_INVALID",
    "INPUT_OPTIMIZE_FOR_INVALID",
    "INPUT_OWNED_GE_INVALID",
    "INPUT_PROGRESS_RP_EXCEEDS_TOTAL",
    "INPUT_PROGRESS_RP_NEGATIVE_OR_INVALID",
    "INPUT_PROGRESS_STATUS_INVALID",
    "INPUT_PROGRESS_VEHICLE_UNKNOWN",
    "INPUT_PURCHASE_WITHOUT_RESEARCH",
    "INPUT_RESEARCH_FLAG_RP_CONFLICT",
    "INPUT_SL_DISCOUNT_INVALID",
    "INPUT_START_COUNTRY_MISMATCH",
    "INPUT_START_UNKNOWN",
    "INPUT_START_VEHICLE_TYPE_MISMATCH",
    "INPUT_TARGET_UNKNOWN",
)

DATAMINE_VALIDATION_RULE_IDS = (
    "DATAMINE_GAME_VERSION_INVALID",
    "DATAMINE_RP_PER_GE_INVALID",
    "DATAMINE_VEHICLE_COST_INVALID",
)

FINGERPRINT_VERSION = "graph-pipeline-fingerprint-v1"


@dataclass(frozen=True)
class PipelineInputFinding:
    rule_id: str
    category: ValidationCategory
    severity: ValidationSeverity
    message: str
    source_field: str
    entity_id: str | None
    details: dict[str, Any]
    blocking: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "category": self.category.value,
            "severity": self.severity.value,
            "message": self.message,
            "source_field": self.source_field,
            "entity_id": self.entity_id,
            "details": canonicalize(self.details),
            "blocking": self.blocking,
        }


@dataclass(frozen=True)
class PipelineStatusContract:
    status: PipelineStatus
    cause: str
    affected_rule_ids: tuple[str, ...]
    blocking: bool
    user_safe: bool
    comparable_to_legacy: bool
    explanation: str
    evidence: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "cause": self.cause,
            "affected_rule_ids": list(self.affected_rule_ids),
            "blocking": self.blocking,
            "user_safe": self.user_safe,
            "comparable_to_legacy": self.comparable_to_legacy,
            "explanation": self.explanation,
            "evidence": canonicalize(self.evidence),
        }


@dataclass(frozen=True)
class GraphPipelineResult:
    target_vehicle_id: str
    start_vehicle_id: str | None
    evaluation_report: GraphEvaluationReport | None
    prerequisite_resolution: PrerequisiteResolution | None
    cost_result: GraphCostResult | None
    pipeline_status: PipelineStatus
    status_contract: PipelineStatusContract
    input_findings: tuple[PipelineInputFinding, ...]
    evidence: dict[str, Any]
    explanation_trace: tuple[str, ...]
    diagnostics: dict[str, Any]
    fingerprint_version: str
    fingerprint: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "target_vehicle_id": canonicalize(self.target_vehicle_id),
            "start_vehicle_id": canonicalize(self.start_vehicle_id),
            "evaluation_results": (
                self.evaluation_report.to_dict()
                if self.evaluation_report is not None
                else None
            ),
            "prerequisite_resolution": (
                self.prerequisite_resolution.to_dict()
                if self.prerequisite_resolution is not None
                else None
            ),
            "graph_cost_result": (
                self.cost_result.to_dict() if self.cost_result is not None else None
            ),
            "pipeline_status": self.pipeline_status.value,
            "status_contract": self.status_contract.to_dict(),
            "input_findings": [item.to_dict() for item in self.input_findings],
            "evidence": canonicalize(self.evidence),
            "explanation_trace": list(self.explanation_trace),
            "diagnostics": canonicalize(self.diagnostics),
            "fingerprint_version": self.fingerprint_version,
            "fingerprint": self.fingerprint,
        }


class GraphCalculationPipeline:
    """Compose graph evaluation, prerequisite resolution and cost calculation.

    The pipeline owns orchestration, validation and status translation only. Domain
    semantics remain in the three delegated graph components.
    """

    version = "1.0.0-shadow"

    def __init__(
        self,
        source: VehicleDatabase | GraphDatabaseAdapter,
        *,
        rank_compatibility_strategy: RankCompatibilityStrategy | None = None,
        evaluator: GraphRuleEvaluator | None = None,
        resolver: GraphPrerequisiteResolver | None = None,
        cost_engine: GraphCostEngine | None = None,
    ) -> None:
        if isinstance(source, GraphDatabaseAdapter):
            self.database = source.database
            self.graph = source.graph
            self.source_kind = "GraphDatabaseAdapter"
        elif isinstance(source, VehicleDatabase):
            self.database = source
            self.graph = ResearchGraphBuilder.from_database(source)
            self.source_kind = "VehicleDatabase"
        else:
            raise TypeError("GraphCalculationPipeline requires VehicleDatabase or adapter.")
        self.evaluator = evaluator or GraphRuleEvaluator(self.graph)
        self.resolver = resolver or GraphPrerequisiteResolver(
            self.graph,
            rank_compatibility_strategy=rank_compatibility_strategy,
        )
        self.cost_engine = cost_engine or GraphCostEngine(self.database)
        self._datamine_findings = self._validate_database()
        graph_diagnostics = self.graph.diagnostics().to_dict()
        self._graph_diagnostics = {
            key: graph_diagnostics[key]
            for key in (
                "nodeCount",
                "edgeCount",
                "disconnectedComponents",
                "cycles",
                "isDag",
                "longestPath",
                "averageBranchingFactor",
            )
        }
        self._graph_diagnostics_fingerprint = stable_fingerprint(
            graph_diagnostics,
            version="graph-diagnostics-v1",
        )

    def run(
        self,
        *,
        target_vehicle_id: str,
        start_vehicle_id: str | None = None,
        progress: PlayerProgress | None = None,
        options: SolveOptions | None = None,
    ) -> GraphPipelineResult:
        progress = progress if progress is not None else PlayerProgress()
        options = options if options is not None else SolveOptions()
        trace = [
            f"pipeline={self.version}",
            f"target={_safe_trace_value(target_vehicle_id)}",
            f"start={_safe_trace_value(start_vehicle_id)}",
        ]
        try:
            findings = tuple(
                sorted(
                    (
                        *self._datamine_findings,
                        *self._validate_request(
                            target_vehicle_id,
                            start_vehicle_id,
                            progress,
                            options,
                        ),
                    ),
                    key=lambda item: (
                        item.category.value,
                        item.rule_id,
                        item.entity_id or "",
                        item.message,
                    ),
                )
            )
        except Exception as exc:
            trace.append("internal_error_stage=input_validation")
            trace.append("pipeline_status=internal_error")
            return self._result(
                target_vehicle_id=target_vehicle_id,
                start_vehicle_id=start_vehicle_id,
                progress=progress,
                options=options,
                evaluation=None,
                resolution=None,
                cost=None,
                status=PipelineStatus.INTERNAL_ERROR,
                cause="internal_error",
                rule_ids=(),
                blocking=True,
                user_safe=False,
                comparable=False,
                explanation="The graph pipeline input boundary failed internally.",
                findings=(),
                trace=trace,
                status_evidence={
                    "errorCode": "PIPELINE_INPUT_VALIDATION_FAILURE",
                    "failedStage": "input_validation",
                    "exceptionType": type(exc).__name__,
                    "rawExceptionExposed": False,
                },
            )
        blocking = tuple(item for item in findings if item.blocking)
        trace.extend(
            f"input:{item.rule_id}={item.severity.value}" for item in findings
        )
        if blocking:
            datamine_blocking = any(
                item.category is ValidationCategory.DATAMINE_ERROR for item in blocking
            )
            status = (
                PipelineStatus.UNAVAILABLE
                if datamine_blocking
                else PipelineStatus.INVALID_INPUT
            )
            cause = "datamine_error" if datamine_blocking else "invalid_input"
            explanation = (
                "The graph pipeline cannot use invalid datamine values."
                if datamine_blocking
                else "The request violates the graph pipeline input contract."
            )
            trace.append(f"pipeline_status={status.value}")
            return self._result(
                target_vehicle_id=target_vehicle_id,
                start_vehicle_id=start_vehicle_id,
                progress=progress,
                options=options,
                evaluation=None,
                resolution=None,
                cost=None,
                status=status,
                cause=cause,
                rule_ids=tuple(item.rule_id for item in blocking),
                blocking=True,
                user_safe=True,
                comparable=False,
                explanation=explanation,
                findings=findings,
                trace=trace,
                status_evidence={
                    "blockingFindingCount": len(blocking),
                    "validationCategory": cause,
                },
            )

        evaluation: GraphEvaluationReport | None = None
        resolution: PrerequisiteResolution | None = None
        cost: GraphCostResult | None = None
        stage = "evaluation"
        try:
            evaluation = self.evaluator.evaluate(
                target_vehicle_id=target_vehicle_id,
                start_vehicle_id=start_vehicle_id,
                progress=progress,
                options=options,
            )
            trace.extend(
                f"evaluation:{item.rule_id}={item.status.value}"
                for item in evaluation.evaluations
            )
            stage = "resolution"
            resolution = self.resolver.resolve(
                target_vehicle_id=target_vehicle_id,
                start_vehicle_id=start_vehicle_id,
                progress=progress,
                options=options,
            )
            trace.extend(
                f"resolution:{_strip_number(item)}"
                for item in resolution.explanation_trace
            )
            stage = "cost"
            cost = self.cost_engine.calculate(
                resolution,
                progress=progress,
                options=options,
            )
            trace.extend(
                f"cost:{_strip_number(item)}" for item in cost.explanation_trace
            )
        except Exception as exc:
            trace.append(f"internal_error_stage={stage}")
            trace.append("pipeline_status=internal_error")
            return self._result(
                target_vehicle_id=target_vehicle_id,
                start_vehicle_id=start_vehicle_id,
                progress=progress,
                options=options,
                evaluation=evaluation,
                resolution=resolution,
                cost=cost,
                status=PipelineStatus.INTERNAL_ERROR,
                cause="internal_error",
                rule_ids=(),
                blocking=True,
                user_safe=False,
                comparable=False,
                explanation=(
                    "The graph pipeline could not complete because an internal "
                    "component failed."
                ),
                findings=findings,
                trace=trace,
                status_evidence={
                    "errorCode": "PIPELINE_COMPONENT_FAILURE",
                    "failedStage": stage,
                    "exceptionType": type(exc).__name__,
                    "rawExceptionExposed": False,
                },
            )

        status, cause, explanation = self._translate_status(resolution, cost)
        open_rules = tuple(
            sorted(
                {
                    item.rule_id
                    for item in (
                        *resolution.blocking_rule_results,
                        *resolution.unresolved_rule_results,
                    )
                }
            )
        )
        trace.append(f"pipeline_status={status.value}")
        return self._result(
            target_vehicle_id=target_vehicle_id,
            start_vehicle_id=start_vehicle_id,
            progress=progress,
            options=options,
            evaluation=evaluation,
            resolution=resolution,
            cost=cost,
            status=status,
            cause=cause,
            rule_ids=open_rules,
            blocking=status in {
                PipelineStatus.BLOCKED,
                PipelineStatus.INVALID_INPUT,
                PipelineStatus.INTERNAL_ERROR,
            },
            user_safe=True,
            comparable=status is PipelineStatus.COMPLETE,
            explanation=explanation,
            findings=findings,
            trace=trace,
            status_evidence={
                "resolutionStatus": resolution.resolution_status.value,
                "costStatus": cost.cost_status.value,
                "completeTotalsEmitted": cost.cost_status is CostStatus.COMPLETE,
            },
        )

    @staticmethod
    def _translate_status(
        resolution: PrerequisiteResolution,
        cost: GraphCostResult,
    ) -> tuple[PipelineStatus, str, str]:
        if resolution.resolution_status is ResolutionStatus.BLOCKED:
            return (
                PipelineStatus.BLOCKED,
                "blocking_rule",
                "A deterministic graph rule blocks the calculation.",
            )
        if resolution.resolution_status is ResolutionStatus.UNRESOLVED:
            return (
                PipelineStatus.PARTIAL,
                "unresolved_rule",
                "At least one prerequisite rule remains unresolved; costs are partial.",
            )
        if resolution.resolution_status is ResolutionStatus.UNSUPPORTED:
            return (
                PipelineStatus.UNAVAILABLE,
                "unsupported_feature",
                "The current graph model cannot represent this calculation reliably.",
            )
        if cost.cost_status is CostStatus.COMPLETE:
            return (
                PipelineStatus.COMPLETE,
                "all_components_complete",
                "Evaluation, prerequisite resolution and cost calculation completed.",
            )
        if cost.cost_status is CostStatus.UNAVAILABLE:
            return (
                PipelineStatus.UNAVAILABLE,
                "datamine_error",
                "Cost calculation rejected invalid source data.",
            )
        return (
            PipelineStatus.INTERNAL_ERROR,
            "internal_error",
            "Component statuses form an invalid pipeline combination.",
        )

    def _result(
        self,
        *,
        target_vehicle_id: str,
        start_vehicle_id: str | None,
        progress: PlayerProgress,
        options: SolveOptions,
        evaluation: GraphEvaluationReport | None,
        resolution: PrerequisiteResolution | None,
        cost: GraphCostResult | None,
        status: PipelineStatus,
        cause: str,
        rule_ids: Iterable[str],
        blocking: bool,
        user_safe: bool,
        comparable: bool,
        explanation: str,
        findings: tuple[PipelineInputFinding, ...],
        trace: list[str],
        status_evidence: dict[str, Any],
    ) -> GraphPipelineResult:
        affected = tuple(sorted(set(rule_ids)))
        status_contract = PipelineStatusContract(
            status=status,
            cause=cause,
            affected_rule_ids=affected,
            blocking=blocking,
            user_safe=user_safe,
            comparable_to_legacy=comparable,
            explanation=explanation,
            evidence=status_evidence,
        )
        evidence = {
            "gameVersion": self.database.game_version,
            "sourceKind": self.source_kind,
            "shadowMode": True,
            "delegatedComponents": (
                "GraphRuleEvaluator",
                "GraphPrerequisiteResolver",
                "GraphCostEngine",
            ),
            "domainRulesDuplicatedByPipeline": False,
            "productiveLegacySolverModified": False,
            "guiModified": False,
            "browserModified": False,
            "optimizerSelectionPerformed": False,
            "request": {
                "progress": serialize_progress(progress),
                "options": serialize_options(options),
            },
        }
        diagnostics = {
            "componentVersions": {
                "pipeline": self.version,
                "evaluator": getattr(self.evaluator, "version", "1.0.0-shadow"),
                "resolver": getattr(self.resolver, "version", "1.0.0-shadow"),
                "costEngine": getattr(self.cost_engine, "version", "unknown"),
            },
            "inputFindingCount": len(findings),
            "blockingInputFindingCount": sum(item.blocking for item in findings),
            "inputFindingRuleIds": sorted({item.rule_id for item in findings}),
            "evaluationCounts": evaluation.counts if evaluation is not None else None,
            "resolutionStatus": (
                resolution.resolution_status.value if resolution is not None else None
            ),
            "costStatus": cost.cost_status.value if cost is not None else None,
            "graphDiagnostics": self._graph_diagnostics,
            "graphDiagnosticsFingerprint": self._graph_diagnostics_fingerprint,
            "statusEvidence": status_evidence,
        }
        preliminary = GraphPipelineResult(
            target_vehicle_id=target_vehicle_id,
            start_vehicle_id=start_vehicle_id,
            evaluation_report=evaluation,
            prerequisite_resolution=resolution,
            cost_result=cost,
            pipeline_status=status,
            status_contract=status_contract,
            input_findings=findings,
            evidence=evidence,
            explanation_trace=_numbered(trace),
            diagnostics=diagnostics,
            fingerprint_version=FINGERPRINT_VERSION,
            fingerprint="",
        )
        payload = preliminary.to_dict()
        payload.pop("fingerprint")
        return replace(
            preliminary,
            fingerprint=stable_fingerprint(payload, version=FINGERPRINT_VERSION),
        )

    def _validate_database(self) -> tuple[PipelineInputFinding, ...]:
        findings: list[PipelineInputFinding] = []
        if (
            not isinstance(self.database.game_version, str)
            or not self.database.game_version.strip()
        ):
            findings.append(
                _finding(
                    "DATAMINE_GAME_VERSION_INVALID",
                    ValidationCategory.DATAMINE_ERROR,
                    "gameVersion must be a non-empty string.",
                    "gameVersion",
                )
            )
        if not _positive_int(self.database.rp_per_ge):
            findings.append(
                _finding(
                    "DATAMINE_RP_PER_GE_INVALID",
                    ValidationCategory.DATAMINE_ERROR,
                    "rpPerGE must be a positive integer.",
                    "economy.rpPerGE",
                    details={"value": self.database.rp_per_ge},
                )
            )
        for vehicle in sorted(self.database.vehicles.values(), key=lambda item: item.id):
            invalid_fields = [
                field
                for field, value in (("rp", vehicle.rp), ("sl", vehicle.sl))
                if not _nonnegative_int(value)
            ]
            if invalid_fields:
                findings.append(
                    _finding(
                        "DATAMINE_VEHICLE_COST_INVALID",
                        ValidationCategory.DATAMINE_ERROR,
                        "Vehicle RP and SL must be non-negative integers.",
                        ",".join(invalid_fields),
                        entity_id=vehicle.id,
                        details={field: getattr(vehicle, field) for field in invalid_fields},
                    )
                )
        return tuple(findings)

    def _validate_request(
        self,
        target_vehicle_id: str,
        start_vehicle_id: str | None,
        progress: Any,
        options: Any,
    ) -> tuple[PipelineInputFinding, ...]:
        findings: list[PipelineInputFinding] = []
        target = (
            self.database.vehicles.get(target_vehicle_id)
            if isinstance(target_vehicle_id, str)
            else None
        )
        if not isinstance(target_vehicle_id, str) or target is None:
            findings.append(
                _finding(
                    "INPUT_TARGET_UNKNOWN",
                    ValidationCategory.INVALID_INPUT,
                    "Target vehicle is not present in the database.",
                    "target_vehicle_id",
                    entity_id=_safe_entity_id(target_vehicle_id),
                )
            )
        start = None
        if start_vehicle_id is not None:
            start = (
                self.database.vehicles.get(start_vehicle_id)
                if isinstance(start_vehicle_id, str)
                else None
            )
            if not isinstance(start_vehicle_id, str) or start is None:
                findings.append(
                    _finding(
                        "INPUT_START_UNKNOWN",
                        ValidationCategory.INVALID_INPUT,
                        "Start vehicle is not present in the database.",
                        "start_vehicle_id",
                        entity_id=_safe_entity_id(start_vehicle_id),
                    )
                )
        if target is not None and start is not None:
            if target.country_id != start.country_id:
                findings.append(
                    _finding(
                        "INPUT_START_COUNTRY_MISMATCH",
                        ValidationCategory.INVALID_INPUT,
                        "Start and target must belong to the same nation.",
                        "start_vehicle_id",
                        entity_id=start.id,
                        details={
                            "startCountry": start.country_id,
                            "targetCountry": target.country_id,
                        },
                    )
                )
            if target.branch_id != start.branch_id:
                findings.append(
                    _finding(
                        "INPUT_START_VEHICLE_TYPE_MISMATCH",
                        ValidationCategory.INVALID_INPUT,
                        "Start and target must belong to the same vehicle type.",
                        "start_vehicle_id",
                        entity_id=start.id,
                        details={
                            "startVehicleType": start.branch_id,
                            "targetVehicleType": target.branch_id,
                        },
                    )
                )

        if not isinstance(progress, PlayerProgress):
            findings.append(
                _finding(
                    "INPUT_PROGRESS_STATUS_INVALID",
                    ValidationCategory.INVALID_INPUT,
                    "progress must be a PlayerProgress instance.",
                    "progress",
                )
            )
        else:
            findings.extend(self._validate_progress(progress))
        if not isinstance(options, SolveOptions):
            findings.append(
                _finding(
                    "INPUT_OPTIMIZE_FOR_INVALID",
                    ValidationCategory.INVALID_INPUT,
                    "options must be a SolveOptions instance.",
                    "options",
                )
            )
        else:
            findings.extend(self._validate_options(options))
        return tuple(findings)

    def _validate_progress(self, progress: PlayerProgress) -> list[PipelineInputFinding]:
        findings: list[PipelineInputFinding] = []
        if not _nonnegative_int(progress.owned_ge):
            findings.append(
                _finding(
                    "INPUT_OWNED_GE_INVALID",
                    ValidationCategory.INVALID_INPUT,
                    "owned_ge must be a non-negative integer.",
                    "progress.owned_ge",
                    details={"value": progress.owned_ge},
                )
            )
        if progress.convertible_rp is not None and not _nonnegative_int(
            progress.convertible_rp
        ):
            findings.append(
                _finding(
                    "INPUT_CONVERTIBLE_RP_INVALID",
                    ValidationCategory.INVALID_INPUT,
                    "convertible_rp must be null or a non-negative integer.",
                    "progress.convertible_rp",
                    details={"value": progress.convertible_rp},
                )
            )
        unlocks = progress.fulfilled_unlocks
        if not isinstance(unlocks, (set, frozenset)) or any(
            not isinstance(item, str) or not item for item in unlocks
        ):
            findings.append(
                _finding(
                    "INPUT_FULFILLED_UNLOCK_INVALID",
                    ValidationCategory.INVALID_INPUT,
                    "fulfilled_unlocks must contain non-empty strings.",
                    "progress.fulfilled_unlocks",
                )
            )
        if not isinstance(progress.vehicles, dict):
            findings.append(
                _finding(
                    "INPUT_PROGRESS_STATUS_INVALID",
                    ValidationCategory.INVALID_INPUT,
                    "progress.vehicles must be a mapping of vehicle progress states.",
                    "progress.vehicles",
                )
            )
            return findings
        for vehicle_id, state in sorted(
            progress.vehicles.items(),
            key=lambda item: str(item[0]),
        ):
            vehicle = self.database.vehicles.get(vehicle_id)
            if vehicle is None:
                findings.append(
                    _finding(
                        "INPUT_PROGRESS_VEHICLE_UNKNOWN",
                        ValidationCategory.INVALID_INPUT,
                        "PlayerProgress references an unknown vehicle.",
                        "progress.vehicles",
                        entity_id=_safe_entity_id(vehicle_id),
                    )
                )
                continue
            if not isinstance(state, VehicleProgress):
                findings.append(
                    _finding(
                        "INPUT_PROGRESS_STATUS_INVALID",
                        ValidationCategory.INVALID_INPUT,
                        "Vehicle progress must use VehicleProgress.",
                        "progress.vehicles",
                        entity_id=vehicle.id,
                    )
                )
                continue
            if not _nonnegative_int(state.researched_rp):
                findings.append(
                    _finding(
                        "INPUT_PROGRESS_RP_NEGATIVE_OR_INVALID",
                        ValidationCategory.INVALID_INPUT,
                        "researched_rp must be a non-negative integer.",
                        "progress.vehicles.researched_rp",
                        entity_id=vehicle.id,
                        details={"value": state.researched_rp},
                    )
                )
            elif state.researched_rp > vehicle.rp:
                findings.append(
                    _finding(
                        "INPUT_PROGRESS_RP_EXCEEDS_TOTAL",
                        ValidationCategory.INVALID_INPUT,
                        "researched_rp exceeds the vehicle RP value.",
                        "progress.vehicles.researched_rp",
                        entity_id=vehicle.id,
                        details={"researchedRp": state.researched_rp, "totalRp": vehicle.rp},
                    )
                )
            if not isinstance(state.researched, bool) or not isinstance(
                state.purchased, bool
            ):
                findings.append(
                    _finding(
                        "INPUT_PROGRESS_STATUS_INVALID",
                        ValidationCategory.INVALID_INPUT,
                        "researched and purchased must be booleans.",
                        "progress.vehicles.status",
                        entity_id=vehicle.id,
                    )
                )
                continue
            if state.purchased and not state.researched:
                findings.append(
                    _finding(
                        "INPUT_PURCHASE_WITHOUT_RESEARCH",
                        ValidationCategory.INVALID_INPUT,
                        "A purchased vehicle must also be marked researched.",
                        "progress.vehicles.purchased",
                        entity_id=vehicle.id,
                    )
                )
            if state.researched and state.researched_rp != vehicle.rp:
                findings.append(
                    _finding(
                        "INPUT_RESEARCH_FLAG_RP_CONFLICT",
                        ValidationCategory.INVALID_INPUT,
                        (
                            "researched=True requires researched_rp to equal the "
                            "vehicle RP value."
                        ),
                        "progress.vehicles.researched_rp",
                        entity_id=vehicle.id,
                        details={"researchedRp": state.researched_rp, "totalRp": vehicle.rp},
                    )
                )
        return findings

    @staticmethod
    def _validate_options(options: SolveOptions) -> list[PipelineInputFinding]:
        findings: list[PipelineInputFinding] = []
        if not isinstance(options.optimize_for, str) or options.optimize_for not in {
            "ge",
            "rp",
            "sl",
            "vehicles",
        }:
            findings.append(
                _finding(
                    "INPUT_OPTIMIZE_FOR_INVALID",
                    ValidationCategory.INVALID_INPUT,
                    "optimize_for must be ge, rp, sl or vehicles.",
                    "options.optimize_for",
                    details={"value": options.optimize_for},
                )
            )
        for rule_id, field_name in (
            ("INPUT_INCLUDE_START_INVALID", "include_start_vehicle"),
            ("INPUT_INCLUDE_HIDDEN_INVALID", "include_hidden_legacy"),
            ("INPUT_ASSUME_EXTERNAL_INVALID", "assume_external_unlocks"),
        ):
            value = getattr(options, field_name)
            if not isinstance(value, bool):
                findings.append(
                    _finding(
                        rule_id,
                        ValidationCategory.INVALID_INPUT,
                        f"{field_name} must be a boolean.",
                        f"options.{field_name}",
                        details={"value": value},
                    )
                )
        if (
            not isinstance(options.sl_discount_percent, int)
            or isinstance(options.sl_discount_percent, bool)
            or options.sl_discount_percent not in ALLOWED_SL_DISCOUNTS
        ):
            findings.append(
                _finding(
                    "INPUT_SL_DISCOUNT_INVALID",
                    ValidationCategory.INVALID_INPUT,
                    "Version 1.0 SL discount must be 0, 30 or 50 percent.",
                    "options.sl_discount_percent",
                    details={
                        "value": options.sl_discount_percent,
                        "allowed": sorted(ALLOWED_SL_DISCOUNTS),
                    },
                )
            )
        return findings


def _finding(
    rule_id: str,
    category: ValidationCategory,
    message: str,
    source_field: str,
    *,
    entity_id: str | None = None,
    details: dict[str, Any] | None = None,
    severity: ValidationSeverity = ValidationSeverity.ERROR,
    blocking: bool = True,
) -> PipelineInputFinding:
    return PipelineInputFinding(
        rule_id=rule_id,
        category=category,
        severity=severity,
        message=message,
        source_field=source_field,
        entity_id=entity_id,
        details=details or {},
        blocking=blocking,
    )


def serialize_progress(progress: PlayerProgress) -> dict[str, Any]:
    vehicles: dict[str, Any] = {}
    if isinstance(progress, PlayerProgress):
        if isinstance(progress.vehicles, dict):
            for vehicle_id, state in sorted(
                progress.vehicles.items(),
                key=lambda item: str(item[0]),
            ):
                if isinstance(state, VehicleProgress):
                    vehicles[str(vehicle_id)] = {
                        "researched_rp": state.researched_rp,
                        "researched": state.researched,
                        "purchased": state.purchased,
                    }
                else:
                    vehicles[str(vehicle_id)] = {
                        "invalidType": type(state).__name__
                    }
        else:
            vehicles = {"invalidType": type(progress.vehicles).__name__}
        unlocks = progress.fulfilled_unlocks
        serialized_unlocks = (
            sorted(str(item) for item in unlocks)
            if isinstance(unlocks, (set, frozenset))
            else [f"invalidType:{type(unlocks).__name__}"]
        )
        return {
            "vehicles": vehicles,
            "convertible_rp": progress.convertible_rp,
            "owned_ge": progress.owned_ge,
            "fulfilled_unlocks": serialized_unlocks,
        }
    return {"invalidType": type(progress).__name__}


def serialize_options(options: SolveOptions) -> dict[str, Any]:
    if not isinstance(options, SolveOptions):
        return {"invalidType": type(options).__name__}
    return {
        "optimize_for": options.optimize_for,
        "include_start_vehicle": options.include_start_vehicle,
        "include_hidden_legacy": options.include_hidden_legacy,
        "assume_external_unlocks": options.assume_external_unlocks,
        "sl_discount_percent": options.sl_discount_percent,
    }


def stable_fingerprint(value: Any, *, version: str) -> str:
    payload = json.dumps(
        canonicalize(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    digest = hashlib.sha256(payload).hexdigest()
    return f"{version}:{digest}"


def canonicalize(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): canonicalize(value[key]) for key in sorted(value, key=str)}
    if isinstance(value, (set, frozenset)):
        return [canonicalize(item) for item in sorted(value, key=str)]
    if isinstance(value, (list, tuple)):
        return [canonicalize(item) for item in value]
    if isinstance(value, Enum):
        return value.value
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        if math.isfinite(value):
            return value
        return {"nonFiniteFloat": str(value)}
    return {"unsupportedType": type(value).__name__}


def _nonnegative_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _positive_int(value: Any) -> bool:
    return _nonnegative_int(value) and value > 0


def _numbered(trace: Iterable[str]) -> tuple[str, ...]:
    return tuple(f"{index:02d}:{item}" for index, item in enumerate(trace, 1))


def _strip_number(value: str) -> str:
    prefix, separator, remainder = value.partition(":")
    return remainder if separator and prefix.isdigit() else value


def _safe_entity_id(value: Any) -> str:
    return value if isinstance(value, str) else f"invalid:{type(value).__name__}"


def _safe_trace_value(value: Any) -> str:
    if value is None:
        return "none"
    return _safe_entity_id(value)
