from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "core"))

from wurstbrot_core import (  # noqa: E402
    VehicleDatabase,
    render_experimental_switch_text,
    run_experimental_switch_matrix,
    validate_experimental_switch_report,
    write_experimental_switch_reports,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the Accuracy 8 experimental Graph execution matrix."
    )
    parser.add_argument("--output", type=Path, default=ROOT / "build" / "health")
    args = parser.parse_args()
    database = VehicleDatabase.from_json(
        ROOT / "data" / "samples" / "WT_Database_2.57.1.67.json"
    )
    golden = json.loads(
        (ROOT / "accuracy" / "golden" / "2.57.1.67.json").read_text(
            encoding="utf-8"
        )
    )
    report = run_experimental_switch_matrix(database, golden)
    validate_experimental_switch_report(report)
    write_experimental_switch_reports(report, args.output)
    print(render_experimental_switch_text(report), end="")
    full = report["fullMatrix"]
    if full["comparisonCounts"]["mismatch"]:
        return 1
    if full["comparisonCounts"]["internal_error"]:
        return 1
    if report["acceptanceMatrix"]["failed"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
