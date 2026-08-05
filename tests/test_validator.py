from __future__ import annotations

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "validator"))

from wurstbrot_validator import legacy_validation_report, validate_database, write_health_reports


def vehicle(vehicle_id: str, **overrides):
    result = {
        "id": vehicle_id,
        "name": vehicle_id.replace("_", " ").title(),
        "countryId": "country_test",
        "branchId": "army",
        "rank": 1,
        "rp": 1_000,
        "sl": 2_000,
        "reserve": False,
        "hiddenResearch": False,
        "reqUnlock": "",
        "premium": False,
        "special": False,
        "group": None,
        "groupIndex": 0,
    }
    result.update(overrides)
    return result


def database(*vehicles):
    return {
        "schemaVersion": 1,
        "gameVersion": "2.57.1.67",
        "generatedAt": "2026-01-01T00:00:00+00:00",
        "economy": {"rpPerGE": 45},
        "vehicles": list(vehicles),
        "predecessors": {item["id"]: None for item in vehicles if "id" in item},
        "groups": {},
        "rankUnlock": {},
    }


class ValidatorTests(unittest.TestCase):
    def rules(self, value):
        return [finding.rule_id for finding in validate_database(value).findings]

    def assert_rule(self, value, rule_id):
        self.assertIn(rule_id, self.rules(value))

    def test_valid_minimal_database_passes(self):
        report = validate_database(database(vehicle("a", reserve=True, rp=0, sl=0)))
        self.assertTrue(report.passed)
        self.assertEqual(report.counts["error"], 0)

    def test_valid_graph_group_and_rank_unlock_are_clean_counterexamples(self):
        value = database(
            vehicle("a", group="g", groupIndex=0),
            vehicle("b", rank=2, group="g", groupIndex=1),
        )
        value["predecessors"]["b"] = "a"
        value["groups"] = {"g": ["a", "b"]}
        value["rankUnlock"] = {"country_test": {"army": {"1": 1}}}
        report = validate_database(value)
        structural = [
            item.rule_id
            for item in report.findings
            if item.rule_id.startswith(("GRAPH_", "GROUP_", "RANK_UNLOCK_"))
        ]
        self.assertEqual(structural, [])
        self.assertTrue(report.passed)

    def test_identity_and_schema_rules(self):
        base = database(vehicle("a"))
        cases = {
            "SCHEMA_INVALID_VERSION": {**base, "schemaVersion": 99},
            "GAME_VERSION_MISSING": {**base, "gameVersion": ""},
            "ECONOMY_INVALID_RP_PER_GE": {**base, "economy": {"rpPerGE": 0}},
            "VEHICLE_DUPLICATE_ID": database(vehicle("a"), vehicle("a")),
            "VEHICLE_MISSING_FIELD": database({"id": "a"}),
            "VEHICLE_INVALID_FIELD_TYPE": database(vehicle("a", countryId=7)),
        }
        for rule_id, value in cases.items():
            with self.subTest(rule_id=rule_id):
                self.assert_rule(value, rule_id)

    def test_cost_and_rank_rules(self):
        cases = {
            "COST_NEGATIVE_RP": vehicle("a", rp=-1),
            "COST_NEGATIVE_SL": vehicle("a", sl=-1),
            "COST_NON_NUMERIC": vehicle("a", rp="many"),
            "RANK_INVALID": vehicle("a", rank=0),
            "COST_ZERO_RP_WITH_SL": vehicle("a", rp=0, sl=1),
            "COST_ZERO_SL_WITH_RP": vehicle("a", rp=1, sl=0),
        }
        for rule_id, item in cases.items():
            with self.subTest(rule_id=rule_id):
                self.assert_rule(database(item), rule_id)

    def test_graph_rules(self):
        base = database(vehicle("a"), vehicle("b", rank=2))
        cases = {}
        missing = copy.deepcopy(base)
        missing["predecessors"]["b"] = "missing"
        cases["GRAPH_MISSING_PREDECESSOR"] = missing
        self_ref = copy.deepcopy(base)
        self_ref["predecessors"]["a"] = "a"
        cases["GRAPH_SELF_REFERENCE"] = self_ref
        cycle = copy.deepcopy(base)
        cycle["predecessors"] = {"a": "b", "b": "a"}
        cases["GRAPH_CYCLE"] = cycle
        nation = database(vehicle("a"), vehicle("b", countryId="country_other"))
        nation["predecessors"]["b"] = "a"
        cases["GRAPH_CROSS_NATION"] = nation
        branch = database(vehicle("a"), vehicle("b", branchId="aviation"))
        branch["predecessors"]["b"] = "a"
        cases["GRAPH_CROSS_BRANCH"] = branch
        backwards = database(vehicle("a", rank=2), vehicle("b", rank=1))
        backwards["predecessors"]["b"] = "a"
        cases["GRAPH_RANK_BACKWARDS"] = backwards
        unreachable = copy.deepcopy(base)
        del unreachable["predecessors"]["b"]
        cases["GRAPH_UNREACHABLE"] = unreachable
        conflicting = copy.deepcopy(base)
        conflicting["predecessors"]["b"] = ["a", "missing"]
        cases["GRAPH_CONFLICTING_PREDECESSORS"] = conflicting
        for rule_id, value in cases.items():
            with self.subTest(rule_id=rule_id):
                self.assert_rule(value, rule_id)

    def test_group_rules(self):
        base = database(
            vehicle("a", group="g", groupIndex=1),
            vehicle("b", group="g", groupIndex=0),
            vehicle("c", countryId="country_other"),
        )
        base["groups"] = {"g": ["a", "b", "missing"], "other": ["a", "c"]}
        rules = self.rules(base)
        for rule_id in (
            "GROUP_UNKNOWN_VEHICLE",
            "GROUP_CONFLICTING_MEMBERSHIP",
            "GROUP_INDEX_MISMATCH",
            "GROUP_CROSS_TREE",
        ):
            self.assertIn(rule_id, rules)
        single = database(vehicle("a", group="single"))
        single["groups"] = {"single": ["a"]}
        self.assert_rule(single, "GROUP_SINGLE_VEHICLE")

    def test_rank_unlock_rules(self):
        base = database(vehicle("a"), vehicle("b", rank=2))
        cases = {}
        negative = copy.deepcopy(base)
        negative["rankUnlock"] = {"country_test": {"army": {"1": -1}}}
        cases["RANK_UNLOCK_NEGATIVE"] = negative
        high = copy.deepcopy(base)
        high["rankUnlock"] = {"country_test": {"army": {"1": 21}}}
        cases["RANK_UNLOCK_UNREALISTIC"] = high
        unavailable = copy.deepcopy(base)
        unavailable["rankUnlock"] = {"country_test": {"army": {"1": 2}}}
        cases["RANK_UNLOCK_EXCEEDS_AVAILABLE"] = unavailable
        cases["RANK_UNLOCK_MISSING"] = base
        order = copy.deepcopy(base)
        order["rankUnlock"] = {"country_test": {"army": {"invalid": 1}}}
        cases["RANK_UNLOCK_ORDER_CONFLICT"] = order
        for rule_id, value in cases.items():
            with self.subTest(rule_id=rule_id):
                self.assert_rule(value, rule_id)

    def test_localization_and_special_case_rules(self):
        missing_name = vehicle("missing")
        del missing_name["name"]
        value = database(
            missing_name,
            vehicle("empty", name=""),
            vehicle("internal", name="internal"),
            vehicle("one", name="Duplicate"),
            vehicle("two", name="Duplicate"),
            vehicle("hidden", hiddenResearch=True),
            vehicle("unlock", reqUnlock="external_rule"),
            vehicle("reserve", reserve=True, rp=0, sl=0),
            vehicle("premium", premium=True),
            vehicle("special", special=True),
        )
        rules = self.rules(value)
        for rule_id in (
            "LOCALIZATION_MISSING_NAME",
            "LOCALIZATION_EMPTY",
            "LOCALIZATION_INTERNAL_ID",
            "LOCALIZATION_DUPLICATE_NAME",
            "SPECIAL_HIDDEN_RESEARCH",
            "SPECIAL_EXTERNAL_UNLOCK",
            "SPECIAL_RESERVE",
            "SPECIAL_PREMIUM",
            "SPECIAL_NON_REGULAR",
        ):
            self.assertIn(rule_id, rules)

    def test_multiple_findings_are_deterministic(self):
        value = database(vehicle("b", rp=-1, name=""), vehicle("a", sl=-1))
        first = [finding.to_dict() for finding in validate_database(value).findings]
        second = [finding.to_dict() for finding in validate_database(value).findings]
        self.assertEqual(first, second)
        order = {"error": 0, "warning": 1, "info": 2}
        keys = [
            (order[item["severity"]], item["rule_id"], item.get("entity_id", ""))
            for item in first
        ]
        self.assertEqual(keys, sorted(keys))

    def test_health_report_is_serializable_and_writable(self):
        report = validate_database(database(vehicle("a", reserve=True, rp=0, sl=0)))
        json.dumps(report.to_dict())
        with tempfile.TemporaryDirectory() as directory:
            json_path, text_path = write_health_reports(report, Path(directory))
            self.assertEqual(json.loads(json_path.read_text())["passed"], True)
            self.assertIn("Validation passed: yes", text_path.read_text())
            self.assertEqual(
                set(report.to_dict()),
                {
                    "schemaVersion",
                    "gameVersion",
                    "generatedAt",
                    "passed",
                    "counts",
                    "countsByRule",
                    "vehicleCount",
                    "countryCount",
                    "treeCount",
                    "groupCount",
                    "graphStatistics",
                    "findings",
                    "ignoredRules",
                },
            )

    def test_legacy_validation_export_remains_available(self):
        report = validate_database(database(vehicle("a", reserve=True, rp=0, sl=0)))
        legacy = legacy_validation_report(report)
        self.assertEqual(legacy["schemaVersion"], 1)
        self.assertIn("errors", legacy)
        self.assertIn("warnings", legacy)
        self.assertEqual(legacy["healthReport"], "WT_Health_2.57.1.67.json")

    def test_ignored_rule_is_recorded(self):
        report = validate_database(
            database(vehicle("a", rp=0, sl=1)),
            ignored_rules={"COST_ZERO_RP_WITH_SL"},
        )
        self.assertNotIn("COST_ZERO_RP_WITH_SL", [item.rule_id for item in report.findings])
        self.assertEqual(report.ignored_rules, ("COST_ZERO_RP_WITH_SL",))

    def test_sample_database_has_no_errors(self):
        sample = json.loads(
            (ROOT / "data" / "samples" / "WT_Database_2.57.1.67.json").read_text()
        )
        report = validate_database(sample)
        errors = [
            finding.to_dict()
            for finding in report.findings
            if finding.severity.value == "error"
        ]
        self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()
