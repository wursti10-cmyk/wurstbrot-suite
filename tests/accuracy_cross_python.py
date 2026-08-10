from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "core"))

from wurstbrot_core.accuracy_confidence import (  # noqa: E402
    execute_core_reference_suite,
    execute_golden_suite,
    load_json,
)
from wurstbrot_core.database import VehicleDatabase  # noqa: E402


def main() -> int:
    database = VehicleDatabase.from_json(
        ROOT / "data" / "samples" / "WT_Database_2.57.1.67.json"
    )
    fixture = load_json(ROOT / "accuracy" / "golden" / "2.57.1.67.json")
    result = execute_golden_suite(database, fixture)
    core_fixture = load_json(
        ROOT / "accuracy" / "golden" / "core_contract_2.57.1.67.json"
    )
    core_result = execute_core_reference_suite(database, core_fixture)
    expected = fixture["resultFingerprint"]
    print(
        json.dumps(
            {
                "canonical_result_fingerprint": result.fingerprint,
                "canonical_fixture_fingerprint": fixture["fixtureFingerprint"],
                "expected_fingerprint": expected,
                "identical": result.fingerprint == expected,
                "core_reference_result_fingerprint": core_result.fingerprint,
                "core_reference_fixture_fingerprint": core_fixture["fixtureFingerprint"],
                "core_reference_expected_fingerprint": core_fixture["resultFingerprint"],
                "core_reference_identical": (
                    core_result.fingerprint == core_fixture["resultFingerprint"]
                ),
            },
            sort_keys=True,
        )
    )
    return (
        0
        if result.failed == 0
        and result.fingerprint == expected
        and core_result.failed == 0
        and core_result.fingerprint == core_fixture["resultFingerprint"]
        else 1
    )


if __name__ == "__main__":
    raise SystemExit(main())
