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
from wurstbrot_core.graph_pipeline import (  # noqa: E402
    GraphCalculationPipeline,
    PipelineStatus,
)
from wurstbrot_core.models import (  # noqa: E402
    PlayerProgress,
    SolveOptions,
    Vehicle,
    VehicleProgress,
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
        game_version="dual-test",
        rp_per_ge=45,
        vehicles={item.id: item for item in vehicles},
        predecessors={
            item.id: vehicles[index - 1].id if index else None
            for index, item in enumerate(vehicles)
        },
        groups={},
        rank_unlock={},
    )


class FixedPipeline:
    def __init__(self, result):
        self.result = result

    def run(self, **_kwargs):
        return self.result


class DualEngineTests(unittest.TestCase):
    def test_runner_returns_exact_full_comparison_and_keeps_legacy_productive(self):
        db = database(vehicle("a", rp=0, sl=0), vehicle("b", rp=46, sl=101))
        result = DualEngineRunner(db).run(
            target_vehicle_id="b",
            start_vehicle_id="a",
        )
        self.assertEqual(result.comparison_status, ComparisonStatus.EXACT_MATCH)
        self.assertFalse(result.differences)
        self.assertEqual(result.diagnostics["productiveResultSource"], "legacy")
        self.assertFalse(result.diagnostics["productiveCallerUsesGraphResult"])
        self.assertIn("required_vehicle_ids", result.comparable_fields)
        excluded = {item["field"] for item in result.excluded_fields}
        self.assertEqual(
            excluded,
            {
                "satisfied_vehicle_ids",
                "folder_requirements",
                "unlock_requirements",
                "evaluation_results",
            },
        )
        json.dumps(result.to_dict(), sort_keys=True)

    def test_out_of_contract_discount_is_rejected_by_both_engines(self):
        db = database(vehicle("target"))
        result = DualEngineRunner(db).run(
            target_vehicle_id="target",
            options=SolveOptions(sl_discount_percent=10),
        )
        self.assertEqual(
            result.comparison_status,
            ComparisonStatus.INPUT_CONTRACT_DIFFERENCE,
        )
        self.assertEqual(result.legacy_result.status, "error")
        self.assertEqual(result.differences[0].rule_ids, ("INPUT_SL_DISCOUNT_INVALID",))

    def test_unresolved_and_blocked_results_are_not_matches(self):
        external_db = database(
            vehicle("external", unlock="unlocked_dual_test")
        )
        unresolved = DualEngineRunner(external_db).run(
            target_vehicle_id="external"
        )
        self.assertEqual(
            unresolved.comparison_status,
            ComparisonStatus.UNRESOLVED_EXPECTED,
        )

        hidden_db = database(vehicle("hidden", hidden=True))
        blocked = DualEngineRunner(hidden_db).run(target_vehicle_id="hidden")
        self.assertEqual(blocked.comparison_status, ComparisonStatus.UNSUPPORTED)

    def test_researched_flag_numeric_conflict_is_a_visible_contract_difference(self):
        db = database(vehicle("target", rp=45))
        result = DualEngineRunner(db).run(
            target_vehicle_id="target",
            progress=PlayerProgress(
                vehicles={
                    "target": VehicleProgress(
                        researched_rp=0,
                        researched=True,
                        purchased=False,
                    )
                }
            ),
        )
        self.assertEqual(
            result.comparison_status,
            ComparisonStatus.INPUT_CONTRACT_DIFFERENCE,
        )
        self.assertIn(
            "INPUT_RESEARCH_FLAG_RP_CONFLICT",
            {item.rule_ids[0] for item in result.differences},
        )
        self.assertEqual(result.legacy_result.status, "error")
        self.assertEqual(result.graph_result.pipeline_status, PipelineStatus.INVALID_INPUT)

    def test_numeric_divergence_is_a_mismatch_with_vehicle_diagnostics(self):
        db = database(vehicle("target", rp=45))
        pipeline = GraphCalculationPipeline(db)
        baseline = pipeline.run(target_vehicle_id="target")
        line = baseline.cost_result.vehicle_cost_lines[0]
        divergent_line = replace(line, ge=line.ge + 1)
        divergent_cost = replace(
            baseline.cost_result,
            vehicle_cost_lines=(divergent_line,),
            total_ge_before_owned=baseline.cost_result.total_ge_before_owned + 1,
            total_ge_after_owned=baseline.cost_result.total_ge_after_owned + 1,
        )
        divergent = replace(baseline, cost_result=divergent_cost)
        result = DualEngineRunner(
            db,
            pipeline=FixedPipeline(divergent),
        ).run(target_vehicle_id="target")
        self.assertEqual(result.comparison_status, ComparisonStatus.MISMATCH)
        fields = {item.field for item in result.differences}
        self.assertIn("vehicle_cost_lines.target.ge", fields)
        self.assertIn("total_ge_before_owned", fields)
        diagnostics = result.diagnostics["nonExactComparison"]
        self.assertEqual(diagnostics["vehicleSetDifferences"]["onlyLegacy"], [])
        self.assertEqual(diagnostics["vehicleSetDifferences"]["onlyGraph"], [])
        self.assertTrue(
            diagnostics["vehicleCostLineDifferences"]["comparisonPerformed"]
        )
        self.assertIn(
            "VEHICLE_COST_LINE_PARITY",
            diagnostics["contractRules"],
        )
        self.assertEqual(
            diagnostics["fingerprints"]["graph"],
            result.graph_result.fingerprint,
        )

    def test_representation_only_difference_is_equivalent(self):
        db = database(vehicle("a"), vehicle("b"))
        pipeline = GraphCalculationPipeline(db)
        baseline = pipeline.run(target_vehicle_id="b")
        reversed_resolution = replace(
            baseline.prerequisite_resolution,
            required_vehicle_ids=tuple(
                reversed(baseline.prerequisite_resolution.required_vehicle_ids)
            ),
        )
        reversed_cost = replace(
            baseline.cost_result,
            vehicle_cost_lines=tuple(reversed(baseline.cost_result.vehicle_cost_lines)),
        )
        represented = replace(
            baseline,
            prerequisite_resolution=reversed_resolution,
            cost_result=reversed_cost,
        )
        result = DualEngineRunner(
            db,
            pipeline=FixedPipeline(represented),
        ).run(target_vehicle_id="b")
        self.assertEqual(result.comparison_status, ComparisonStatus.EQUIVALENT_MATCH)
        self.assertTrue(all(item.representation_only for item in result.differences))

    def test_internal_error_is_never_classified_as_unresolved(self):
        class ExplodingEvaluator:
            version = "test"

            def evaluate(self, **_kwargs):
                raise RuntimeError("internal")

        db = database(vehicle("target"))
        pipeline = GraphCalculationPipeline(db, evaluator=ExplodingEvaluator())
        result = DualEngineRunner(db, pipeline=pipeline).run(
            target_vehicle_id="target"
        )
        self.assertEqual(result.comparison_status, ComparisonStatus.INTERNAL_ERROR)
        self.assertNotEqual(
            result.comparison_status,
            ComparisonStatus.UNRESOLVED_EXPECTED,
        )

    def test_dual_fingerprint_is_stable_and_changes_with_domain_input(self):
        db = database(vehicle("target"))
        runner = DualEngineRunner(db)
        first = runner.run(target_vehicle_id="target")
        second = runner.run(target_vehicle_id="target")
        changed = runner.run(
            target_vehicle_id="target",
            progress=PlayerProgress(owned_ge=1),
        )
        self.assertEqual(first.fingerprint, second.fingerprint)
        self.assertNotEqual(first.fingerprint, changed.fingerprint)
        self.assertTrue(first.fingerprint.startswith("dual-engine-comparison-v1:"))


if __name__ == "__main__":
    unittest.main()
