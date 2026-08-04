import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "core"))

from wurstbrot_core.economy import apply_discount, ge_for_remaining_rp


class EconomyTests(unittest.TestCase):
    def test_zero_rp_costs_zero_ge(self):
        self.assertEqual(ge_for_remaining_rp(0, 45), 0)

    def test_rounds_each_vehicle_up(self):
        self.assertEqual(ge_for_remaining_rp(46, 45), 2)

    def test_individual_rounding_differs_from_total_rounding(self):
        self.assertEqual(
            ge_for_remaining_rp(1, 45) + ge_for_remaining_rp(1, 45),
            2,
        )

    def test_discount(self):
        self.assertEqual(apply_discount(1_000_000, 50), 500_000)


if __name__ == "__main__":
    unittest.main()
