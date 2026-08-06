from __future__ import annotations

import json
import sys
import tempfile
import unittest
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "core"))

from wurstbrot_core.database import VehicleDatabase  # noqa: E402
from wurstbrot_core.graph_pipeline import INPUT_VALIDATION_RULE_IDS  # noqa: E402
from wurstbrot_core.graph_shadow import (  # noqa: E402
    OPTION_COVERAGE_LABELS,
    build_full_pipeline_cases,
    build_input_validation_cases,
    build_options_compatibility_cases,
    render_shadow_text,
    run_full_pipeline_shadow,
    write_shadow_reports,
)


class GraphShadowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.database = VehicleDatabase.from_json(
            ROOT / "data" / "samples" / "WT_Database_2.57.1.67.json"
        )
        cls.coverage_cases = (
            build_options_compatibility_cases(cls.database)
            + build_input_validation_cases(cls.database)
        )
        cls.coverage_summary = run_full_pipeline_shadow(
            cls.database,
            cls.coverage_cases,
        )

    def test_full_case_builder_has_documented_non_overlapping_counting_levels(self):
        cases = build_full_pipeline_cases(self.database)
        self.assertEqual(len(cases), 2_090)
        self.assertEqual(len({item.case_id for item in cases}), 2_090)
        self.assertEqual(
            Counter(item.level for item in cases),
            {
                "regular_regression": 1_977,
                "cost_scenario": 18,
                "player_progress": 13,
                "options_compatibility": 15,
                "special_case": 49,
                "input_validation": 18,
            },
        )

    def test_options_and_input_coverage_are_derived_from_executable_cases(self):
        option_labels = {
            label
            for item in build_options_compatibility_cases(self.database)
            for label in item.coverage_labels
        }
        input_rules = {
            rule
            for item in build_input_validation_cases(self.database)
            for rule in item.expected_input_rule_ids
        }
        self.assertEqual(option_labels, set(OPTION_COVERAGE_LABELS))
        self.assertEqual(input_rules, set(INPUT_VALIDATION_RULE_IDS))
        self.assertEqual(self.coverage_summary.options_coverage["coverage"], 100.0)
        self.assertEqual(
            self.coverage_summary.input_validation_coverage["coverage"],
            100.0,
        )

    def test_shadow_report_is_deterministic_serializable_and_writable(self):
        repeated = run_full_pipeline_shadow(self.database, self.coverage_cases)
        self.assertEqual(self.coverage_summary, repeated)
        payload = self.coverage_summary.to_dict()
        json.dumps(payload, sort_keys=True)
        self.assertEqual(payload["scenarioCount"], 33)
        self.assertTrue(payload["fingerprint"].startswith("graph-shadow-report-v1:"))
        diagnostic = payload["nonExactDetails"][0]["diagnostics"]
        self.assertIn("playerProgressScenario", diagnostic)
        self.assertIn("vehicleSetDifferences", diagnostic)
        self.assertIn("vehicleCostLineDifferences", diagnostic)
        self.assertIn("totalDifferences", diagnostic)
        self.assertIn("fingerprints", diagnostic)
        with tempfile.TemporaryDirectory() as directory:
            json_path, text_path = write_shadow_reports(
                self.coverage_summary,
                directory,
            )
            self.assertEqual(json.loads(json_path.read_text(encoding="utf-8")), payload)
            self.assertEqual(
                text_path.read_text(encoding="utf-8"),
                render_shadow_text(self.coverage_summary),
            )

    def test_readiness_allows_shadow_experiments_but_not_default_use(self):
        readiness = self.coverage_summary.readiness
        self.assertTrue(readiness["ready_for_experimental_use"])
        self.assertFalse(readiness["ready_for_default_use"])
        self.assertIn("GRAPH_PIPELINE_NOT_IN_BROWSER", readiness["blockers"])
        self.assertIn(
            "INPUT_CONTRACT_DIFFERENCES_REQUIRE_DECISION",
            readiness["blockers"],
        )
        self.assertFalse(
            readiness["evidence"]["knownContractDifferencesDecided"]
        )
        self.assertFalse(readiness["evidence"]["browserGraphPipelineParity"])
        self.assertFalse(
            readiness["evidence"]["legacyRankCompatibilityRetired"]
        )


if __name__ == "__main__":
    unittest.main()
