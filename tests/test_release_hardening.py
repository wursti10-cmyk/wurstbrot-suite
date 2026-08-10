from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from wurstbrot_core.database import VehicleDatabase
from wurstbrot_core.release_hardening import (
    DIRECT_RESULT_FINGERPRINT_VERSION,
    EXPECTED_EXECUTION_MODES,
    REQUIRED_COVERAGE,
    build_release_hardening_report,
    direct_fixture_fingerprint,
    load_release_fixture,
    release_report_fingerprint,
    write_release_hardening_report,
)


ROOT = Path(__file__).resolve().parents[1]


class ReleaseHardeningTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.database = VehicleDatabase.from_json(
            ROOT / "data" / "samples" / "WT_Database_2.57.1.67.json"
        )
        cls.fixture = load_release_fixture(
            ROOT / "accuracy" / "acceptance" / "release_hardening_2.57.1.67.json"
        )
        cls.golden = json.loads(
            (ROOT / "accuracy" / "golden" / "2.57.1.67.json").read_text(encoding="utf-8")
        )
        cls.core = json.loads(
            (
                ROOT / "accuracy" / "golden" / "core_contract_2.57.1.67.json"
            ).read_text(encoding="utf-8")
        )
        cls.dossier = json.loads(
            (
                ROOT
                / "accuracy"
                / "research"
                / "partial_folder_cases_2.57.1.67.json"
            ).read_text(encoding="utf-8")
        )
        cls.report = build_release_hardening_report(
            cls.database,
            cls.fixture,
            cls.golden,
            cls.core,
            cls.dossier,
            gate_evidence={
                "mismatches": 0,
                "internalErrors": 0,
                "contractDecisionsOpen": 0,
                "crossPythonPassed": True,
                "browserLegacyPassed": True,
                "pythonRegressionPassed": True,
                "pythonRegressionCases": 1_977,
                "graphMirrorPassed": True,
                "graphMirrorCases": 1_977,
                "browserRegressionPassed": True,
                "browserRegressionCases": 1_977,
                "healthErrors": 0,
                "validatorCoverage": 100.0,
                "validatorImplementedRules": 42,
                "validatorTestedRules": 42,
            },
        )

    def test_fixture_is_manual_immutable_and_covers_all_44_trees(self) -> None:
        self.assertEqual(self.fixture["generationPolicy"], "manual_review_only")
        self.assertTrue(self.fixture["immutable"])
        self.assertFalse(self.fixture["automaticOverwriteSupported"])
        self.assertEqual(self.fixture["caseCount"], 44)
        self.assertEqual(
            self.fixture["fixtureFingerprint"],
            direct_fixture_fingerprint(self.fixture),
        )
        trees = {
            (item["countryId"], item["vehicleType"])
            for item in self.fixture["cases"]
        }
        self.assertEqual(len(trees), 44)

    def test_direct_matrix_passes_all_three_modes_without_fallback(self) -> None:
        direct = self.report["directAcceptance"]
        self.assertEqual(direct["total"], 44)
        self.assertEqual(direct["passed"], 44)
        self.assertEqual(direct["failed"], 0)
        self.assertTrue(
            direct["fingerprint"].startswith(f"{DIRECT_RESULT_FINGERPRINT_VERSION}:")
        )
        self.assertEqual(set(direct["modeCounts"]), set(EXPECTED_EXECUTION_MODES))
        for mode, counts in direct["modeCounts"].items():
            with self.subTest(mode=mode):
                self.assertEqual(counts, {"passed": 44, "failed": 0})
        for case in direct["caseResults"]:
            self.assertEqual(case["modes"]["legacy"]["resultSource"], "legacy")
            self.assertEqual(case["modes"]["shadow"]["resultSource"], "legacy")
            self.assertEqual(
                case["modes"]["graph_experimental"]["resultSource"], "graph"
            )
            self.assertFalse(case["modes"]["graph_experimental"]["fallbackUsed"])

    def test_real_acceptance_exceeds_fifty_without_solver_generated_truth(self) -> None:
        acceptance = self.report["realAcceptance"]
        self.assertEqual(acceptance["total"], 61)
        self.assertEqual(acceptance["passed"], 61)
        self.assertEqual(acceptance["failed"], 0)
        self.assertEqual(acceptance["uniqueAtoBPairs"], 61)
        self.assertFalse(acceptance["legacyUsedAsExpectedTruth"])
        self.assertEqual(
            self.fixture["expectedValueSources"],
            ["DATAMINE_DIRECT", "FORMULA_DERIVED", "MANUALLY_REVIEWED"],
        )
        direct_lines = [
            line
            for case in self.report["directAcceptance"]["caseResults"]
            for line in case["expected"]["vehicleLines"]
        ]
        self.assertTrue(any(line["totalRp"] == 0 for line in direct_lines))
        self.assertTrue(any(line["sl"] == 0 for line in direct_lines))

    def test_required_release_coverage_has_case_evidence(self) -> None:
        coverage = self.report["coverage"]
        self.assertEqual(set(coverage), set(REQUIRED_COVERAGE))
        for category, item in coverage.items():
            with self.subTest(category=category):
                self.assertTrue(item["covered"])
                self.assertTrue(item["caseIds"])

    def test_boundary_matrix_is_deterministic_and_never_falls_back_invalid_input(self) -> None:
        boundary = self.report["boundaryMatrix"]
        self.assertEqual(boundary["total"], 32)
        self.assertEqual(boundary["passed"], 32)
        self.assertEqual(boundary["failed"], 0)
        self.assertFalse(boundary["randomized"])
        for item in boundary["invalidCases"]:
            with self.subTest(case=item["caseId"]):
                self.assertEqual(item["calculationStatus"], "unavailable")
                self.assertFalse(item["fallbackUsed"])
                self.assertIsNone(item["resultSource"])
        differences = [
            item
            for item in boundary["invalidCases"]
            if item["documentedContractDifference"]
        ]
        self.assertEqual([item["caseId"] for item in differences], ["invalid:empty-start"])

    def test_all_fourteen_hidden_folder_cases_remain_partial(self) -> None:
        partial = self.report["partialCases"]
        self.assertEqual(partial["total"], 14)
        self.assertEqual(partial["passed"], 14)
        self.assertEqual(partial["failed"], 0)
        self.assertFalse(partial["heuristicsIntroduced"])
        self.assertTrue(all(item["pipelineStatus"] == "partial" for item in partial["cases"]))
        self.assertTrue(all(item["fallbackUsed"] for item in partial["cases"]))

    def test_performance_is_a_smoke_gate_not_a_benchmark(self) -> None:
        performance = self.report["directAcceptance"]["performanceSmoke"]
        self.assertTrue(performance["passed"])
        self.assertFalse(performance["benchmark"])
        self.assertEqual(performance["caseExecutions"], 132)
        self.assertIn("observedSeconds", performance["fingerprintExcludedFields"])

    def test_rc_readiness_is_machine_readable_but_default_stays_false(self) -> None:
        readiness = self.report["readiness"]
        self.assertTrue(readiness["ready_for_rc_review"])
        self.assertTrue(readiness["ready_for_release_candidate"])
        self.assertFalse(readiness["ready_for_default_use"])
        self.assertEqual(readiness["mismatches"], 0)
        self.assertEqual(readiness["internal_errors"], 0)
        self.assertEqual(readiness["contract_decisions_open"], 0)
        self.assertEqual(readiness["partial_cases"], 14)
        self.assertTrue(readiness["python_regression_passed"])
        self.assertEqual(readiness["python_regression_cases"], 1_977)
        self.assertTrue(readiness["graph_mirror_passed"])
        self.assertEqual(readiness["graph_mirror_cases"], 1_977)
        self.assertTrue(readiness["browser_regression_passed"])
        self.assertEqual(readiness["browser_regression_cases"], 1_977)
        self.assertEqual(readiness["validator_coverage"], 100.0)
        self.assertEqual(readiness["validator_implemented_rules"], 42)
        self.assertEqual(readiness["validator_tested_rules"], 42)
        self.assertEqual(readiness["blockers"], [])

    def test_rc_readiness_requires_regression_and_validator_evidence(self) -> None:
        report = build_release_hardening_report(
            self.database,
            self.fixture,
            self.golden,
            self.core,
            self.dossier,
            gate_evidence={
                "mismatches": 0,
                "internalErrors": 0,
                "contractDecisionsOpen": 0,
                "crossPythonPassed": True,
                "browserLegacyPassed": True,
                "healthErrors": 0,
            },
        )
        self.assertFalse(report["readiness"]["ready_for_release_candidate"])
        self.assertEqual(
            report["readiness"]["blockers"],
            [
                "python_regression_failed",
                "graph_mirror_failed",
                "browser_regression_failed",
                "validator_coverage_incomplete",
            ],
        )

    def test_report_fingerprint_excludes_observed_timing_and_files_are_serializable(self) -> None:
        original = self.report["reportFingerprint"]
        changed = json.loads(json.dumps(self.report))
        changed["directAcceptance"]["performanceSmoke"]["observedSeconds"] += 1
        self.assertEqual(release_report_fingerprint(changed), original)
        with tempfile.TemporaryDirectory() as directory:
            json_path, text_path = write_release_hardening_report(self.report, directory)
            persisted = json.loads(json_path.read_text(encoding="utf-8"))
            self.assertEqual(persisted["reportFingerprint"], original)
            self.assertIn("Ready for default use: no", text_path.read_text(encoding="utf-8"))

    def test_browser_gui_and_desktop_sources_have_no_graph_activation(self) -> None:
        for relative in (
            "apps/web/app.js",
            "apps/web/solver.mjs",
            "apps/ge-calculator/ge_calculator_gui.py",
        ):
            with self.subTest(path=relative):
                source = (ROOT / relative).read_text(encoding="utf-8")
                self.assertNotIn("graph_experimental", source)
                self.assertNotIn("GraphCalculationPipeline", source)
        gui = (ROOT / "apps" / "ge-calculator" / "ge_calculator_gui.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("ResearchSolver", gui)


if __name__ == "__main__":
    unittest.main()
