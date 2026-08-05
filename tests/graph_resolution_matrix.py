from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "core"))

from wurstbrot_core import (  # noqa: E402
    LegacyRankCompatibilityStrategy,
    ResearchGraphBuilder,
    VehicleDatabase,
    build_full_shadow_cases,
    build_player_progress_scenarios,
    build_resolution_special_case_matrix,
    run_shadow_comparison,
)


def main() -> int:
    database = VehicleDatabase.from_json(
        ROOT / "data" / "samples" / "WT_Database_2.57.1.67.json"
    )
    graph = ResearchGraphBuilder.from_database(database)
    strategy = LegacyRankCompatibilityStrategy(database)
    full_cases = build_full_shadow_cases(database)
    progress_cases = build_player_progress_scenarios(database)
    shadow = run_shadow_comparison(
        database,
        graph,
        full_cases,
        rank_compatibility_strategy=strategy,
    )
    progress = run_shadow_comparison(
        database,
        graph,
        progress_cases,
        rank_compatibility_strategy=strategy,
    )
    special = build_resolution_special_case_matrix(
        database,
        graph,
        rank_compatibility_strategy=strategy,
    )
    result = {
        "schemaVersion": 1,
        "gameVersion": database.game_version,
        "resolverVersion": "1.0.0-shadow",
        "compatibilityMode": strategy.mode_name,
        "graphCostCalculationPerformed": False,
        "costValuesEmitted": False,
        "legacyCompatibilityModeEnabled": True,
        "optimizerSelectionPerformed": False,
        "shadowMatrix": shadow.to_dict(),
        "playerProgressMatrix": {
            "scenarios": [case.to_dict() for case in progress_cases],
            "comparison": progress.to_dict(),
        },
        "specialCaseComparison": special.to_dict(),
        "graphDiagnostics": graph.diagnostics().to_dict(),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if shadow.mismatch or progress.mismatch or special.mismatch:
        return 1
    if shadow.scenario_count != 1_990 or len(progress_cases) != 13:
        return 1
    if len(special.rows) != 49:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
