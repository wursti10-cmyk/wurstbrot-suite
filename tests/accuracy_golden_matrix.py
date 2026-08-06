from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "core"))

from wurstbrot_core.accuracy_confidence import execute_golden_suite, load_json  # noqa: E402
from wurstbrot_core.database import VehicleDatabase  # noqa: E402


def main() -> int:
    database = VehicleDatabase.from_json(
        ROOT / "data" / "samples" / "WT_Database_2.57.1.67.json"
    )
    fixture = load_json(ROOT / "accuracy" / "golden" / "2.57.1.67.json")
    result = execute_golden_suite(database, fixture)
    print(
        json.dumps(
            {
                "golden_cases": result.total,
                "passed": result.passed,
                "failed": result.failed,
                "by_origin": result.results_by_origin,
                "fingerprint": result.fingerprint,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0 if result.failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
