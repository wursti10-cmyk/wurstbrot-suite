from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "validator"))

from validator_rule_matrix import rule_cases
from wurstbrot_validator import (
    RULE_DEFINITIONS,
    discover_tested_rules,
    render_rule_documentation,
    validate_database,
)


class ValidatorRuleCoverageTests(unittest.TestCase):
    def test_every_implemented_rule_has_positive_and_negative_contract(self):
        cases = rule_cases()
        self.assertEqual(set(cases), set(RULE_DEFINITIONS))
        for rule_id, (negative, positive) in sorted(cases.items()):
            with self.subTest(rule_id=rule_id, polarity="negative"):
                negative_rules = {item.rule_id for item in validate_database(negative).findings}
                self.assertIn(rule_id, negative_rules)
            with self.subTest(rule_id=rule_id, polarity="positive"):
                positive_rules = {item.rule_id for item in validate_database(positive).findings}
                self.assertNotIn(rule_id, positive_rules)

    def test_coverage_is_discovered_from_executable_matrix(self):
        matrix_path = ROOT / "tests" / "validator_rule_matrix.py"
        tested = discover_tested_rules([matrix_path])
        self.assertEqual(set(tested), set(RULE_DEFINITIONS))
        report = validate_database(rule_cases()["SCHEMA_INVALID_VERSION"][1], tested_rules=tested)
        self.assertEqual(report.coverage, 100.0)
        self.assertEqual(report.implemented_rules, report.tested_rules)

    def test_committed_rule_reference_matches_registry(self):
        expected = render_rule_documentation()
        actual = (ROOT / "docs" / "19_VALIDATOR_RULES.md").read_text(encoding="utf-8")
        self.assertEqual(actual, expected)


if __name__ == "__main__":
    unittest.main()
