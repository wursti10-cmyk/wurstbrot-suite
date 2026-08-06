from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "core"))

from wurstbrot_core import (  # noqa: E402
    VehicleDatabase,
    build_full_pipeline_cases,
    render_experimental_switch_text,
    run_experimental_switch_matrix,
)


class ExperimentalSwitchAnalysisTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.database = VehicleDatabase.from_json(
            ROOT / "data" / "samples" / "WT_Database_2.57.1.67.json"
        )
        cls.golden = json.loads(
            (ROOT / "accuracy" / "golden" / "2.57.1.67.json").read_text(
                encoding="utf-8"
            )
        )
        cls.case = build_full_pipeline_cases(cls.database)[0]
        cls.report = run_experimental_switch_matrix(
            cls.database,
            cls.golden,
            cases=(cls.case,),
        )

    def test_report_contract_contains_real_and_special_acceptance(self):
        report = self.report
        self.assertEqual(report["defaultMode"], "legacy")
        self.assertEqual(report["recommendedMode"], "legacy")
        self.assertFalse(report["featureFlag"]["defaultEnabled"])
        self.assertFalse(report["featureFlag"]["persistent"])
        self.assertEqual(report["fullMatrix"]["scenarioCount"], 1)
        self.assertEqual(report["acceptanceMatrix"]["passed"], 9)
        self.assertEqual(report["acceptanceMatrix"]["failed"], 0)
        self.assertEqual(report["specialCaseMatrix"]["caseCount"], 49)
        self.assertEqual(report["specialCaseMatrix"]["graphResultFullyUsed"], 35)
        self.assertEqual(report["specialCaseMatrix"]["legacyFallbackUsed"], 14)
        self.assertEqual(report["specialCaseMatrix"]["partialGraphCases"], 14)
        self.assertEqual(report["runtimeScope"]["desktopResultSource"], "legacy")
        self.assertEqual(report["runtimeScope"]["browserResultSource"], "legacy")
        json.dumps(report, sort_keys=True)

    def test_report_is_deterministic_and_text_is_explicit(self):
        repeated = run_experimental_switch_matrix(
            self.database,
            self.golden,
            cases=(self.case,),
        )
        self.assertEqual(self.report, repeated)
        self.assertTrue(
            self.report["fingerprint"].startswith("graph-experimental-report-v1:")
        )
        rendered = render_experimental_switch_text(self.report)
        self.assertIn("Default mode: legacy", rendered)
        self.assertIn("Real A-to-B acceptance: 9/9", rendered)


if __name__ == "__main__":
    unittest.main()
