from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "core"))
sys.path.insert(0, str(ROOT / "packages" / "validator"))

from wurstbrot_core.accuracy_confidence import (  # noqa: E402
    build_confidence_report,
    execute_golden_suite,
    load_json,
    render_confidence_text,
    run_metamorphic_suite,
    validate_baseline,
    validate_decision_register,
    validate_partial_dossier,
    validate_rollback_plan,
    write_confidence_reports,
)
from wurstbrot_core.database import VehicleDatabase  # noqa: E402
from wurstbrot_validator.rules import RULE_DEFINITIONS, VALIDATOR_VERSION  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the Accuracy 7 confidence report.")
    parser.add_argument("--shadow-report", type=Path, required=True)
    parser.add_argument("--browser-report", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=ROOT / "build" / "health")
    args = parser.parse_args()

    database = VehicleDatabase.from_json(
        ROOT / "data" / "samples" / "WT_Database_2.57.1.67.json"
    )
    baseline = load_json(ROOT / "accuracy" / "baselines" / "2.57.1.67.json")
    golden_fixture = load_json(ROOT / "accuracy" / "golden" / "2.57.1.67.json")
    decisions = load_json(ROOT / "accuracy" / "contracts" / "decision_register.json")
    dossier = load_json(
        ROOT / "accuracy" / "research" / "partial_folder_cases_2.57.1.67.json"
    )
    rollback = load_json(ROOT / "accuracy" / "rollback" / "experimental_switch_plan.json")
    validate_baseline(
        baseline,
        database,
        validator_version=VALIDATOR_VERSION,
        validator_rule_count=len(RULE_DEFINITIONS),
    )
    validate_decision_register(decisions)
    validate_partial_dossier(dossier, database)
    validate_rollback_plan(rollback)
    golden = execute_golden_suite(database, golden_fixture)
    metamorphic = run_metamorphic_suite(database)
    report = build_confidence_report(
        database=database,
        baseline=baseline,
        golden=golden,
        metamorphic=metamorphic,
        shadow_report=load_json(args.shadow_report),
        browser_report=load_json(args.browser_report),
        decision_register=decisions,
        partial_dossier=dossier,
        rollback_plan=rollback,
    )
    write_confidence_reports(report, args.output)
    print(render_confidence_text(report), end="")
    comparisons = report["pipelineComparisons"]["comparisonCounts"]
    if golden.failed or metamorphic.failed:
        return 1
    if comparisons["mismatch"] or comparisons["internal_error"]:
        return 1
    if not report["readiness"]["ready_for_release_candidate"]:
        return 1
    if report["readiness"]["ready_for_default_use"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
