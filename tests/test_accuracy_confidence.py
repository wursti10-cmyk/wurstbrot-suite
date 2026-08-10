from __future__ import annotations

import json
import sys
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "core"))
sys.path.insert(0, str(ROOT / "packages" / "validator"))

from wurstbrot_core.accuracy_confidence import (  # noqa: E402
    EXPECTED_PARTIAL_TARGET_IDS,
    PROVENANCE_CATEGORIES,
    REQUIRED_E2E_TAGS,
    AccuracyContractError,
    baseline_fingerprint,
    build_confidence_report,
    execute_golden_suite,
    load_json,
    render_confidence_text,
    run_metamorphic_suite,
    validate_baseline,
    validate_decision_register,
    validate_golden_fixture,
    validate_partial_dossier,
    validate_rollback_plan,
    write_confidence_reports,
)
from wurstbrot_core.database import VehicleDatabase  # noqa: E402
from wurstbrot_core.graph_pipeline import GraphCalculationPipeline  # noqa: E402
from wurstbrot_core.graph_resolution import LegacyRankCompatibilityStrategy  # noqa: E402
from wurstbrot_core.models import SolveOptions  # noqa: E402
from wurstbrot_validator.rules import RULE_DEFINITIONS, VALIDATOR_VERSION  # noqa: E402


class AccuracyConfidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.database = VehicleDatabase.from_json(
            ROOT / "data" / "samples" / "WT_Database_2.57.1.67.json"
        )
        cls.baseline = load_json(ROOT / "accuracy" / "baselines" / "2.57.1.67.json")
        cls.golden_fixture = load_json(ROOT / "accuracy" / "golden" / "2.57.1.67.json")
        cls.decisions = load_json(ROOT / "accuracy" / "contracts" / "decision_register.json")
        cls.partial_dossier = load_json(
            ROOT / "accuracy" / "research" / "partial_folder_cases_2.57.1.67.json"
        )
        cls.rollback = load_json(
            ROOT / "accuracy" / "rollback" / "experimental_switch_plan.json"
        )
        cls.golden_summary = execute_golden_suite(cls.database, cls.golden_fixture)
        cls.metamorphic_summary = run_metamorphic_suite(cls.database)

    def test_baseline_is_exact_versioned_and_environment_independent(self):
        validate_baseline(
            self.baseline,
            self.database,
            validator_version=VALIDATOR_VERSION,
            validator_rule_count=len(RULE_DEFINITIONS),
        )
        self.assertEqual(self.baseline["vehicleCount"], 2_232)
        self.assertEqual(self.baseline["researchTreeCount"], 44)
        self.assertEqual(self.baseline["ruleCount"], 42)
        self.assertEqual(self.baseline["fingerprint"], baseline_fingerprint(self.baseline))

    def test_baseline_fingerprint_changes_with_domain_content(self):
        changed = deepcopy(self.baseline)
        changed["vehicleCount"] += 1
        self.assertNotEqual(baseline_fingerprint(changed), self.baseline["fingerprint"])

    def test_golden_fixture_schema_tree_coverage_and_immutability(self):
        validate_golden_fixture(self.golden_fixture, self.database)
        self.assertEqual(len(self.golden_fixture["cases"]), 60)
        self.assertEqual(
            self.baseline["fingerprints"]["goldenFixture"],
            self.golden_fixture["fixtureFingerprint"],
        )
        self.assertEqual(
            self.baseline["fingerprints"]["goldenResults"],
            self.golden_fixture["resultFingerprint"],
        )
        tree_cases = [
            item for item in self.golden_fixture["cases"] if "tree_coverage" in item["tags"]
        ]
        self.assertEqual(len(tree_cases), 44)
        changed = deepcopy(self.golden_fixture)
        changed["cases"][0]["purpose"] += " changed"
        with self.assertRaises(AccuracyContractError):
            validate_golden_fixture(changed, self.database)

    def test_golden_suite_passes_without_legacy_execution(self):
        self.assertEqual(self.golden_summary.total, 60)
        self.assertEqual(self.golden_summary.passed, 60)
        self.assertEqual(self.golden_summary.failed, 0)
        self.assertEqual(
            self.golden_summary.fingerprint,
            self.golden_fixture["resultFingerprint"],
        )
        self.assertNotIn("legacy", self.golden_summary.fingerprint.lower())

    def test_every_provenance_category_is_executable_and_legacy_is_not_sole_proof(self):
        self.assertEqual(
            set(self.golden_summary.results_by_origin),
            set(PROVENANCE_CATEGORIES),
        )
        for origin in PROVENANCE_CATEGORIES:
            self.assertGreater(self.golden_summary.results_by_origin[origin]["total"], 0)
        legacy_cases = [
            item
            for item in self.golden_fixture["cases"]
            if item["primary_origin"] == "LEGACY_CONFIRMED"
        ]
        self.assertTrue(legacy_cases)
        for case in legacy_cases:
            self.assertTrue(
                {"DATAMINE_DIRECT", "FORMULA_DERIVED", "MANUALLY_REVIEWED"}
                & set(case["supporting_origins"])
            )

    def test_nine_real_end_to_end_references_are_reviewed(self):
        reviewed = {
            tag
            for case in self.golden_fixture["cases"]
            if case["review_status"] == "reviewed"
            for tag in case["tags"]
            if tag.startswith("e2e:")
        }
        self.assertEqual(set(REQUIRED_E2E_TAGS), reviewed)

    def test_all_sixteen_metamorphic_properties_pass_deterministically(self):
        repeated = run_metamorphic_suite(self.database)
        self.assertEqual(self.metamorphic_summary, repeated)
        self.assertEqual(self.metamorphic_summary.total, 16)
        self.assertEqual(self.metamorphic_summary.passed, 16)
        self.assertEqual(self.metamorphic_summary.failed, 0)
        self.assertTrue(all(item["seed"] is None for item in repeated.case_results))

    def test_contract_decision_register_is_complete_and_has_no_silent_decisions(self):
        validate_decision_register(self.decisions)
        self.assertEqual(len(self.decisions["decisions"]), 5)
        deferred = [item for item in self.decisions["decisions"] if item["status"] == "deferred"]
        self.assertTrue(deferred)
        self.assertTrue(all(item["release_blocking"] for item in deferred))

    def test_partial_dossier_matches_all_fourteen_datamine_targets(self):
        validate_partial_dossier(self.partial_dossier, self.database)
        self.assertEqual(
            [item["target_vehicle_id"] for item in self.partial_dossier["cases"]],
            list(EXPECTED_PARTIAL_TARGET_IDS),
        )
        self.assertTrue(
            all(not item["heuristic_applied"] for item in self.partial_dossier["cases"])
        )
        pipeline = GraphCalculationPipeline(
            self.database,
            rank_compatibility_strategy=LegacyRankCompatibilityStrategy(self.database),
        )
        statuses = {
            target: pipeline.run(
                target_vehicle_id=target,
                options=SolveOptions(
                    include_hidden_legacy=True,
                    assume_external_unlocks=True,
                ),
            ).pipeline_status.value
            for target in EXPECTED_PARTIAL_TARGET_IDS
        }
        self.assertEqual(set(statuses.values()), {"partial"})

    def test_rollback_plan_covers_opt_in_cli_without_default_switch(self):
        validate_rollback_plan(self.rollback)
        self.assertTrue(self.rollback["experimentalCliSwitchImplemented"])
        self.assertFalse(self.rollback["defaultProductiveSwitchImplemented"])
        self.assertEqual(self.rollback["defaultMode"], "legacy")
        self.assertFalse(self.rollback["featureFlag"]["persistent"])
        self.assertIn(
            "feature_flag_disabled",
            self.rollback["legacyFallback"]["conditions"],
        )
        self.assertNotIn(
            "invalid_input_if_legacy_accepts",
            self.rollback["legacyFallback"]["conditions"],
        )
        self.assertIn(
            "Reject invalid_input",
            self.rollback["legacyFallback"]["invalidInputPolicy"],
        )
        self.assertFalse(self.rollback["dataMigrationRequired"])
        self.assertFalse(self.rollback["telemetryEnabled"])

    def test_confidence_report_is_reproducible_without_numeric_score(self):
        first = self._confidence_report()
        second = self._confidence_report()
        self.assertEqual(first, second)
        self.assertNotIn("confidenceScore", first)
        self.assertTrue(first["readiness"]["ready_for_experimental_use"])
        self.assertTrue(first["readiness"]["ready_for_release_candidate"])
        self.assertFalse(first["readiness"]["ready_for_default_use"])
        self.assertEqual(
            first["readiness"]["experimental_use_scope"],
            "explicit_cli_graph_experimental_with_legacy_fallback",
        )
        self.assertEqual(first["browserParity"]["browserParityStatus"], "fixture_validation_only")
        with tempfile.TemporaryDirectory() as directory:
            json_path, text_path = write_confidence_reports(first, directory)
            self.assertEqual(json.loads(json_path.read_text(encoding="utf-8")), first)
            self.assertEqual(
                text_path.read_text(encoding="utf-8"),
                render_confidence_text(first),
            )

    def test_confidence_fingerprint_changes_with_factual_result(self):
        report = self._confidence_report()
        changed_shadow = self._shadow_report()
        changed_shadow["comparisonCounts"]["mismatch"] = 1
        changed = build_confidence_report(
            database=self.database,
            baseline=self.baseline,
            golden=self.golden_summary,
            metamorphic=self.metamorphic_summary,
            shadow_report=changed_shadow,
            browser_report=self._browser_report(),
            decision_register=self.decisions,
            partial_dossier=self.partial_dossier,
            rollback_plan=self.rollback,
        )
        self.assertNotEqual(report["fingerprint"], changed["fingerprint"])
        self.assertFalse(changed["readiness"]["ready_for_release_candidate"])

    def _confidence_report(self):
        return build_confidence_report(
            database=self.database,
            baseline=self.baseline,
            golden=self.golden_summary,
            metamorphic=self.metamorphic_summary,
            shadow_report=self._shadow_report(),
            browser_report=self._browser_report(),
            decision_register=self.decisions,
            partial_dossier=self.partial_dossier,
            rollback_plan=self.rollback,
        )

    def _shadow_report(self):
        return {
            "scenarioCount": 2_090,
            "comparisonCounts": {
                "exact_match": 1_988,
                "equivalent_match": 0,
                "unresolved_expected": 80,
                "unsupported": 2,
                "input_contract_difference": 20,
                "mismatch": 0,
                "internal_error": 0,
            },
            "optionsCoverage": {"coverage": 100.0},
            "inputValidationCoverage": {"coverage": 100.0},
            "specialCaseStatistics": {
                "caseCount": 49,
                "pipelineStatusDistribution": {"complete": 35, "partial": 14},
            },
            "fingerprint": self.baseline["fingerprints"]["accuracy6Shadow"],
        }

    def _browser_report(self):
        return {
            "schemaVersion": 1,
            "browserParityStatus": "fixture_validation_only",
            "graphRuntimeAvailable": False,
            "canonicalGoldenCasesValidated": 60,
            "passed": 60,
            "failed": 0,
            "resultFingerprint": self.golden_summary.fingerprint,
            "productiveBrowserLogicModified": False,
        }


if __name__ == "__main__":
    unittest.main()
