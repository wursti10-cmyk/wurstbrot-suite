import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "core"))

from wurstbrot_core import (  # noqa: E402
    PlayerProgress,
    ResearchSolver,
    SolveOptions,
    VehicleDatabase,
    VehicleProgress,
)


class SolverContractTests(unittest.TestCase):
    def test_shared_browser_contract_matches_python_core(self):
        fixture = json.loads(
            (ROOT / "tests" / "fixtures" / "solver_contract.json").read_text(encoding="utf-8")
        )
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", encoding="utf-8") as handle:
            json.dump(fixture["database"], handle)
            handle.flush()
            database = VehicleDatabase.from_json(handle.name)

        case = fixture["input"]
        result = ResearchSolver(database).solve(
            start_vehicle_id=case["startId"],
            target_vehicle_id=case["targetId"],
            progress=PlayerProgress(
                vehicles={
                    case["targetId"]: VehicleProgress(
                        researched_rp=case["targetResearchedRp"]
                    )
                },
                convertible_rp=case["convertibleRp"],
                owned_ge=case["ownedGe"],
            ),
            options=SolveOptions(
                optimize_for=case["optimizeFor"],
                sl_discount_percent=case["slDiscountPercent"],
            ),
        )
        expected = fixture["expected"]
        self.assertEqual(list(result.required_vehicle_ids), expected["requiredVehicleIds"])
        self.assertEqual([line.reason for line in result.vehicle_lines], expected["reasons"])
        self.assertEqual(result.total_rp, expected["totalRp"])
        self.assertEqual(result.total_ge_before_owned, expected["totalGeBeforeOwned"])
        self.assertEqual(result.total_ge_after_owned, expected["totalGeAfterOwned"])
        self.assertEqual(result.total_sl, expected["totalSl"])
        self.assertEqual(result.convertible_rp_shortfall, expected["convertibleRpShortfall"])
        self.assertEqual(result.rank_requirements[0].available_after, expected["rankAvailableAfter"])


if __name__ == "__main__":
    unittest.main()
