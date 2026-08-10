from __future__ import annotations

import json
import sys
import unittest
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "core"))

from wurstbrot_core.database import VehicleDatabase  # noqa: E402
from wurstbrot_core.dual_engine import (  # noqa: E402
    ComparisonStatus,
    DualEngineRunner,
)
from wurstbrot_core.engine_execution import (  # noqa: E402
    CalculationEngine,
    CalculationStatus,
    EngineFeatureFlags,
    ExecutionMode,
    FallbackReason,
    GraphCalculationResultAdapter,
    ResultAdapterContractError,
    ResultSource,
    serialize_solve_result,
)
from wurstbrot_core.graph_pipeline import (  # noqa: E402
    GraphCalculationPipeline,
    PipelineStatus,
)
from wurstbrot_core.models import (  # noqa: E402
    PlayerProgress,
    SolveOptions,
    Vehicle,
)


def vehicle(
    vehicle_id: str,
    *,
    rp: int = 45,
    sl: int = 100,
    hidden: bool = False,
    unlock: str = "",
) -> Vehicle:
    return Vehicle(
        id=vehicle_id,
        name=vehicle_id.upper(),
        country_id="country_test",
        branch_id="army",
        rank=1,
        rp=rp,
        sl=sl,
        hidden_research=hidden,
        req_unlock=unlock,
    )


def database(*vehicles: Vehicle) -> VehicleDatabase:
    return VehicleDatabase(
        game_version="execution-test",
        rp_per_ge=45,
        vehicles={item.id: item for item in vehicles},
        predecessors={
            item.id: vehicles[index - 1].id if index else None
            for index, item in enumerate(vehicles)
        },
        groups={},
        rank_unlock={},
    )


class TrackingDualRunner:
    def __init__(self, runner: DualEngineRunner) -> None:
        self.runner = runner
        self.calls = 0

    def run(self, **kwargs):
        self.calls += 1
        return self.runner.run(**kwargs)


class FixedDualRunner:
    def __init__(self, result) -> None:
        self.result = result

    def run(self, **_kwargs):
        return self.result


class ExplodingDualRunner:
    def run(self, **_kwargs):
        raise RuntimeError("deliberate dual-runner failure")


class RejectingAdapter:
    version = "test"

    def adapt(self, _result):
        raise ResultAdapterContractError("deliberate contract failure")


class ExplodingAdapter:
    version = "test"

    def adapt(self, _result):
        raise RuntimeError("deliberate internal adapter failure")


class EngineExecutionTests(unittest.TestCase):
    def setUp(self):
        self.database = database(
            vehicle("a", rp=0, sl=0),
            vehicle("b", rp=46, sl=101),
        )

    def test_default_mode_is_legacy_only_and_does_not_execute_graph(self):
        dual = TrackingDualRunner(DualEngineRunner(self.database))
        engine = CalculationEngine(self.database, dual_runner=dual)

        result = engine.calculate(target_vehicle_id="b", start_vehicle_id="a")

        self.assertEqual(result.requested_mode, ExecutionMode.LEGACY)
        self.assertEqual(result.result_source, ResultSource.LEGACY)
        self.assertEqual(result.calculation_status, CalculationStatus.COMPLETE)
        self.assertEqual(dual.calls, 0)
        self.assertFalse(result.shadow_comparison_exists)
        self.assertFalse(result.experimental)
        self.assertEqual(result.diagnostics["defaultMode"], "legacy")

    def test_exactly_three_execution_modes_exist(self):
        self.assertEqual(
            {item.value for item in ExecutionMode},
            {"legacy", "shadow", "graph_experimental"},
        )

    def test_disabled_feature_flag_uses_visible_legacy_fallback_without_graph(self):
        dual = TrackingDualRunner(DualEngineRunner(self.database))
        result = CalculationEngine(self.database, dual_runner=dual).calculate(
            target_vehicle_id="b",
            mode=ExecutionMode.GRAPH_EXPERIMENTAL,
        )

        self.assertEqual(result.result_source, ResultSource.LEGACY)
        self.assertTrue(result.fallback_applied)
        self.assertEqual(
            result.fallback_reason,
            FallbackReason.GRAPH_FEATURE_DISABLED,
        )
        self.assertEqual(dual.calls, 0)
        self.assertFalse(result.shadow_comparison_exists)
        self.assertFalse(result.diagnostics["graphExperimentalFeatureEnabled"])

    def test_feature_flag_activation_is_process_local_and_not_persistent(self):
        enabled = EngineFeatureFlags.explicit_graph_experimental()

        self.assertTrue(enabled.graph_experimental_enabled)
        self.assertFalse(EngineFeatureFlags().graph_experimental_enabled)
        self.assertFalse(EngineFeatureFlags().graph_experimental_enabled)

    def test_shadow_returns_the_exact_legacy_user_result(self):
        engine = CalculationEngine(self.database)
        legacy = engine.calculate(target_vehicle_id="b", start_vehicle_id="a")
        shadow = engine.calculate(
            target_vehicle_id="b",
            start_vehicle_id="a",
            mode=ExecutionMode.SHADOW,
        )

        self.assertEqual(shadow.result, legacy.result)
        self.assertEqual(shadow.result_source, ResultSource.LEGACY)
        self.assertEqual(shadow.comparison_status, ComparisonStatus.EXACT_MATCH)
        self.assertTrue(shadow.shadow_comparison_exists)
        self.assertFalse(shadow.fallback_applied)

    def test_unexpected_shadow_runner_error_cannot_change_legacy_user_result(self):
        engine = CalculationEngine(self.database, dual_runner=ExplodingDualRunner())
        legacy = engine.calculate(target_vehicle_id="b", start_vehicle_id="a")
        shadow = engine.calculate(
            target_vehicle_id="b",
            start_vehicle_id="a",
            mode=ExecutionMode.SHADOW,
        )

        self.assertEqual(shadow.result, legacy.result)
        self.assertEqual(shadow.result_source, ResultSource.LEGACY)
        self.assertEqual(shadow.graph_status, PipelineStatus.INTERNAL_ERROR)
        self.assertEqual(shadow.comparison_status, ComparisonStatus.INTERNAL_ERROR)
        self.assertFalse(shadow.fallback_applied)
        self.assertEqual(shadow.diagnostics["failedStage"], "DualEngineRunner")

    def test_shadow_mismatch_cannot_change_legacy_user_result(self):
        baseline = DualEngineRunner(self.database).run(target_vehicle_id="b")
        mismatch = replace(
            baseline,
            comparison_status=ComparisonStatus.MISMATCH,
        )
        engine = CalculationEngine(
            self.database,
            dual_runner=FixedDualRunner(mismatch),
        )
        legacy = engine.calculate(target_vehicle_id="b")
        shadow = engine.calculate(
            target_vehicle_id="b",
            mode=ExecutionMode.SHADOW,
        )

        self.assertEqual(shadow.result, legacy.result)
        self.assertEqual(shadow.result_source, ResultSource.LEGACY)
        self.assertEqual(shadow.comparison_status, ComparisonStatus.MISMATCH)
        self.assertFalse(shadow.fallback_applied)

    def test_graph_experimental_uses_adapted_graph_result_only_for_exact_complete(self):
        engine = CalculationEngine(
            self.database,
            feature_flags=EngineFeatureFlags.explicit_graph_experimental(),
        )
        result = engine.calculate(
            target_vehicle_id="b",
            start_vehicle_id="a",
            progress=PlayerProgress(owned_ge=1, convertible_rp=20),
            options=SolveOptions(sl_discount_percent=30),
            mode=ExecutionMode.GRAPH_EXPERIMENTAL,
        )

        self.assertEqual(result.result_source, ResultSource.GRAPH)
        self.assertEqual(result.graph_status, PipelineStatus.COMPLETE)
        self.assertEqual(result.comparison_status, ComparisonStatus.EXACT_MATCH)
        self.assertFalse(result.fallback_applied)
        self.assertTrue(result.experimental)
        self.assertEqual(result.result.total_rp, 46)
        self.assertEqual(result.result.total_ge_before_owned, 2)
        self.assertEqual(result.result.total_ge_after_owned, 1)
        self.assertEqual(result.result.total_sl, 71)
        self.assertEqual(result.result.convertible_rp_shortfall, 26)

    def test_adapter_preserves_every_existing_user_cost_field(self):
        progress = PlayerProgress(owned_ge=1, convertible_rp=20)
        options = SolveOptions(sl_discount_percent=50)
        dual = DualEngineRunner(self.database).run(
            target_vehicle_id="b",
            start_vehicle_id="a",
            progress=progress,
            options=options,
        )
        adapted = GraphCalculationResultAdapter(self.database).adapt(dual)

        self.assertEqual(
            serialize_solve_result(adapted),
            dual.legacy_result.result,
        )

    def test_adapter_does_not_replace_existing_user_warning_contract(self):
        db = database(vehicle("hidden", hidden=True))
        dual = DualEngineRunner(db).run(
            target_vehicle_id="hidden",
            options=SolveOptions(include_hidden_legacy=True),
        )
        adapted = GraphCalculationResultAdapter(db).adapt(dual)

        self.assertEqual(
            adapted.warnings,
            tuple(dual.legacy_result.result["warnings"]),
        )
        self.assertNotEqual(adapted.warnings, dual.graph_result.cost_result.warnings)

    def test_partial_graph_result_uses_visible_legacy_fallback(self):
        db = database(vehicle("external", unlock="external_unlock"))
        engine = CalculationEngine(
            db,
            feature_flags=EngineFeatureFlags.explicit_graph_experimental(),
        )
        legacy = engine.calculate(target_vehicle_id="external")
        result = engine.calculate(
            target_vehicle_id="external",
            mode=ExecutionMode.GRAPH_EXPERIMENTAL,
        )

        self.assertEqual(result.graph_status, PipelineStatus.PARTIAL)
        self.assertEqual(result.result_source, ResultSource.LEGACY)
        self.assertTrue(result.fallback_applied)
        self.assertEqual(result.fallback_reason, FallbackReason.GRAPH_PARTIAL)
        self.assertEqual(result.calculation_status, CalculationStatus.COMPLETE)
        self.assertEqual(result.result, legacy.result)
        payload = result.to_dict()
        self.assertEqual(payload["requested_engine"], "graph_experimental")
        self.assertEqual(payload["result_source"], "legacy")
        self.assertTrue(payload["fallback_used"])
        self.assertEqual(payload["fallback_reason"], "graph_partial")
        self.assertEqual(payload["pipeline_status"], "partial")
        self.assertEqual(payload["comparison_status"], "unresolved_expected")

    def test_invalid_graph_input_is_rejected_even_when_legacy_accepts_it(self):
        result = CalculationEngine(
            self.database,
            feature_flags=EngineFeatureFlags.explicit_graph_experimental(),
        ).calculate(
            target_vehicle_id="b",
            options=SolveOptions(sl_discount_percent=10),
            mode=ExecutionMode.GRAPH_EXPERIMENTAL,
        )

        self.assertEqual(result.graph_status, PipelineStatus.INVALID_INPUT)
        self.assertIsNone(result.result_source)
        self.assertIsNone(result.result)
        self.assertEqual(result.calculation_status, CalculationStatus.UNAVAILABLE)
        self.assertEqual(
            result.comparison_status,
            ComparisonStatus.INPUT_CONTRACT_DIFFERENCE,
        )
        self.assertFalse(result.fallback_applied)
        self.assertEqual(
            result.fallback_reason,
            FallbackReason.GRAPH_INVALID_INPUT,
        )
        self.assertTrue(result.diagnostics["invalidInputRejected"])
        self.assertTrue(result.diagnostics["legacyResultDiscarded"])

    def test_nonblocking_invalid_input_difference_is_not_made_valid_by_legacy(self):
        from wurstbrot_core.models import VehicleProgress

        result = CalculationEngine(
            self.database,
            feature_flags=EngineFeatureFlags.explicit_graph_experimental(),
        ).calculate(
            target_vehicle_id="b",
            progress=PlayerProgress(
                vehicles={"b": VehicleProgress(researched=True, researched_rp=0)}
            ),
            mode=ExecutionMode.GRAPH_EXPERIMENTAL,
        )

        self.assertEqual(result.graph_status, PipelineStatus.COMPLETE)
        self.assertEqual(
            result.comparison_status,
            ComparisonStatus.INPUT_CONTRACT_DIFFERENCE,
        )
        self.assertIsNone(result.result_source)
        self.assertIsNone(result.result)
        self.assertFalse(result.fallback_applied)
        self.assertEqual(result.fallback_reason, FallbackReason.GRAPH_INVALID_INPUT)

    def test_internal_error_uses_legacy_fallback_and_is_not_unresolved(self):
        class ExplodingEvaluator:
            version = "test"

            def evaluate(self, **_kwargs):
                raise RuntimeError("deliberate internal failure")

        pipeline = GraphCalculationPipeline(
            self.database,
            evaluator=ExplodingEvaluator(),
        )
        result = CalculationEngine(
            self.database,
            feature_flags=EngineFeatureFlags.explicit_graph_experimental(),
            dual_runner=DualEngineRunner(self.database, pipeline=pipeline),
        ).calculate(
            target_vehicle_id="b",
            mode=ExecutionMode.GRAPH_EXPERIMENTAL,
        )

        self.assertEqual(result.graph_status, PipelineStatus.INTERNAL_ERROR)
        self.assertEqual(result.result_source, ResultSource.LEGACY)
        self.assertEqual(result.comparison_status, ComparisonStatus.INTERNAL_ERROR)
        self.assertTrue(result.fallback_applied)
        self.assertEqual(
            result.fallback_reason,
            FallbackReason.GRAPH_INTERNAL_ERROR,
        )

    def test_unexpected_dual_runner_error_uses_visible_legacy_fallback(self):
        result = CalculationEngine(
            self.database,
            feature_flags=EngineFeatureFlags.explicit_graph_experimental(),
            dual_runner=ExplodingDualRunner(),
        ).calculate(
            target_vehicle_id="b",
            mode=ExecutionMode.GRAPH_EXPERIMENTAL,
        )

        self.assertEqual(result.result_source, ResultSource.LEGACY)
        self.assertTrue(result.fallback_applied)
        self.assertEqual(result.graph_status, PipelineStatus.INTERNAL_ERROR)
        self.assertEqual(result.comparison_status, ComparisonStatus.INTERNAL_ERROR)
        self.assertEqual(result.fallback_reason, FallbackReason.GRAPH_INTERNAL_ERROR)

    def test_unavailable_and_mismatch_results_are_never_used_as_graph_output(self):
        baseline = DualEngineRunner(self.database).run(target_vehicle_id="b")
        unavailable_contract = replace(
            baseline.graph_result.status_contract,
            status=PipelineStatus.UNAVAILABLE,
            cause="test_unavailable",
            comparable_to_legacy=False,
        )
        unavailable_graph = replace(
            baseline.graph_result,
            pipeline_status=PipelineStatus.UNAVAILABLE,
            status_contract=unavailable_contract,
        )
        unavailable_dual = replace(
            baseline,
            graph_result=unavailable_graph,
            comparison_status=ComparisonStatus.UNSUPPORTED,
        )
        unavailable = CalculationEngine(
            self.database,
            feature_flags=EngineFeatureFlags.explicit_graph_experimental(),
            dual_runner=FixedDualRunner(unavailable_dual),
        ).calculate(
            target_vehicle_id="b",
            mode=ExecutionMode.GRAPH_EXPERIMENTAL,
        )
        mismatch_dual = replace(
            baseline,
            comparison_status=ComparisonStatus.MISMATCH,
        )
        mismatch = CalculationEngine(
            self.database,
            feature_flags=EngineFeatureFlags.explicit_graph_experimental(),
            dual_runner=FixedDualRunner(mismatch_dual),
        ).calculate(
            target_vehicle_id="b",
            mode=ExecutionMode.GRAPH_EXPERIMENTAL,
        )

        self.assertEqual(unavailable.result_source, ResultSource.LEGACY)
        self.assertEqual(
            unavailable.fallback_reason,
            FallbackReason.GRAPH_UNAVAILABLE,
        )
        self.assertEqual(mismatch.result_source, ResultSource.LEGACY)
        self.assertEqual(
            mismatch.fallback_reason,
            FallbackReason.COMPARISON_NOT_EXACT,
        )

    def test_blocked_and_unsupported_results_use_visible_legacy_fallback(self):
        baseline = DualEngineRunner(self.database).run(target_vehicle_id="b")
        blocked_contract = replace(
            baseline.graph_result.status_contract,
            status=PipelineStatus.BLOCKED,
            cause="blocking_rule",
            comparable_to_legacy=False,
        )
        blocked_dual = replace(
            baseline,
            graph_result=replace(
                baseline.graph_result,
                pipeline_status=PipelineStatus.BLOCKED,
                status_contract=blocked_contract,
            ),
            comparison_status=ComparisonStatus.UNRESOLVED_EXPECTED,
        )
        unsupported_contract = replace(
            baseline.graph_result.status_contract,
            status=PipelineStatus.UNAVAILABLE,
            cause="unsupported_feature",
            comparable_to_legacy=False,
        )
        unsupported_dual = replace(
            baseline,
            graph_result=replace(
                baseline.graph_result,
                pipeline_status=PipelineStatus.UNAVAILABLE,
                status_contract=unsupported_contract,
            ),
            comparison_status=ComparisonStatus.UNSUPPORTED,
        )

        blocked = CalculationEngine(
            self.database,
            feature_flags=EngineFeatureFlags.explicit_graph_experimental(),
            dual_runner=FixedDualRunner(blocked_dual),
        ).calculate(target_vehicle_id="b", mode=ExecutionMode.GRAPH_EXPERIMENTAL)
        unsupported = CalculationEngine(
            self.database,
            feature_flags=EngineFeatureFlags.explicit_graph_experimental(),
            dual_runner=FixedDualRunner(unsupported_dual),
        ).calculate(target_vehicle_id="b", mode=ExecutionMode.GRAPH_EXPERIMENTAL)

        self.assertEqual(blocked.result_source, ResultSource.LEGACY)
        self.assertTrue(blocked.fallback_applied)
        self.assertEqual(blocked.fallback_reason, FallbackReason.GRAPH_BLOCKED)
        self.assertEqual(unsupported.result_source, ResultSource.LEGACY)
        self.assertTrue(unsupported.fallback_applied)
        self.assertEqual(unsupported.comparison_status, ComparisonStatus.UNSUPPORTED)
        self.assertEqual(
            unsupported.fallback_reason,
            FallbackReason.GRAPH_UNAVAILABLE,
        )

    def test_equivalent_match_is_not_accepted_as_graph_user_result(self):
        baseline = DualEngineRunner(self.database).run(target_vehicle_id="b")
        equivalent = replace(
            baseline,
            comparison_status=ComparisonStatus.EQUIVALENT_MATCH,
        )
        result = CalculationEngine(
            self.database,
            feature_flags=EngineFeatureFlags.explicit_graph_experimental(),
            dual_runner=FixedDualRunner(equivalent),
        ).calculate(target_vehicle_id="b", mode=ExecutionMode.GRAPH_EXPERIMENTAL)

        self.assertEqual(result.result_source, ResultSource.LEGACY)
        self.assertTrue(result.fallback_applied)
        self.assertEqual(result.fallback_reason, FallbackReason.COMPARISON_NOT_EXACT)

    def test_adapter_contract_violation_falls_back_without_leaking_exception(self):
        result = CalculationEngine(
            self.database,
            feature_flags=EngineFeatureFlags.explicit_graph_experimental(),
            graph_adapter=RejectingAdapter(),
        ).calculate(
            target_vehicle_id="b",
            mode=ExecutionMode.GRAPH_EXPERIMENTAL,
        )

        self.assertEqual(result.result_source, ResultSource.LEGACY)
        self.assertTrue(result.fallback_applied)
        self.assertEqual(
            result.fallback_reason,
            FallbackReason.ADAPTER_CONTRACT_VIOLATION,
        )
        self.assertEqual(
            result.diagnostics["adapterErrorType"],
            "ResultAdapterContractError",
        )

    def test_unexpected_adapter_error_uses_internal_error_fallback(self):
        result = CalculationEngine(
            self.database,
            feature_flags=EngineFeatureFlags.explicit_graph_experimental(),
            graph_adapter=ExplodingAdapter(),
        ).calculate(
            target_vehicle_id="b",
            mode=ExecutionMode.GRAPH_EXPERIMENTAL,
        )

        self.assertEqual(result.result_source, ResultSource.LEGACY)
        self.assertTrue(result.fallback_applied)
        self.assertEqual(
            result.fallback_reason,
            FallbackReason.GRAPH_INTERNAL_ERROR,
        )
        self.assertEqual(result.diagnostics["adapterErrorType"], "RuntimeError")
        self.assertEqual(
            result.diagnostics["failedStage"],
            "GraphCalculationResultAdapter",
        )

    def test_output_and_fingerprint_are_deterministic_and_domain_sensitive(self):
        engine = CalculationEngine(
            self.database,
            feature_flags=EngineFeatureFlags.explicit_graph_experimental(),
        )
        first = engine.calculate(
            target_vehicle_id="b",
            mode=ExecutionMode.GRAPH_EXPERIMENTAL,
        )
        second = engine.calculate(
            target_vehicle_id="b",
            mode=ExecutionMode.GRAPH_EXPERIMENTAL,
        )
        changed = engine.calculate(
            target_vehicle_id="b",
            progress=PlayerProgress(owned_ge=1),
            mode=ExecutionMode.GRAPH_EXPERIMENTAL,
        )

        self.assertEqual(first, second)
        self.assertEqual(first.to_dict(), second.to_dict())
        self.assertNotEqual(first.fingerprint, changed.fingerprint)
        self.assertTrue(first.fingerprint.startswith("calculation-execution-v1:"))
        json.dumps(first.to_dict(), sort_keys=True)

        payload = first.to_dict()
        self.assertEqual(payload["requested_engine"], "graph_experimental")
        self.assertEqual(payload["result_source"], "graph")
        self.assertFalse(payload["fallback_used"])
        self.assertIsNone(payload["fallback_reason"])
        self.assertEqual(payload["pipeline_status"], "complete")
        self.assertEqual(payload["comparison_status"], "exact_match")


if __name__ == "__main__":
    unittest.main()
