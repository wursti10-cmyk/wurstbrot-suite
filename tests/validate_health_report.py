from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path


REQUIRED_FIELDS = {
    "schemaVersion",
    "gameVersion",
    "generatedAt",
    "passed",
    "counts",
    "countsByRule",
    "vehicleCount",
    "countryCount",
    "treeCount",
    "groupCount",
    "graphStatistics",
    "findings",
    "ignoredRules",
}


def validate(path: Path) -> None:
    report = json.loads(path.read_text(encoding="utf-8"))
    missing = REQUIRED_FIELDS - set(report)
    if missing:
        raise AssertionError(f"Health report fields missing: {sorted(missing)}")
    if report["schemaVersion"] != 1:
        raise AssertionError("Unsupported health report schemaVersion")
    if set(report["counts"]) != {"error", "warning", "info"}:
        raise AssertionError("Health report severity counts are incomplete")
    actual_counts = {severity: 0 for severity in ("error", "warning", "info")}
    actual_rules = Counter()
    for finding in report["findings"]:
        required = {"rule_id", "severity", "message", "entity_type", "details"}
        if required - set(finding):
            raise AssertionError(f"Finding fields missing: {required - set(finding)}")
        actual_counts[finding["severity"]] += 1
        actual_rules[finding["rule_id"]] += 1
    if report["counts"] != actual_counts:
        raise AssertionError(f"Severity counts disagree: {report['counts']} != {actual_counts}")
    if report["countsByRule"] != dict(sorted(actual_rules.items())):
        raise AssertionError("Rule counts disagree with findings")
    if not report["passed"] or report["counts"]["error"] != 0:
        raise AssertionError("Released sample database contains ERROR findings")


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("usage: validate_health_report.py WT_Health_*.json")
    validate(Path(sys.argv[1]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
