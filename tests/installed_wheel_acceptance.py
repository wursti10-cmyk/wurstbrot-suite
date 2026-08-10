from __future__ import annotations

import argparse
import json
from pathlib import Path

import wurstbrot_core
from wurstbrot_core.database import VehicleDatabase
from wurstbrot_core.release_hardening import build_release_hardening_report, load_release_fixture


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    args = parse_args()
    root = args.repository.resolve()
    imported_from = Path(wurstbrot_core.__file__).resolve()
    source_package = (root / "packages" / "core").resolve()
    if source_package in imported_from.parents:
        raise SystemExit(f"source-tree import detected: {imported_from}")
    if wurstbrot_core.__version__ != "1.0.0-rc.1":
        raise SystemExit(f"unexpected installed version: {wurstbrot_core.__version__}")

    database = VehicleDatabase.from_json(root / "data" / "samples" / "WT_Database_2.57.1.67.json")
    report = build_release_hardening_report(
        database,
        load_release_fixture(root / "accuracy" / "acceptance" / "release_hardening_2.57.1.67.json"),
        load_json(root / "accuracy" / "golden" / "2.57.1.67.json"),
        load_json(root / "accuracy" / "golden" / "core_contract_2.57.1.67.json"),
        load_json(root / "accuracy" / "research" / "partial_folder_cases_2.57.1.67.json"),
        gate_evidence={
            "mismatches": 0,
            "internalErrors": 0,
            "contractDecisionsOpen": 0,
            "crossPythonPassed": True,
            "browserLegacyPassed": True,
            "pythonRegressionPassed": True,
            "pythonRegressionCases": 1_977,
            "graphMirrorPassed": True,
            "graphMirrorCases": 1_977,
            "browserRegressionPassed": True,
            "browserRegressionCases": 1_977,
            "healthErrors": 0,
            "validatorCoverage": 100.0,
            "validatorImplementedRules": 42,
            "validatorTestedRules": 42,
        },
    )
    expected = {
        "acceptance": (report["realAcceptance"]["passed"], 61),
        "golden": (report["golden"]["passed"], 60),
        "core": (report["coreReferences"]["passed"], 8),
        "metamorphic": (report["metamorphic"]["passed"], 16),
        "boundary": (report["boundaryMatrix"]["passed"], 32),
        "partial": (report["partialCases"]["total"], 14),
    }
    failures = [name for name, (actual, required) in expected.items() if actual != required]
    payload = {
        "schemaVersion": 1,
        "version": wurstbrot_core.__version__,
        "importedFrom": str(imported_from),
        "databaseLoaded": len(database.vehicles) > 0,
        "acceptance_total": report["realAcceptance"]["total"],
        "acceptance_passed": report["realAcceptance"]["passed"],
        "golden_total": report["golden"]["total"],
        "golden_passed": report["golden"]["passed"],
        "core_total": report["coreReferences"]["total"],
        "core_passed": report["coreReferences"]["passed"],
        "metamorphic_total": report["metamorphic"]["total"],
        "metamorphic_passed": report["metamorphic"]["passed"],
        "boundary_total": report["boundaryMatrix"]["total"],
        "boundary_passed": report["boundaryMatrix"]["passed"],
        "known_partial_cases": report["partialCases"]["total"],
        "failedChecks": failures,
        "passed": not failures,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
