from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "core"))

from wurstbrot_core.database import VehicleDatabase  # noqa: E402
from wurstbrot_core.graph_adapter import GraphDatabaseAdapter  # noqa: E402
from wurstbrot_core.graph_pipeline import (  # noqa: E402
    DATAMINE_VALIDATION_RULE_IDS,
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
    country: str = "country_test",
    branch: str = "army",
    rp: int = 45,
    sl: int = 100,
    hidden: bool = False,
    unlock: str = "",
) -> Vehicle:
    return Vehicle(
        id=vehicle_id,
        name=vehicle_id.upper(),
        country_id=country,
        branch_id=branch,
        rank=1,
        rp=rp,
        sl=sl,
        hidden_research=hidden,
        req_unlock=unlock,
    )


def database(*vehicles: Vehicle, rp_per_ge: int = 45) -> VehicleDatabase:
    return VehicleDatabase(
        game_version="pipeline-test",
        rp_per_ge=rp_per_ge,
        vehicles={item.id: item for item in vehicles},
        predecessors={
            item.id: vehicles[index - 1].id if index else None
            for index, item in enumerate(vehicles)
            if item.country_id == vehicles[0].country_id
            and item.branch_id == vehicles[0].branch_id
        }
        | {
            item.id: None
            for item in vehicles
            if item.country_id != vehicles[0].country_id
            or item.branch_id != vehicles[0].branch_id
        },
        groups={},
        rank_unlock={},
    )


class GraphPipelineTests(unittest.TestCase):
    def test_pipeline_orchestrates_all_components_deterministically(self):
        db = database(vehicle("a", rp=0, sl=0), vehicle("b", rp=46, sl=101))
        pipeline = GraphCalculationPipeline(db)
        first = pipeline.run(target_vehicle_id="b", start_vehicle_id="a")
        second = pipeline.run(target_vehicle_id="b", start_vehicle_id="a")
        self.assertEqual(first, second)
        self.assertEqual(first.pipeline_status, PipelineStatus.COMPLETE)
        self.assertIsNotNone(first.evaluation_report)
        self.assertIsNotNone(first.prerequisite_resolution)
        self.assertIsNotNone(first.cost_result)
        self.assertTrue(first.fingerprint.startswith("graph-pipeline-fingerprint-v1:"))
        self.assertEqual(
            first.evidence["delegatedComponents"],
            (
                "GraphRuleEvaluator",
                "GraphPrerequisiteResolver",
                "GraphCostEngine",
            ),
        )
        json.dumps(first.to_dict(), sort_keys=True)

    def test_pipeline_accepts_graph_database_adapter(self):
        db = database(vehicle("target"))
        result = GraphCalculationPipeline(GraphDatabaseAdapter(db)).run(
            target_vehicle_id="target"
        )
        self.assertEqual(result.pipeline_status, PipelineStatus.COMPLETE)
        self.assertEqual(result.evidence["sourceKind"], "GraphDatabaseAdapter")

    def test_resolution_statuses_propagate_to_partial_and_blocked(self):
        db = database(
            vehicle("external", unlock="unlocked_pipeline_test"),
            vehicle("hidden", hidden=True),
        )
        pipeline = GraphCalculationPipeline(db)
        partial = pipeline.run(target_vehicle_id="external")
        self.assertEqual(partial.pipeline_status, PipelineStatus.PARTIAL)
        self.assertEqual(partial.status_contract.cause, "unresolved_rule")
        self.assertIsNone(partial.cost_result.total_remaining_rp)
        self.assertFalse(partial.status_contract.comparable_to_legacy)

        blocked = pipeline.run(target_vehicle_id="hidden")
        self.assertEqual(blocked.pipeline_status, PipelineStatus.BLOCKED)
        self.assertTrue(blocked.status_contract.blocking)

    def test_input_boundary_rejects_unknown_and_cross_tree_requests(self):
        db = database(
            vehicle("target"),
            vehicle("other_country", country="country_other"),
            vehicle("other_type", branch="aviation"),
        )
        pipeline = GraphCalculationPipeline(db)
        unknown = pipeline.run(target_vehicle_id="missing")
        self.assertEqual(unknown.pipeline_status, PipelineStatus.INVALID_INPUT)
        self.assertEqual(
            {item.rule_id for item in unknown.input_findings},
            {"INPUT_TARGET_UNKNOWN"},
        )
        cross = pipeline.run(
            target_vehicle_id="target",
            start_vehicle_id="other_country",
        )
        self.assertIn(
            "INPUT_START_COUNTRY_MISMATCH",
            {item.rule_id for item in cross.input_findings},
        )
        other_type = pipeline.run(
            target_vehicle_id="target",
            start_vehicle_id="other_type",
        )
        self.assertIn(
            "INPUT_START_VEHICLE_TYPE_MISMATCH",
            {item.rule_id for item in other_type.input_findings},
        )

    def test_progress_and_options_are_validated_without_clamping(self):
        db = database(vehicle("target", rp=45))
        pipeline = GraphCalculationPipeline(db)
        negative = pipeline.run(
            target_vehicle_id="target",
            progress=PlayerProgress(
                vehicles={"target": VehicleProgress(researched_rp=-1)}
            ),
        )
        self.assertEqual(negative.pipeline_status, PipelineStatus.INVALID_INPUT)
        self.assertIn(
            "INPUT_PROGRESS_RP_NEGATIVE_OR_INVALID",
            {item.rule_id for item in negative.input_findings},
        )
        discount = pipeline.run(
            target_vehicle_id="target",
            options=SolveOptions(sl_discount_percent=10),
        )
        self.assertIn(
            "INPUT_SL_DISCOUNT_INVALID",
            {item.rule_id for item in discount.input_findings},
        )

    def test_malformed_container_values_remain_structured_invalid_input(self):
        db = database(vehicle("target", rp=45))
        pipeline = GraphCalculationPipeline(db)
        unknown = pipeline.run(target_vehicle_id=["target"])  # type: ignore[arg-type]
        self.assertEqual(unknown.pipeline_status, PipelineStatus.INVALID_INPUT)
        self.assertIn(
            "INPUT_TARGET_UNKNOWN",
            {item.rule_id for item in unknown.input_findings},
        )

        malformed_progress = pipeline.run(
            target_vehicle_id="target",
            progress=PlayerProgress(vehicles=None),  # type: ignore[arg-type]
        )
        self.assertEqual(
            malformed_progress.pipeline_status,
            PipelineStatus.INVALID_INPUT,
        )
        self.assertIn(
            "INPUT_PROGRESS_STATUS_INVALID",
            {item.rule_id for item in malformed_progress.input_findings},
        )

        malformed_options = pipeline.run(
            target_vehicle_id="target",
            options=SolveOptions(optimize_for={}),  # type: ignore[arg-type]
        )
        self.assertEqual(
            malformed_options.pipeline_status,
            PipelineStatus.INVALID_INPUT,
        )
        json.dumps(malformed_options.to_dict(), sort_keys=True)

    def test_researched_flag_rp_conflict_is_visible_and_not_silent(self):
        db = database(vehicle("target", rp=45))
        result = GraphCalculationPipeline(db).run(
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
        conflict = next(
            item
            for item in result.input_findings
            if item.rule_id == "INPUT_RESEARCH_FLAG_RP_CONFLICT"
        )
        self.assertTrue(conflict.blocking)
        self.assertEqual(result.pipeline_status, PipelineStatus.INVALID_INPUT)
        self.assertEqual(conflict.severity.value, "error")

    def test_all_datamine_errors_are_distinct_from_invalid_input(self):
        invalid_version = database(vehicle("target"))
        invalid_version.game_version = " "
        databases = (
            invalid_version,
            database(vehicle("target"), rp_per_ge=0),
            database(vehicle("target", rp=-1)),
        )
        observed: set[str] = set()
        for db in databases:
            with self.subTest(game_version=db.game_version, rp_per_ge=db.rp_per_ge):
                result = GraphCalculationPipeline(db).run(target_vehicle_id="target")
                self.assertEqual(result.pipeline_status, PipelineStatus.UNAVAILABLE)
                self.assertEqual(result.status_contract.cause, "datamine_error")
                observed.update(result.status_contract.affected_rule_ids)
        self.assertEqual(observed, set(DATAMINE_VALIDATION_RULE_IDS))

    def test_internal_exceptions_are_sanitized_and_not_unresolved(self):
        class ExplodingEvaluator:
            version = "test"

            def evaluate(self, **_kwargs):
                raise RuntimeError("secret implementation detail")

        db = database(vehicle("target"))
        result = GraphCalculationPipeline(db, evaluator=ExplodingEvaluator()).run(
            target_vehicle_id="target"
        )
        serialized = json.dumps(result.to_dict(), sort_keys=True)
        self.assertEqual(result.pipeline_status, PipelineStatus.INTERNAL_ERROR)
        self.assertNotIn("secret implementation detail", serialized)
        self.assertEqual(
            result.status_contract.evidence["errorCode"],
            "PIPELINE_COMPONENT_FAILURE",
        )

    def test_input_validation_internal_error_is_sanitized(self):
        db = database(vehicle("target"))
        pipeline = GraphCalculationPipeline(db)

        def explode(*_args):
            raise RuntimeError("private validation failure")

        pipeline._validate_request = explode  # type: ignore[method-assign]
        result = pipeline.run(target_vehicle_id="target")
        serialized = json.dumps(result.to_dict(), sort_keys=True)
        self.assertEqual(result.pipeline_status, PipelineStatus.INTERNAL_ERROR)
        self.assertNotIn("private validation failure", serialized)
        self.assertEqual(
            result.status_contract.evidence["errorCode"],
            "PIPELINE_INPUT_VALIDATION_FAILURE",
        )

    def test_fingerprint_changes_only_with_canonical_domain_content(self):
        db = database(vehicle("target", rp=45))
        pipeline = GraphCalculationPipeline(db)
        baseline = pipeline.run(target_vehicle_id="target")
        repeated = pipeline.run(target_vehicle_id="target")
        changed = pipeline.run(
            target_vehicle_id="target",
            progress=PlayerProgress(
                vehicles={"target": VehicleProgress(researched_rp=1)}
            ),
        )
        self.assertEqual(baseline.fingerprint, repeated.fingerprint)
        self.assertNotEqual(baseline.fingerprint, changed.fingerprint)


if __name__ == "__main__":
    unittest.main()
