from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "core"))

from wurstbrot_core import (  # noqa: E402
    ResearchSolver,
    VehicleDatabase,
    build_visual_tree_highlight,
    build_visual_tree_layout,
)


DATABASE_PATH = ROOT / "data" / "samples" / "WT_Database_2.57.1.67.json"
DEFAULT_OUTPUT = ROOT / "apps" / "visual-tech-tree-prototype" / "germany-army.json"
COUNTRY_ID = "country_germany"
BRANCH_ID = "army"
START_ID = "germ_pzkpfw_VI_ausf_h1_tiger"
TARGET_ID = "germ_leopard_2a7v"


def build_payload() -> dict:
    database = VehicleDatabase.from_json(DATABASE_PATH)
    layout = build_visual_tree_layout(
        database,
        country_id=COUNTRY_ID,
        branch_id=BRANCH_ID,
    )
    result = ResearchSolver(database).solve(
        start_vehicle_id=START_ID,
        target_vehicle_id=TARGET_ID,
    )
    highlight = build_visual_tree_highlight(
        layout,
        result,
        user_result_source="legacy",
        calculation_status="complete",
    )
    return {
        "prototype": {
            "status": "isolated_foundation",
            "productiveBrowserReplacement": False,
            "countryLabel": "Deutschland",
            "branchLabel": "Panzer",
            "startLabel": database.get(START_ID).name,
            "targetLabel": database.get(TARGET_ID).name,
            "generatedBy": "scripts/build_visual_tree_prototype.py",
        },
        "layout": layout.to_dict(),
        "highlight": highlight.to_dict(),
        "solverSummary": {
            "requiredVehicleIds": list(result.required_vehicle_ids),
            "requiredVehicleReasons": {
                line.vehicle_id: line.reason for line in result.vehicle_lines
            },
            "totalRP": result.total_rp,
            "totalGE": result.total_ge_before_owned,
            "totalSL": result.total_sl,
        },
    }


def encoded_payload() -> str:
    return json.dumps(build_payload(), ensure_ascii=False, indent=2) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Erzeugt den isolierten Deutschland/Panzer-Layout-Prototyp."
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    expected = encoded_payload()

    if args.check:
        if not args.output.exists() or args.output.read_text(encoding="utf-8") != expected:
            print(f"Prototype payload is stale: {args.output}")
            return 1
        print(f"Prototype payload is reproducible: {args.output}")
        return 0

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(expected, encoding="utf-8")
    print(f"Prototype payload written: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
