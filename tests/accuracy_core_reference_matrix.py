from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "core"))

from wurstbrot_core.accuracy_confidence import (  # noqa: E402
    execute_core_reference_suite,
    load_json,
)
from wurstbrot_core.database import VehicleDatabase  # noqa: E402


def main() -> int:
    database = VehicleDatabase.from_json(
        ROOT / "data" / "samples" / "WT_Database_2.57.1.67.json"
    )
    fixture = load_json(
        ROOT / "accuracy" / "golden" / "core_contract_2.57.1.67.json"
    )
    result = execute_core_reference_suite(database, fixture)
    print(
        json.dumps(
            {
                "schemaVersion": 1,
                "gameVersion": database.game_version,
                "suite": "accuracy9-core-reference",
                "cases": result.total,
                "passed": result.passed,
                "failed": result.failed,
                "resultsByOrigin": result.results_by_origin,
                "fingerprintVersion": result.fingerprint_version,
                "fingerprint": result.fingerprint,
                "legacyUsedAsExpectedTruth": False,
                "fixtureAutomaticallyOverwritten": False,
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    return 1 if result.failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
