import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "core"))

from wurstbrot_core import (
    PlayerProgress,
    ResearchSolver,
    SolveOptions,
    VehicleDatabase,
    VehicleProgress,
)
from wurstbrot_core.solver import SolveError


class SolverTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db = VehicleDatabase.from_json(
            ROOT / "data" / "samples" / "WT_Database_2.57.1.67.json"
        )
        cls.solver = ResearchSolver(cls.db)

    def test_target_cost_is_included(self):
        result = self.solver.solve(
            target_vehicle_id="germ_leopard_2a7v",
            start_vehicle_id="germ_leopard_2a5",
        )
        ids = {line.vehicle_id for line in result.vehicle_lines}
        self.assertIn("germ_leopard_2a7v", ids)
        self.assertGreater(result.total_ge_before_owned, 0)

    def test_partial_rp_reduces_ge(self):
        baseline = self.solver.solve(
            target_vehicle_id="germ_leopard_2a7v",
            start_vehicle_id="germ_leopard_2a5",
        )
        progress = PlayerProgress(
            vehicles={
                "germ_leopard_2a7v": VehicleProgress(researched_rp=100_000)
            }
        )
        partial = self.solver.solve(
            target_vehicle_id="germ_leopard_2a7v",
            start_vehicle_id="germ_leopard_2a5",
            progress=progress,
        )
        self.assertLess(partial.total_ge_before_owned, baseline.total_ge_before_owned)

    def test_owned_vehicle_costs_nothing_and_implies_predecessors(self):
        progress = PlayerProgress(
            vehicles={
                "germ_leopard_2a5_pso": VehicleProgress(
                    researched_rp=self.db.get("germ_leopard_2a5_pso").rp,
                    researched=True,
                    purchased=True,
                )
            }
        )
        result = self.solver.solve(
            target_vehicle_id="germ_leopard_2a7v",
            progress=progress,
        )
        line_map = {line.vehicle_id: line for line in result.vehicle_lines}
        if "germ_leopard_2a5_pso" in line_map:
            self.assertTrue(line_map["germ_leopard_2a5_pso"].already_owned)

    def test_owned_ge_is_subtracted(self):
        result = self.solver.solve(
            target_vehicle_id="germ_leopard_2a7v",
            start_vehicle_id="germ_leopard_2a5",
            progress=PlayerProgress(owned_ge=1_000),
        )
        self.assertEqual(
            result.total_ge_after_owned,
            max(result.total_ge_before_owned - 1_000, 0),
        )

    def test_convertible_rp_shortfall(self):
        result = self.solver.solve(
            target_vehicle_id="germ_leopard_2a7v",
            start_vehicle_id="germ_leopard_2a5",
            progress=PlayerProgress(convertible_rp=0),
        )
        self.assertEqual(result.convertible_rp_shortfall, result.total_rp)

    def test_rank_requirements_are_satisfied(self):
        result = self.solver.solve(
            target_vehicle_id="germ_leopard_2a7v",
        )
        for item in result.rank_requirements:
            self.assertGreaterEqual(item.available_after, item.required)

    def test_start_vehicle_skips_obsolete_lower_rank_gates(self):
        result = self.solver.solve(
            target_vehicle_id="germ_leopard_2a7v",
            start_vehicle_id="germ_leopard_2a5",
        )
        start_rank = self.db.get("germ_leopard_2a5").rank
        self.assertTrue(
            all(item.rank >= start_rank for item in result.rank_requirements)
        )
        self.assertTrue(
            all(
                self.db.get(line.vehicle_id).rank >= start_rank
                for line in result.vehicle_lines
            )
        )

    def test_indirect_start_in_same_tree_is_supported(self):
        # A can be in another line; its prerequisite chain is owned, while the
        # target line's mandatory predecessors are still calculated.
        result = self.solver.solve(
            start_vehicle_id="germ_marder_1a1",
            target_vehicle_id="germ_leopard_2a7v",
        )
        self.assertIn("germ_leopard_2a7v", result.required_vehicle_ids)
        self.assertNotIn("germ_marder_1a1", result.required_vehicle_ids)

    def test_ge_total_equals_sum_of_vehicle_lines(self):
        result = self.solver.solve(
            start_vehicle_id="germ_leopard_2a5",
            target_vehicle_id="germ_leopard_2a7v",
        )
        self.assertEqual(
            result.total_ge_before_owned,
            sum(line.ge for line in result.vehicle_lines),
        )

    def test_hidden_target_is_rejected_by_default(self):
        hidden = next(v for v in self.db.vehicles.values() if v.hidden_research)
        with self.assertRaises(Exception):
            self.solver.solve(target_vehicle_id=hidden.id)

    def test_israel_rank_unlock_candidates_work_after_tree_access(self):
        result = self.solver.solve(
            start_vehicle_id="spitfire_lf_mk9e_iaf",
            target_vehicle_id="meteor_nfmk13",
        )
        self.assertIn("meteor_nfmk13", result.required_vehicle_ids)
        self.assertTrue(all(r.available_after >= r.required for r in result.rank_requirements))

    def test_v1_sl_discount_contract_accepts_only_zero_thirty_and_fifty(self):
        for discount in (0, 30, 50):
            with self.subTest(discount=discount):
                self.solver.solve(
                    target_vehicle_id="germ_leopard_2a7v",
                    start_vehicle_id="germ_leopard_2a5",
                    options=SolveOptions(sl_discount_percent=discount),
                )

        for discount in (10, 100):
            with self.subTest(discount=discount):
                with self.assertRaisesRegex(SolveError, "0, 30 oder 50"):
                    self.solver.solve(
                        target_vehicle_id="germ_leopard_2a7v",
                        start_vehicle_id="germ_leopard_2a5",
                        options=SolveOptions(sl_discount_percent=discount),
                    )

    def test_invalid_progress_is_rejected_instead_of_clamped(self):
        target = self.db.get("germ_leopard_2a7v")
        invalid_progress = (
            PlayerProgress(
                vehicles={target.id: VehicleProgress(researched_rp=-1)}
            ),
            PlayerProgress(
                vehicles={
                    target.id: VehicleProgress(researched_rp=target.rp + 1)
                }
            ),
            PlayerProgress(owned_ge=-1),
            PlayerProgress(convertible_rp=-1),
        )
        for progress in invalid_progress:
            with self.subTest(progress=progress):
                with self.assertRaises(SolveError):
                    self.solver.solve(
                        target_vehicle_id=target.id,
                        start_vehicle_id="germ_leopard_2a5",
                        progress=progress,
                    )

    def test_researched_flag_requires_complete_numeric_rp(self):
        target = self.db.get("germ_leopard_2a7v")
        with self.assertRaisesRegex(SolveError, "researched=True"):
            self.solver.solve(
                target_vehicle_id=target.id,
                start_vehicle_id="germ_leopard_2a5",
                progress=PlayerProgress(
                    vehicles={
                        target.id: VehicleProgress(
                            researched_rp=target.rp - 1,
                            researched=True,
                        )
                    }
                ),
            )

    def test_purchased_vehicle_requires_researched_state(self):
        target = self.db.get("germ_leopard_2a7v")
        with self.assertRaisesRegex(SolveError, "gekauftes Fahrzeug"):
            self.solver.solve(
                target_vehicle_id=target.id,
                start_vehicle_id="germ_leopard_2a5",
                progress=PlayerProgress(
                    vehicles={
                        target.id: VehicleProgress(
                            researched_rp=target.rp,
                            researched=False,
                            purchased=True,
                        )
                    }
                ),
            )


if __name__ == "__main__":
    unittest.main()
