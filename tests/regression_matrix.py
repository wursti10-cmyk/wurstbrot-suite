from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "core"))

from wurstbrot_core import ResearchSolver, SolveOptions, VehicleDatabase


def main() -> int:
    db = VehicleDatabase.from_json(ROOT / "data/samples/WT_Database_2.57.1.67.json")
    solver = ResearchSolver(db)
    stats = Counter()
    failures = []

    for target in db.vehicles.values():
        if target.hidden_research or target.req_unlock:
            stats["skipped_special"] += 1
            continue
        predecessor = db.predecessors.get(target.id)
        if not predecessor:
            stats["root_targets"] += 1
            continue
        try:
            result = solver.solve(
                start_vehicle_id=predecessor,
                target_vehicle_id=target.id,
                options=SolveOptions(optimize_for="ge"),
            )
            assert target.id in result.required_vehicle_ids
            assert result.total_ge_before_owned == sum(x.ge for x in result.vehicle_lines)
            assert all(r.available_after >= r.required for r in result.rank_requirements)
            stats["passed"] += 1
        except Exception as exc:
            failures.append({"target": target.id, "start": predecessor, "error": str(exc)})
            stats["failed"] += 1

    report = {
        "gameVersion": db.game_version,
        "vehicles": len(db.vehicles),
        "stats": dict(stats),
        "failures": failures[:100],
    }
    out = ROOT / "MILESTONE1_REGRESSION.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report["stats"], ensure_ascii=False))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
