from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "core"))

from wurstbrot_core import (  # noqa: E402
    GraphCostEngine,
    LegacyRankCompatibilityStrategy,
    ResearchGraphBuilder,
    VehicleDatabase,
    build_cost_scenarios,
    build_cost_special_case_matrix,
    build_full_cost_shadow_cases,
    run_cost_shadow_comparison,
)


def main() -> int:
    database = VehicleDatabase.from_json(
        ROOT / "data" / "samples" / "WT_Database_2.57.1.67.json"
    )
    graph = ResearchGraphBuilder.from_database(database)
    compatibility = LegacyRankCompatibilityStrategy(database)
    full = run_cost_shadow_comparison(
        database,
        graph,
        build_full_cost_shadow_cases(database),
        rank_compatibility_strategy=compatibility,
    )
    scenarios = run_cost_shadow_comparison(
        database,
        graph,
        build_cost_scenarios(database),
        rank_compatibility_strategy=compatibility,
    )
    special = build_cost_special_case_matrix(
        database,
        graph,
        rank_compatibility_strategy=compatibility,
    )
    payload = {
        "schemaVersion": 1,
        "gameVersion": database.game_version,
        "costEngineVersion": GraphCostEngine.version,
        "shadowMode": True,
        "productiveLegacySolverModified": False,
        "guiModified": False,
        "browserModified": False,
        "optimizerSelectionPerformed": False,
        "completeTotalsRequireResolvedPrerequisites": True,
        "costShadowMatrix": full.to_dict(),
        "costScenarioMatrix": scenarios.to_dict(),
        "costScenarioIds": [item.scenario_id for item in build_cost_scenarios(database)],
        "specialCaseMatrix": special.to_dict(),
    }
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    if full.mismatch or scenarios.mismatch:
        return 1
    if len(special.rows) != 49:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
