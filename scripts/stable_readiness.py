from __future__ import annotations

import argparse
import json
from pathlib import Path


VERSION = "1.0.0"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Aggregate the Stable 1.0 readiness status.")
    parser.add_argument("--accuracy-report", type=Path, required=True)
    parser.add_argument("--release-report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    args = parse_args()
    accuracy = load(args.accuracy_report)
    release = load(args.release_report)
    readiness = accuracy["readiness"]
    evidence = accuracy["externalGateEvidence"]
    productive = accuracy["productiveBehavior"]
    blockers = list(readiness["blockers"]) + list(release.get("blockers", []))
    exact_gates = {
        "acceptance": accuracy["realAcceptance"] == {**accuracy["realAcceptance"], "total": 61, "passed": 61, "failed": 0},
        "golden": accuracy["golden"] == {"total": 60, "passed": 60, "failed": 0},
        "core": accuracy["coreReferences"] == {"total": 8, "passed": 8, "failed": 0},
        "metamorphic": accuracy["metamorphic"] == {"total": 16, "passed": 16, "failed": 0},
        "boundary": accuracy["boundaryMatrix"]["total"] == 32 and accuracy["boundaryMatrix"]["passed"] == 32,
        "partials": accuracy["partialCases"]["total"] == 14 and accuracy["partialCases"]["failed"] == 0,
        "python_regression": readiness["python_regression_passed"] and readiness["python_regression_cases"] == 1_977,
        "graph_mirror": readiness["graph_mirror_passed"] and readiness["graph_mirror_cases"] == 1_977,
        "browser_regression": readiness["browser_regression_passed"] and readiness["browser_regression_cases"] == 1_977,
        "browser_hardening": readiness["browser_legacy_passed"] and accuracy["directAcceptance"]["passed"] == 44,
        "validator": readiness["validator_coverage"] == 100.0 and readiness["validator_implemented_rules"] == readiness["validator_tested_rules"] == 42,
        "health": evidence["healthErrors"] == 0,
        "mismatches": readiness["mismatches"] == evidence["mismatches"] == 0,
        "internal_errors": readiness["internal_errors"] == evidence["internalErrors"] == 0,
        "cross_python": readiness["cross_python_passed"],
        "release_build": release["release_build_passed"],
        "clean_install": release["clean_install_passed"],
        "build_acceptance": release["release_build_acceptance_passed"],
        "version": release["version"] == VERSION and release["version_consistent"],
        "execution_contracts": (
            accuracy["defaultExecutionMode"] == "legacy"
            and accuracy["executionModes"] == ["legacy", "shadow", "graph_experimental"]
            and productive["legacyRemainsDefault"]
            and productive["browserRemainsLegacy"]
            and productive["desktopRemainsLegacy"]
            and productive["guiRemainsLegacy"]
            and not productive["readyForDefaultUse"]
            and not productive["solverRulesChanged"]
            and not productive["folderHeuristicsAdded"]
            and not readiness["ready_for_default_use"]
        ),
    }
    blockers.extend(f"{name}_failed" for name, passed in exact_gates.items() if not passed)
    blockers = list(dict.fromkeys(blockers))
    payload = {
        "schemaVersion": 1,
        "version": VERSION,
        "ready_for_stable_1_0": not blockers,
        "release_blockers": blockers,
        "mismatches": readiness["mismatches"],
        "internal_errors": readiness["internal_errors"],
        "acceptance_total": accuracy["realAcceptance"]["total"],
        "acceptance_passed": accuracy["realAcceptance"]["passed"],
        "golden_total": accuracy["golden"]["total"],
        "golden_passed": accuracy["golden"]["passed"],
        "accuracy9_core_total": accuracy["coreReferences"]["total"],
        "accuracy9_core_passed": accuracy["coreReferences"]["passed"],
        "metamorphic_total": accuracy["metamorphic"]["total"],
        "metamorphic_passed": accuracy["metamorphic"]["passed"],
        "boundary_total": accuracy["boundaryMatrix"]["total"],
        "boundary_passed": accuracy["boundaryMatrix"]["passed"],
        "browser_regression": {"passed": readiness["browser_regression_cases"], "total": 1_977},
        "browser_hardening": {"passed": accuracy["directAcceptance"]["passed"], "total": 44},
        "python_regression": {"passed": readiness["python_regression_cases"], "total": 1_977},
        "graph_mirror": {"passed": readiness["graph_mirror_cases"], "total": 1_977},
        "cross_python": readiness["cross_python_passed"],
        "validator_coverage": readiness["validator_coverage"],
        "validator_rules": {"passed": readiness["validator_tested_rules"], "total": readiness["validator_implemented_rules"]},
        "health_errors": evidence["healthErrors"],
        "known_partial_cases": accuracy["partialCases"]["total"],
        "clean_install_passed": release["clean_install_passed"],
        "release_build_passed": release["release_build_passed"],
        "release_build_acceptance_passed": release["release_build_acceptance_passed"],
        "version_consistent": release["version_consistent"],
        "ready_for_default_use": False,
        "gates": exact_gates,
    }
    args.output.mkdir(parents=True, exist_ok=True)
    path = args.output / "Stable_Readiness_1.0.0.json"
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload["ready_for_stable_1_0"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
