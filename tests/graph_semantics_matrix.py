from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "core"))

from wurstbrot_core import (
    GraphRuleEvaluator,
    ResearchGraphBuilder,
    VehicleDatabase,
    build_special_case_matrix,
    run_mirror_evaluation,
)


def main() -> int:
    database = VehicleDatabase.from_json(ROOT / "data" / "samples" / "WT_Database_2.57.1.67.json")
    graph = ResearchGraphBuilder.from_database(database)
    mirror = run_mirror_evaluation(database, graph)
    special_cases = build_special_case_matrix(database, graph)
    status_counts: Counter[str] = Counter()
    evaluator = GraphRuleEvaluator(graph)
    for vehicle_id in sorted(database.vehicles):
        report = evaluator.evaluate(target_vehicle_id=vehicle_id)
        status_counts.update(evaluation.status.value for evaluation in report.evaluations)

    result = {
        "gameVersion": database.game_version,
        "mirror": {
            "exact_match": mirror.exact_match,
            "unresolved_expected": mirror.unresolved_expected,
            "mismatch": mirror.mismatch,
            "unsupported": mirror.unsupported,
        },
        "evaluationStatusDistribution": dict(sorted(status_counts.items())),
        "specialCaseCount": len(special_cases),
        "specialCaseStatusDistribution": dict(
            sorted(Counter(item["evaluationStatus"] for item in special_cases).items())
        ),
        "graphDiagnostics": graph.diagnostics().to_dict(),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if mirror.mismatch:
        return 1
    if len(special_cases) != 49:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
