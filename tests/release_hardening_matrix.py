from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "core"))

from wurstbrot_core.database import VehicleDatabase
from wurstbrot_core.release_hardening import (  # noqa: E402
    build_release_hardening_report,
    load_release_fixture,
    write_release_hardening_report,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the Accuracy 10 release-hardening gate.")
    parser.add_argument("--shadow-report", type=Path)
    parser.add_argument("--experimental-report", type=Path)
    parser.add_argument("--confidence-report", type=Path)
    parser.add_argument("--health-report", type=Path)
    parser.add_argument("--browser-report", type=Path)
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def load_json(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object.")
    return payload


def main() -> int:
    args = parse_args()
    database = VehicleDatabase.from_json(
        ROOT / "data" / "samples" / "WT_Database_2.57.1.67.json"
    )
    direct = load_release_fixture(
        ROOT / "accuracy" / "acceptance" / "release_hardening_2.57.1.67.json"
    )
    golden = load_json(ROOT / "accuracy" / "golden" / "2.57.1.67.json")
    core = load_json(
        ROOT / "accuracy" / "golden" / "core_contract_2.57.1.67.json"
    )
    dossier = load_json(
        ROOT / "accuracy" / "research" / "partial_folder_cases_2.57.1.67.json"
    )
    decisions = load_json(ROOT / "accuracy" / "contracts" / "decision_register.json")

    evidence = {
        "mismatches": 0,
        "internalErrors": 0,
        "contractDecisionsOpen": sum(
            item.get("status") != "accepted" for item in decisions["decisions"]
        ),
        "crossPythonPassed": False,
        "browserLegacyPassed": False,
        "healthErrors": 0,
    }
    if args.shadow_report:
        shadow = load_json(args.shadow_report)
        counts = shadow["comparisonCounts"]
        evidence["mismatches"] = max(evidence["mismatches"], counts["mismatch"])
        evidence["internalErrors"] = max(
            evidence["internalErrors"], counts["internal_error"]
        )
    if args.experimental_report:
        experimental = load_json(args.experimental_report)
        counts = experimental["fullMatrix"]["comparisonCounts"]
        evidence["mismatches"] = max(evidence["mismatches"], counts["mismatch"])
        evidence["internalErrors"] = max(
            evidence["internalErrors"], counts["internal_error"]
        )
    if args.confidence_report:
        confidence = load_json(args.confidence_report)
        evidence["crossPythonPassed"] = (
            confidence["crossPython"]["status"] == "contract_enforced_by_ci_matrix"
            and confidence["crossPython"]["requiredVersions"] == ["3.10", "3.12", "3.13"]
        )
    if args.health_report:
        health = load_json(args.health_report)
        evidence["healthErrors"] = health["counts"]["error"]
    if args.browser_report:
        browser = load_json(args.browser_report)
        evidence["browserLegacyPassed"] = (
            browser.get("browserExecutionMode") == "legacy"
            and browser.get("browserLegacyPassed") is True
            and browser.get("graphRuntimeAvailable") is False
            and browser.get("failed") == 0
        )

    report = build_release_hardening_report(
        database,
        direct,
        golden,
        core,
        dossier,
        gate_evidence=evidence,
    )
    if args.output:
        write_release_hardening_report(report, args.output)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["readiness"]["ready_for_rc_review"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
