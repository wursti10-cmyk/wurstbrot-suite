import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "core"))

from wurstbrot_core import (  # noqa: E402
    CostShadowCase,
    CostStatus,
    GraphCostEngine,
    GraphPrerequisiteResolver,
    LegacyRankCompatibilityStrategy,
    PlayerProgress,
    PrerequisiteResolution,
    ResearchGraphBuilder,
    ResolutionStatus,
    SolveOptions,
    VehicleDatabase,
    VehicleProgress,
    build_cost_scenarios,
    build_cost_special_case_matrix,
    render_cost_special_case_markdown,
    run_cost_shadow_comparison,
)
from wurstbrot_core.models import Vehicle  # noqa: E402


def vehicle(
    vehicle_id: str,
    *,
    rp: int = 45,
    sl: int = 100,
    reserve: bool = False,
    rank: int = 1,
) -> Vehicle:
    return Vehicle(
        id=vehicle_id,
        name=vehicle_id.upper(),
        country_id="country_test",
        branch_id="army",
        rank=rank,
        rp=rp,
        sl=sl,
        reserve=reserve,
    )


def database(*vehicles: Vehicle, rp_per_ge: int = 45, predecessors=None) -> VehicleDatabase:
    items = {item.id: item for item in vehicles}
    predecessor_map = {item.id: None for item in vehicles}
    predecessor_map.update(predecessors or {})
    return VehicleDatabase(
        game_version="cost-test",
        rp_per_ge=rp_per_ge,
        vehicles=items,
        predecessors=predecessor_map,
        groups={},
        rank_unlock={},
    )


def resolution(
    target: str,
    required=(),
    *,
    satisfied=(),
    start=None,
    status=ResolutionStatus.RESOLVED,
) -> PrerequisiteResolution:
    return PrerequisiteResolution(
        target_vehicle_id=target,
        start_vehicle_id=start,
        required_vehicle_ids=tuple(required),
        satisfied_vehicle_ids=tuple(satisfied),
        blocking_rule_results=(),
        unresolved_rule_results=(),
        rank_requirements=(),
        folder_requirements=(),
        unlock_requirements=(),
        resolution_status=status,
        evidence={"fixture": True},
        explanation_trace=("01:fixture",),
        compatibility_mode=False,
    )


class GraphCostTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sample_database = VehicleDatabase.from_json(
            ROOT / "data" / "samples" / "WT_Database_2.57.1.67.json"
        )
        cls.sample_graph = ResearchGraphBuilder.from_database(cls.sample_database)
        cls.sample_compatibility = LegacyRankCompatibilityStrategy(cls.sample_database)

    def test_cost_contract_is_deterministic_and_json_serializable(self):
        db = database(
            vehicle("a", rp=0, sl=0, reserve=True),
            vehicle("b", rp=46, sl=101),
            predecessors={"b": "a"},
        )
        graph = ResearchGraphBuilder.from_database(db)
        resolved = GraphPrerequisiteResolver(graph).resolve(
            target_vehicle_id="b",
            start_vehicle_id="a",
        )
        engine = GraphCostEngine(db)
        first = engine.calculate(resolved)
        second = engine.calculate(resolved)
        self.assertEqual(first, second)
        payload = first.to_dict()
        json.dumps(payload, sort_keys=True)
        for key in (
            "target_vehicle_id",
            "start_vehicle_id",
            "resolution_status",
            "cost_status",
            "vehicle_cost_lines",
            "total_remaining_rp",
            "total_ge_before_owned",
            "owned_ge",
            "total_ge_after_owned",
            "total_sl",
            "convertible_rp_available",
            "convertible_rp_shortfall",
            "sl_discount_percent",
            "rp_per_ge",
            "warnings",
            "evidence",
            "explanation_trace",
        ):
            self.assertIn(key, payload)
        self.assertEqual(first.cost_status, CostStatus.COMPLETE)
        self.assertEqual(first.vehicle_cost_lines[0].remaining_rp, 46)
        self.assertEqual(first.vehicle_cost_lines[0].ge, 2)

    def test_rp_and_ge_are_calculated_per_vehicle(self):
        db = database(
            vehicle("zero", rp=0, sl=10),
            vehicle("one", rp=1),
            vehicle("exact", rp=45),
            vehicle("over", rp=46),
        )
        result = GraphCostEngine(db).calculate(
            resolution("over", ("zero", "one", "exact", "over"))
        )
        lines = {item.vehicle_id: item for item in result.vehicle_cost_lines}
        self.assertEqual(lines["zero"].ge, 0)
        self.assertEqual(lines["one"].ge, 1)
        self.assertEqual(lines["exact"].ge, 1)
        self.assertEqual(lines["over"].ge, 2)
        self.assertEqual(result.total_ge_before_owned, 4)
        self.assertNotEqual(result.total_ge_before_owned, 3)
        self.assertTrue(lines["zero"].evidence["zeroRp"])
        self.assertTrue(any("zero RP" in item for item in result.warnings))

    def test_negative_and_excess_progress_are_rejected_not_clamped(self):
        db = database(vehicle("target", rp=45))
        resolved = resolution("target", ("target",))
        negative = GraphCostEngine(db).calculate(
            resolved,
            progress=PlayerProgress(
                vehicles={"target": VehicleProgress(researched_rp=-1)}
            ),
        )
        self.assertEqual(negative.cost_status, CostStatus.UNAVAILABLE)
        self.assertIn(
            "NEGATIVE_OR_INVALID_RESEARCHED_RP",
            negative.incomplete_reason_codes,
        )
        excess = GraphCostEngine(db).calculate(
            resolved,
            progress=PlayerProgress(
                vehicles={"target": VehicleProgress(researched_rp=46)}
            ),
        )
        self.assertIn("RESEARCHED_RP_EXCEEDS_TOTAL", excess.incomplete_reason_codes)

    def test_researched_and_purchased_states_remain_distinct(self):
        db = database(vehicle("target", rp=45, sl=101))
        resolved = resolution("target", ("target",))
        researched = GraphCostEngine(db).calculate(
            resolved,
            progress=PlayerProgress(
                vehicles={
                    "target": VehicleProgress(researched=True, purchased=False)
                }
            ),
            options=SolveOptions(sl_discount_percent=50),
        ).vehicle_cost_lines[0]
        self.assertTrue(researched.already_researched)
        self.assertFalse(researched.already_purchased)
        self.assertEqual(researched.remaining_rp, 0)
        self.assertEqual(researched.ge, 0)
        self.assertEqual(researched.discounted_sl, 50)

        purchased = GraphCostEngine(db).calculate(
            resolved,
            progress=PlayerProgress(
                vehicles={
                    "target": VehicleProgress(researched=False, purchased=True)
                }
            ),
        ).vehicle_cost_lines[0]
        self.assertTrue(purchased.already_researched)
        self.assertTrue(purchased.already_purchased)
        self.assertEqual(purchased.remaining_rp, 0)
        self.assertEqual(purchased.discounted_sl, 0)
        self.assertFalse(purchased.cost_applicable)

    def test_owned_ge_and_convertible_rp_are_applied_after_line_sums(self):
        db = database(vehicle("a", rp=46), vehicle("b", rp=45))
        resolved = resolution("b", ("a", "b"))
        result = GraphCostEngine(db).calculate(
            resolved,
            progress=PlayerProgress(owned_ge=2, convertible_rp=90),
        )
        self.assertEqual(result.total_ge_before_owned, 3)
        self.assertEqual(result.total_ge_after_owned, 1)
        self.assertEqual(result.convertible_rp_available, 90)
        self.assertEqual(result.convertible_rp_shortfall, 1)

        unlimited = GraphCostEngine(db).calculate(resolved)
        self.assertIsNone(unlimited.convertible_rp_available)
        self.assertEqual(unlimited.convertible_rp_shortfall, 0)

    def test_only_zero_thirty_and_fifty_percent_sl_discounts_are_valid(self):
        db = database(vehicle("target", sl=101))
        resolved = resolution("target", ("target",))
        expected = {0: 101, 30: 71, 50: 50}
        for discount, amount in expected.items():
            result = GraphCostEngine(db).calculate(
                resolved,
                options=SolveOptions(sl_discount_percent=discount),
            )
            self.assertEqual(result.vehicle_cost_lines[0].discounted_sl, amount)
        invalid = GraphCostEngine(db).calculate(
            resolved,
            options=SolveOptions(sl_discount_percent=10),
        )
        self.assertEqual(invalid.cost_status, CostStatus.UNAVAILABLE)
        self.assertIn("INVALID_SL_DISCOUNT", invalid.incomplete_reason_codes)

    def test_invalid_global_economy_and_progress_values_block_costs(self):
        bad_rate = database(vehicle("target"), rp_per_ge=0)
        result = GraphCostEngine(bad_rate).calculate(
            resolution("target", ("target",))
        )
        self.assertIn("INVALID_RP_PER_GE", result.incomplete_reason_codes)

        db = database(vehicle("target"))
        invalid_progress = GraphCostEngine(db).calculate(
            resolution("target", ("target",)),
            progress=PlayerProgress(owned_ge=-1, convertible_rp=-1),
        )
        self.assertEqual(
            set(invalid_progress.incomplete_reason_codes),
            {"INVALID_CONVERTIBLE_RP", "INVALID_OWNED_GE"},
        )

        invalid_vehicle = database(vehicle("target", rp="invalid", sl=-1))
        invalid_costs = GraphCostEngine(invalid_vehicle).calculate(
            resolution("target", ("target",))
        )
        self.assertEqual(invalid_costs.cost_status, CostStatus.UNAVAILABLE)
        self.assertEqual(
            set(invalid_costs.incomplete_reason_codes),
            {"INVALID_VEHICLE_RP", "INVALID_VEHICLE_SL"},
        )

    def test_start_vehicle_is_costed_only_when_resolution_requires_it(self):
        db = database(
            vehicle("a", rp=45),
            vehicle("b", rp=45),
            predecessors={"b": "a"},
        )
        graph = ResearchGraphBuilder.from_database(db)
        resolver = GraphPrerequisiteResolver(graph)
        excluded_resolution = resolver.resolve(
            target_vehicle_id="b",
            start_vehicle_id="a",
        )
        excluded = GraphCostEngine(db).calculate(excluded_resolution)
        self.assertEqual(
            tuple(item.vehicle_id for item in excluded.vehicle_cost_lines),
            ("b",),
        )

        included_resolution = resolver.resolve(
            target_vehicle_id="b",
            start_vehicle_id="a",
            options=SolveOptions(include_start_vehicle=True),
        )
        included = GraphCostEngine(db).calculate(
            included_resolution,
            options=SolveOptions(include_start_vehicle=True),
        )
        self.assertEqual(
            tuple(item.vehicle_id for item in included.vehicle_cost_lines),
            ("a", "b"),
        )
        self.assertEqual(included.vehicle_cost_lines[0].reason, "start_vehicle")

    def test_resolution_status_controls_complete_partial_and_unavailable_costs(self):
        db = database(vehicle("target", rp=46))
        engine = GraphCostEngine(db)
        partial = engine.calculate(
            resolution(
                "target",
                ("target",),
                status=ResolutionStatus.UNRESOLVED,
            )
        )
        self.assertEqual(partial.cost_status, CostStatus.PARTIAL)
        self.assertIsNone(partial.total_remaining_rp)
        self.assertEqual(partial.partial_remaining_rp, 46)
        self.assertEqual(partial.partial_ge_before_owned, 2)
        self.assertIn("RESOLUTION_UNRESOLVED", partial.incomplete_reason_codes)

        for status, reason_code in (
            (ResolutionStatus.BLOCKED, "RESOLUTION_BLOCKED"),
            (ResolutionStatus.UNSUPPORTED, "RESOLUTION_UNSUPPORTED"),
        ):
            unavailable = engine.calculate(resolution("target", status=status))
            self.assertEqual(unavailable.cost_status, CostStatus.UNAVAILABLE)
            self.assertFalse(unavailable.vehicle_cost_lines)
            self.assertIsNone(unavailable.total_ge_before_owned)
            self.assertIn(reason_code, unavailable.incomplete_reason_codes)

    def test_required_and_satisfied_vehicles_cannot_be_double_counted(self):
        db = database(vehicle("target"))
        result = GraphCostEngine(db).calculate(
            resolution("target", ("target",), satisfied=("target",))
        )
        self.assertEqual(result.cost_status, CostStatus.UNAVAILABLE)
        self.assertIn("REQUIRED_SATISFIED_OVERLAP", result.incomplete_reason_codes)

    def test_shadow_comparison_reports_deterministic_mismatch_diagnostics(self):
        db = database(
            vehicle("a", rp=0, sl=0, reserve=True),
            vehicle("b", rp=45, sl=100),
            predecessors={"b": "a"},
        )
        graph = ResearchGraphBuilder.from_database(db)
        case = CostShadowCase(
            "legacy_researched_flag_gap",
            "b",
            "a",
            PlayerProgress(
                vehicles={"b": VehicleProgress(researched=True, purchased=False)}
            ),
        )
        first = run_cost_shadow_comparison(db, graph, (case,))
        second = run_cost_shadow_comparison(db, graph, (case,))
        self.assertEqual(first, second)
        self.assertEqual(first.mismatch, 1)
        detail = first.details[0].to_dict()
        for key in (
            "target_vehicle_id",
            "start_vehicle_id",
            "progress_scenario",
            "resolution_status",
            "legacy_vehicle_cost_lines",
            "graph_vehicle_cost_lines",
            "vehicle_differences",
            "rp_difference",
            "ge_difference",
            "sl_difference",
            "different_rounding",
            "evidence",
            "explanation_trace",
        ):
            self.assertIn(key, detail)

    def test_shadow_equivalent_and_unsupported_categories_are_not_matches(self):
        db = database(
            vehicle("a", rp=45),
            vehicle("b", rp=45),
            predecessors={"b": "a"},
        )
        graph = ResearchGraphBuilder.from_database(db)

        class ReverseRepresentation:
            mode_name = "test_reverse_representation"

            def select(self, **_kwargs):
                raise AssertionError("No rank selection is expected in this fixture.")

            def sort_vehicle_ids(self, vehicle_ids):
                return tuple(sorted(set(vehicle_ids), reverse=True))

        equivalent = run_cost_shadow_comparison(
            db,
            graph,
            (CostShadowCase("representation_only", "b"),),
            rank_compatibility_strategy=ReverseRepresentation(),
        )
        self.assertEqual(equivalent.equivalent_match, 1)
        self.assertEqual(equivalent.mismatch, 0)

        unsupported = run_cost_shadow_comparison(
            db,
            graph,
            (CostShadowCase("unknown_target", "missing"),),
        )
        self.assertEqual(unsupported.unsupported, 1)
        self.assertEqual(unsupported.exact_match, 0)
        self.assertEqual(unsupported.mismatch, 0)

    def test_cost_scenario_matrix_has_eighteen_reproducible_cases(self):
        cases = build_cost_scenarios(self.sample_database)
        self.assertEqual(cases, build_cost_scenarios(self.sample_database))
        self.assertEqual(len(cases), 18)
        summary = run_cost_shadow_comparison(
            self.sample_database,
            self.sample_graph,
            cases,
            rank_compatibility_strategy=self.sample_compatibility,
        )
        self.assertEqual(summary.scenario_count, 18)
        self.assertEqual(summary.exact_match, 16)
        self.assertEqual(summary.unresolved_expected, 2)
        self.assertEqual(summary.unsupported, 0)
        self.assertEqual(summary.mismatch, 0)
        self.assertEqual(
            summary.cost_status_distribution,
            {"complete": 16, "partial": 2},
        )

    def test_special_cost_matrix_is_deterministic_and_keeps_49_cases(self):
        first = build_cost_special_case_matrix(
            self.sample_database,
            self.sample_graph,
            rank_compatibility_strategy=self.sample_compatibility,
        )
        second = build_cost_special_case_matrix(
            self.sample_database,
            self.sample_graph,
            rank_compatibility_strategy=self.sample_compatibility,
        )
        self.assertEqual(first, second)
        self.assertEqual(len(first.rows), 49)
        self.assertEqual(first.complete, 35)
        self.assertEqual(first.partial, 14)
        self.assertEqual(first.unavailable, 0)
        self.assertEqual(
            render_cost_special_case_markdown(first),
            render_cost_special_case_markdown(second),
        )
        committed = (
            ROOT / "docs" / "26_GRAPH_COST_SPECIAL_CASE_MATRIX.md"
        ).read_text(encoding="utf-8")
        self.assertEqual(committed, render_cost_special_case_markdown(first))


if __name__ == "__main__":
    unittest.main()
