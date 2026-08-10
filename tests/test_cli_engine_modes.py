from __future__ import annotations

import os
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "apps" / "ge-calculator" / "ge_calculator_cli.py"
DATABASE = ROOT / "data" / "samples" / "WT_Database_2.57.1.67.json"
BASE_ARGS = (
    "--database",
    str(DATABASE),
    "--start",
    "germ_sdkfz_222",
    "--target",
    "germ_sdkfz_6_2_flak36",
)


class CliEngineModeTests(unittest.TestCase):
    def run_cli(self, *extra: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            (sys.executable, str(CLI), *BASE_ARGS, *extra),
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )

    def test_default_without_engine_option_is_legacy(self):
        result = self.run_cli()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Rechenmodus: legacy", result.stdout)
        self.assertIn("Ergebnisquelle: legacy", result.stdout)
        self.assertIn("Shadow-Vergleich: nicht vorhanden", result.stdout)
        self.assertIn("Comparison Status: nicht ausgeführt", result.stdout)

    def test_version_is_available_without_database_arguments(self):
        result = subprocess.run(
            (sys.executable, str(CLI), "--version"),
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("1.0.0-rc.1", result.stdout)

    def test_non_utf8_console_does_not_crash_on_explanation_symbols(self):
        result = subprocess.run(
            (sys.executable, str(CLI), *BASE_ARGS),
            cwd=ROOT,
            check=False,
            capture_output=True,
            encoding="ascii",
            errors="strict",
            env={**os.environ, "PYTHONIOENCODING": "ascii"},
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Rechenmodus: legacy", result.stdout)

    def test_shadow_keeps_legacy_as_user_result_and_reports_comparison(self):
        result = self.run_cli("--engine", "shadow")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Rechenmodus: shadow", result.stdout)
        self.assertIn("Ergebnisquelle: legacy", result.stdout)
        self.assertIn("Shadow-Vergleich: vorhanden", result.stdout)
        self.assertIn("Comparison Status: exact_match", result.stdout)

    def test_graph_experimental_is_explicit_and_uses_graph_for_exact_case(self):
        result = self.run_cli("--engine", "graph-experimental")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("WARNUNG: Graph Experimental", result.stdout)
        self.assertIn("Rechenmodus: graph_experimental", result.stdout)
        self.assertIn("Ergebnisquelle: graph", result.stdout)
        self.assertIn("Fallback: nein", result.stdout)
        self.assertIn("Comparison Status: exact_match", result.stdout)
        self.assertIn("Graph-Status: complete", result.stdout)

    def test_existing_legacy_option_remains_hidden_vehicle_alias(self):
        result = self.run_cli("--legacy")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Rechenmodus: legacy", result.stdout)

    def test_unknown_engine_value_is_rejected(self):
        result = self.run_cli("--engine", "automatic")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("invalid choice", result.stderr)
        self.assertNotIn("Ergebnisquelle:", result.stdout)

    def test_partial_graph_status_is_visible_while_legacy_supplies_values(self):
        result = subprocess.run(
            (
                sys.executable,
                str(CLI),
                "--database",
                str(DATABASE),
                "--target",
                "fiat_cr42",
                "--legacy",
                "--engine",
                "graph-experimental",
            ),
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Ergebnisquelle: legacy", result.stdout)
        self.assertIn("Fallback: ja", result.stdout)
        self.assertIn("Fallback-Grund: graph_partial", result.stdout)
        self.assertIn("Graph-Status: partial", result.stdout)

    def test_invalid_graph_input_is_not_presented_as_valid_legacy_fallback(self):
        result = self.run_cli(
            "--engine",
            "graph-experimental",
            "--progress",
            "germ_sdkfz_6_2_flak36:-1",
        )

        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("Ergebnisquelle: keine", result.stdout)
        self.assertIn("Fallback: nein", result.stdout)
        self.assertIn("Fallback-Grund: graph_invalid_input", result.stdout)
        self.assertIn("Comparison Status: input_contract_difference", result.stdout)
        self.assertIn("Ergebnisstatus: unavailable", result.stdout)
        self.assertIn("Graph-Status: invalid_input", result.stdout)
        self.assertIn("Keine darstellbare Berechnung verfügbar.", result.stdout)

    def test_cli_rejects_sl_discounts_outside_the_v1_contract(self):
        result = self.run_cli("--sl-discount", "10")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("invalid choice", result.stderr)
        self.assertNotIn("Ergebnisquelle:", result.stdout)


if __name__ == "__main__":
    unittest.main()
