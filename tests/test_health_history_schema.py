from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class HealthHistorySchemaTests(unittest.TestCase):
    def test_future_history_schema_defines_required_comparison_fields(self):
        schema = json.loads(
            (ROOT / "specs" / "HEALTH_HISTORY_SCHEMA.json").read_text(encoding="utf-8")
        )
        self.assertEqual(schema["$schema"], "https://json-schema.org/draft/2020-12/schema")
        self.assertEqual(schema["properties"]["schemaVersion"]["const"], 1)
        entry = schema["$defs"]["historyEntry"]
        self.assertEqual(
            set(entry["required"]),
            {
                "previousVersion",
                "currentVersion",
                "createdAt",
                "validatorVersion",
                "gameVersion",
            },
        )
        self.assertFalse(entry["additionalProperties"])


if __name__ == "__main__":
    unittest.main()
