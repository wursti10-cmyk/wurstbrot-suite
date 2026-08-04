import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "core"))

from wurstbrot_core import VehicleDatabase


class DatabaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db = VehicleDatabase.from_json(
            ROOT / "data" / "samples" / "WT_Database_2.57.1.67.json"
        )

    def test_database_loads(self):
        self.assertGreater(len(self.db.vehicles), 2_000)
        self.assertEqual(self.db.rp_per_ge, 45)

    def test_leopard_2a7v_exists(self):
        vehicle = self.db.get("germ_leopard_2a7v")
        self.assertEqual(vehicle.rp, 420_000)
        self.assertEqual(vehicle.sl, 1_120_000)

    def test_closure_ends_at_target(self):
        path = self.db.closure("germ_leopard_2a7v")
        self.assertEqual(path[-1], "germ_leopard_2a7v")
        self.assertGreater(len(path), 2)


if __name__ == "__main__":
    unittest.main()
