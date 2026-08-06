from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "core"))

from wurstbrot_core.database import VehicleDatabase  # noqa: E402
from wurstbrot_core.graph_shadow import (  # noqa: E402
    render_shadow_text,
    run_full_pipeline_shadow,
    write_shadow_reports,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the Accuracy 6 dual-engine matrix.")
    parser.add_argument("--output", type=Path, default=ROOT / "build" / "health")
    args = parser.parse_args()
    database = VehicleDatabase.from_json(
        ROOT / "data" / "samples" / "WT_Database_2.57.1.67.json"
    )
    summary = run_full_pipeline_shadow(database)
    write_shadow_reports(summary, args.output)
    print(render_shadow_text(summary), end="")
    counts = summary.comparison_counts
    if counts.get("mismatch", 0) or counts.get("internal_error", 0):
        return 1
    if summary.scenario_count != 2_090:
        return 1
    if summary.options_coverage["coverage"] != 100.0:
        return 1
    if summary.input_validation_coverage["coverage"] != 100.0:
        return 1
    if summary.special_case_statistics["caseCount"] != 49:
        return 1
    if summary.readiness["ready_for_default_use"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
