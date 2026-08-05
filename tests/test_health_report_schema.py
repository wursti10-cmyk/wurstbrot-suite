from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class HealthReportSchemaTests(unittest.TestCase):
    def test_v2_schema_matches_ci_required_fields(self):
        schema = json.loads(
            (ROOT / "specs" / "HEALTH_REPORT_SCHEMA.json").read_text(encoding="utf-8")
        )
        self.assertEqual(schema["properties"]["schemaVersion"]["const"], 2)
        self.assertEqual(schema["properties"]["healthScore"]["type"], "null")
        self.assertEqual(
            set(schema["required"]),
            {
                "schemaVersion",
                "gameVersion",
                "generatedAt",
                "passed",
                "validatorVersion",
                "validationDuration",
                "findingsByRule",
                "findingsBySeverity",
                "findingsByCategory",
                "vehicleStatistics",
                "graphStatistics",
                "folderStatistics",
                "findings",
                "implementedRules",
                "testedRules",
                "coverage",
                "healthScore",
                "healthScoreStatus",
                "ignoredRules",
                "counts",
                "countsByRule",
                "vehicleCount",
                "countryCount",
                "treeCount",
                "groupCount",
            },
        )


if __name__ == "__main__":
    unittest.main()
