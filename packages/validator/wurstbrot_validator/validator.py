from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Iterable


class Severity(str, Enum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass(frozen=True)
class Finding:
    rule_id: str
    severity: Severity
    message: str
    entity_type: str
    entity_id: str | None = None
    source_field: str | None = None
    details: dict[str, Any] | None = None
    suggestion: str | None = None

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "rule_id": self.rule_id,
            "severity": self.severity.value,
            "message": self.message,
            "entity_type": self.entity_type,
            "details": self.details or {},
        }
        if self.entity_id is not None:
            result["entity_id"] = self.entity_id
        if self.source_field is not None:
            result["source_field"] = self.source_field
        if self.suggestion is not None:
            result["suggestion"] = self.suggestion
        return result


@dataclass(frozen=True)
class HealthReport:
    schema_version: int
    game_version: str
    generated_at: str
    passed: bool
    counts: dict[str, int]
    counts_by_rule: dict[str, int]
    vehicle_count: int
    country_count: int
    tree_count: int
    group_count: int
    graph_statistics: dict[str, int]
    findings: tuple[Finding, ...]
    ignored_rules: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "schemaVersion": self.schema_version,
            "gameVersion": self.game_version,
            "generatedAt": self.generated_at,
            "passed": self.passed,
            "counts": self.counts,
            "countsByRule": self.counts_by_rule,
            "vehicleCount": self.vehicle_count,
            "countryCount": self.country_count,
            "treeCount": self.tree_count,
            "groupCount": self.group_count,
            "graphStatistics": self.graph_statistics,
            "findings": [finding.to_dict() for finding in self.findings],
            "ignoredRules": list(self.ignored_rules),
        }

    def to_text(self) -> str:
        lines = [
            f"Validation passed: {'yes' if self.passed else 'no'}",
            f"Errors: {self.counts['error']}",
            f"Warnings: {self.counts['warning']}",
            f"Info: {self.counts['info']}",
            f"Vehicles: {self.vehicle_count}",
            f"Countries: {self.country_count}",
            f"Trees: {self.tree_count}",
            f"Groups: {self.group_count}",
            f"Cycles: {self.counts_by_rule.get('GRAPH_CYCLE', 0)}",
            "Missing predecessors: "
            f"{self.counts_by_rule.get('GRAPH_MISSING_PREDECESSOR', 0)}",
        ]
        if self.ignored_rules:
            lines.append(f"Ignored rules: {', '.join(self.ignored_rules)}")
        return "\n".join(lines) + "\n"


ROOT_REQUIRED = {
    "schemaVersion": int,
    "gameVersion": str,
    "economy": dict,
    "vehicles": list,
    "predecessors": dict,
    "groups": dict,
    "rankUnlock": dict,
}
VEHICLE_REQUIRED = {
    "id": str,
    "name": str,
    "countryId": str,
    "branchId": str,
    "rank": int,
    "rp": int,
    "sl": int,
}
GAME_VERSION_PATTERN = re.compile(r"^\d+(?:\.\d+){2,3}(?:[-+][A-Za-z0-9.-]+)?$")


class _Collector:
    def __init__(self, ignored_rules: Iterable[str]) -> None:
        self.ignored = frozenset(ignored_rules)
        self.findings: list[Finding] = []

    def add(
        self,
        rule_id: str,
        severity: Severity,
        message: str,
        entity_type: str,
        entity_id: str | None = None,
        source_field: str | None = None,
        details: dict[str, Any] | None = None,
        suggestion: str | None = None,
    ) -> None:
        if rule_id in self.ignored:
            return
        self.findings.append(
            Finding(
                rule_id=rule_id,
                severity=severity,
                message=message,
                entity_type=entity_type,
                entity_id=entity_id,
                source_field=source_field,
                details=details or {},
                suggestion=suggestion,
            )
        )


def _is_integer(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _entity_id(vehicle: Any, index: int) -> str:
    if isinstance(vehicle, dict) and isinstance(vehicle.get("id"), str):
        return vehicle["id"]
    return f"vehicles[{index}]"


def validate_database(
    database: dict[str, Any],
    *,
    ignored_rules: Iterable[str] = (),
    generated_at: str | None = None,
) -> HealthReport:
    collector = _Collector(ignored_rules)
    if not isinstance(database, dict):
        collector.add(
            "SCHEMA_INVALID_TYPE",
            Severity.ERROR,
            "Database root must be an object.",
            "database",
            source_field="$",
            details={"actual_type": type(database).__name__},
        )
        database = {}

    for field, expected_type in ROOT_REQUIRED.items():
        if field not in database:
            collector.add(
                "SCHEMA_MISSING_FIELD",
                Severity.ERROR,
                "Database is missing a required root field.",
                "database",
                source_field=field,
                details={"expected_type": expected_type.__name__},
            )
        elif not isinstance(database[field], expected_type) or (
            expected_type is int and isinstance(database[field], bool)
        ):
            collector.add(
                "SCHEMA_INVALID_TYPE",
                Severity.ERROR,
                "Database root field has the wrong type.",
                "database",
                source_field=field,
                details={
                    "expected_type": expected_type.__name__,
                    "actual_type": type(database[field]).__name__,
                },
            )

    if database.get("schemaVersion") != 1:
        collector.add(
            "SCHEMA_INVALID_VERSION",
            Severity.ERROR,
            "Only datamine schemaVersion 1 is supported.",
            "database",
            source_field="schemaVersion",
            details={"actual": database.get("schemaVersion"), "supported": [1]},
        )

    game_version = database.get("gameVersion")
    if not isinstance(game_version, str) or not game_version.strip():
        collector.add(
            "GAME_VERSION_MISSING",
            Severity.ERROR,
            "gameVersion is required and must not be empty.",
            "database",
            source_field="gameVersion",
            details={"actual": game_version},
        )
        normalized_version = "unknown"
    else:
        normalized_version = game_version.strip()
        invalid_version = normalized_version.lower() in {"unknown", "unbekannt"}
        invalid_version = invalid_version or not GAME_VERSION_PATTERN.fullmatch(normalized_version)
        if invalid_version:
            collector.add(
                "GAME_VERSION_INVALID",
                Severity.ERROR,
                "gameVersion is not a recognized dotted game version.",
                "database",
                source_field="gameVersion",
                details={"actual": normalized_version},
                suggestion="Use the exact value from version.txt.",
            )

    economy = database.get("economy") if isinstance(database.get("economy"), dict) else {}
    rp_per_ge = economy.get("rpPerGE")
    if not _is_integer(rp_per_ge) or rp_per_ge <= 0:
        collector.add(
            "ECONOMY_INVALID_RP_PER_GE",
            Severity.ERROR,
            "economy.rpPerGE must be a positive integer.",
            "economy",
            source_field="rpPerGE",
            details={"actual": rp_per_ge},
        )

    raw_vehicles = database.get("vehicles") if isinstance(database.get("vehicles"), list) else []
    valid_vehicles: list[dict[str, Any]] = []
    ids_seen: Counter[str] = Counter()

    for index, raw_vehicle in enumerate(raw_vehicles):
        entity_id = _entity_id(raw_vehicle, index)
        if not isinstance(raw_vehicle, dict):
            collector.add(
                "VEHICLE_INVALID_FIELD_TYPE",
                Severity.ERROR,
                "Vehicle entry must be an object.",
                "vehicle",
                entity_id,
                details={"actual_type": type(raw_vehicle).__name__},
            )
            continue
        valid_vehicles.append(raw_vehicle)
        for field, expected_type in VEHICLE_REQUIRED.items():
            if field not in raw_vehicle:
                collector.add(
                    "VEHICLE_MISSING_FIELD",
                    Severity.ERROR,
                    "Vehicle is missing a required field.",
                    "vehicle",
                    entity_id,
                    field,
                    {"expected_type": expected_type.__name__},
                )
            elif not isinstance(raw_vehicle[field], expected_type) or (
                expected_type is int and isinstance(raw_vehicle[field], bool)
            ):
                rule_id = (
                    "COST_NON_NUMERIC" if field in {"rp", "sl"} else "VEHICLE_INVALID_FIELD_TYPE"
                )
                collector.add(
                    rule_id,
                    Severity.ERROR,
                    "Vehicle field has the wrong type.",
                    "vehicle",
                    entity_id,
                    field,
                    {
                        "expected_type": expected_type.__name__,
                        "actual_type": type(raw_vehicle[field]).__name__,
                        "actual": raw_vehicle[field],
                    },
                )

        vehicle_id = raw_vehicle.get("id")
        if isinstance(vehicle_id, str):
            ids_seen[vehicle_id] += 1

        rank = raw_vehicle.get("rank")
        if not _is_integer(rank) or rank < 1:
            collector.add(
                "RANK_INVALID",
                Severity.ERROR,
                "Vehicle rank must be a positive integer.",
                "vehicle",
                entity_id,
                "rank",
                {"actual": rank},
            )

        for field, rule_id in (("rp", "COST_NEGATIVE_RP"), ("sl", "COST_NEGATIVE_SL")):
            value = raw_vehicle.get(field)
            if _is_integer(value) and value < 0:
                collector.add(
                    rule_id,
                    Severity.ERROR,
                    f"Vehicle {field.upper()} cost must not be negative.",
                    "vehicle",
                    entity_id,
                    field,
                    {"actual": value},
                )

        rp = raw_vehicle.get("rp")
        sl = raw_vehicle.get("sl")
        if _is_integer(rp) and _is_integer(sl):
            if rp == 0 and sl > 0:
                collector.add(
                    "COST_ZERO_RP_WITH_SL",
                    Severity.WARNING,
                    "Vehicle has zero RP but a positive SL purchase cost.",
                    "vehicle",
                    entity_id,
                    "rp",
                    {"rp": rp, "sl": sl},
                )
            if sl == 0 and rp > 0:
                collector.add(
                    "COST_ZERO_SL_WITH_RP",
                    Severity.WARNING,
                    "Vehicle has RP cost but zero SL purchase cost.",
                    "vehicle",
                    entity_id,
                    "sl",
                    {"rp": rp, "sl": sl},
                )

        name = raw_vehicle.get("name")
        if "name" not in raw_vehicle:
            collector.add(
                "LOCALIZATION_MISSING_NAME",
                Severity.WARNING,
                "Vehicle has no name field.",
                "vehicle",
                entity_id,
                "name",
            )
        elif not isinstance(name, str) or not name.strip():
            collector.add(
                "LOCALIZATION_EMPTY",
                Severity.WARNING,
                "Vehicle has no localized display name.",
                "vehicle",
                entity_id,
                "name",
            )
        elif isinstance(vehicle_id, str) and name.strip() == vehicle_id:
            collector.add(
                "LOCALIZATION_INTERNAL_ID",
                Severity.WARNING,
                "Vehicle display name is identical to its internal ID.",
                "vehicle",
                entity_id,
                "name",
            )

        special_rules = (
            ("hiddenResearch", "SPECIAL_HIDDEN_RESEARCH", "Hidden research vehicle retained."),
            ("reqUnlock", "SPECIAL_EXTERNAL_UNLOCK", "External unlock requires manual semantics."),
            ("reserve", "SPECIAL_RESERVE", "Reserve vehicle is treated as initially available."),
            ("premium", "SPECIAL_PREMIUM", "Premium vehicle is outside regular progression."),
            ("special", "SPECIAL_NON_REGULAR", "Event, squadron or legacy vehicle is non-regular."),
        )
        for field, rule_id, message in special_rules:
            if raw_vehicle.get(field):
                collector.add(
                    rule_id,
                    Severity.INFO,
                    message,
                    "vehicle",
                    entity_id,
                    field,
                    {"value": raw_vehicle.get(field)},
                )

    for vehicle_id, count in ids_seen.items():
        if count > 1:
            collector.add(
                "VEHICLE_DUPLICATE_ID",
                Severity.ERROR,
                "Vehicle ID occurs more than once.",
                "vehicle",
                vehicle_id,
                "id",
                {"occurrences": count},
            )

    vehicle_map = {
        item["id"]: item
        for item in valid_vehicles
        if isinstance(item.get("id"), str) and ids_seen[item["id"]] == 1
    }
    _validate_localization_duplicates(vehicle_map, collector)
    graph_stats = _validate_graph(database, vehicle_map, collector)
    _validate_groups(database, vehicle_map, collector)
    _validate_rank_unlock(database, vehicle_map, collector)

    findings = tuple(sorted(collector.findings, key=_finding_sort_key))
    severity_counts = Counter(finding.severity.value for finding in findings)
    rule_counts = Counter(finding.rule_id for finding in findings)
    counts = {severity.value: severity_counts[severity.value] for severity in Severity}
    countries = {
        item.get("countryId")
        for item in vehicle_map.values()
        if isinstance(item.get("countryId"), str)
    }
    trees = {
        (item.get("countryId"), item.get("branchId"))
        for item in vehicle_map.values()
        if isinstance(item.get("countryId"), str) and isinstance(item.get("branchId"), str)
    }
    groups = database.get("groups") if isinstance(database.get("groups"), dict) else {}
    timestamp = generated_at or datetime.now(timezone.utc).isoformat()
    return HealthReport(
        schema_version=1,
        game_version=normalized_version,
        generated_at=timestamp,
        passed=counts["error"] == 0,
        counts=counts,
        counts_by_rule=dict(sorted(rule_counts.items())),
        vehicle_count=len(raw_vehicles),
        country_count=len(countries),
        tree_count=len(trees),
        group_count=len(groups),
        graph_statistics=graph_stats,
        findings=findings,
        ignored_rules=tuple(sorted(collector.ignored)),
    )


def _finding_sort_key(finding: Finding) -> tuple[int, str, str, str, str]:
    severity_order = {Severity.ERROR: 0, Severity.WARNING: 1, Severity.INFO: 2}
    return (
        severity_order[finding.severity],
        finding.rule_id,
        finding.entity_type,
        finding.entity_id or "",
        finding.source_field or "",
    )


def _validate_localization_duplicates(
    vehicle_map: dict[str, dict[str, Any]], collector: _Collector
) -> None:
    by_tree_and_name: defaultdict[tuple[str, str, str], list[str]] = defaultdict(list)
    for vehicle_id, item in vehicle_map.items():
        name = item.get("name")
        country = item.get("countryId")
        branch = item.get("branchId")
        if (
            isinstance(name, str)
            and name.strip()
            and isinstance(country, str)
            and isinstance(branch, str)
        ):
            by_tree_and_name[(country, branch, name.strip().casefold())].append(vehicle_id)
    for (country, branch, name), vehicle_ids in by_tree_and_name.items():
        if len(vehicle_ids) > 1:
            collector.add(
                "LOCALIZATION_DUPLICATE_NAME",
                Severity.INFO,
                "Multiple vehicles share a visible name in one research tree.",
                "research_tree",
                f"{country}/{branch}",
                "name",
                {"normalized_name": name, "vehicle_ids": sorted(vehicle_ids)},
            )


def _validate_graph(
    database: dict[str, Any],
    vehicle_map: dict[str, dict[str, Any]],
    collector: _Collector,
) -> dict[str, int]:
    predecessors = database.get("predecessors")
    predecessors = predecessors if isinstance(predecessors, dict) else {}
    usable: dict[str, str | None] = {}
    missing_count = 0
    edge_count = 0

    for vehicle_id in sorted(vehicle_map):
        if vehicle_id not in predecessors:
            collector.add(
                "GRAPH_UNREACHABLE",
                Severity.WARNING,
                "Vehicle has no explicit predecessor entry and is treated as a root.",
                "vehicle",
                vehicle_id,
                "predecessors",
            )
            usable[vehicle_id] = None
            continue
        predecessor = predecessors.get(vehicle_id)
        if isinstance(predecessor, list):
            collector.add(
                "GRAPH_CONFLICTING_PREDECESSORS",
                Severity.ERROR,
                "Vehicle defines multiple predecessor candidates.",
                "vehicle",
                vehicle_id,
                "predecessors",
                {"predecessors": predecessor},
            )
            usable[vehicle_id] = None
            continue
        if predecessor is not None and not isinstance(predecessor, str):
            collector.add(
                "SCHEMA_INVALID_TYPE",
                Severity.ERROR,
                "Predecessor must be a vehicle ID or null.",
                "vehicle",
                vehicle_id,
                "predecessors",
                {"actual_type": type(predecessor).__name__},
            )
            usable[vehicle_id] = None
            continue
        usable[vehicle_id] = predecessor
        if predecessor is None:
            continue
        edge_count += 1
        if predecessor == vehicle_id:
            collector.add(
                "GRAPH_SELF_REFERENCE",
                Severity.ERROR,
                "Vehicle references itself as predecessor.",
                "vehicle",
                vehicle_id,
                "predecessors",
            )
            continue
        if predecessor not in vehicle_map:
            missing_count += 1
            collector.add(
                "GRAPH_MISSING_PREDECESSOR",
                Severity.ERROR,
                "Vehicle references a missing predecessor.",
                "vehicle",
                vehicle_id,
                "predecessors",
                {"predecessor": predecessor},
            )
            continue
        child = vehicle_map[vehicle_id]
        parent = vehicle_map[predecessor]
        if child.get("countryId") != parent.get("countryId"):
            collector.add(
                "GRAPH_CROSS_NATION",
                Severity.ERROR,
                "Predecessor crosses national research trees.",
                "vehicle",
                vehicle_id,
                "predecessors",
                {"predecessor": predecessor},
            )
        if child.get("branchId") != parent.get("branchId"):
            collector.add(
                "GRAPH_CROSS_BRANCH",
                Severity.ERROR,
                "Predecessor crosses vehicle types.",
                "vehicle",
                vehicle_id,
                "predecessors",
                {"predecessor": predecessor},
            )
        child_rank, parent_rank = child.get("rank"), parent.get("rank")
        if _is_integer(child_rank) and _is_integer(parent_rank) and parent_rank > child_rank:
            collector.add(
                "GRAPH_RANK_BACKWARDS",
                Severity.ERROR,
                "Predecessor rank is higher than the vehicle rank.",
                "vehicle",
                vehicle_id,
                "predecessors",
                {"predecessor": predecessor, "predecessor_rank": parent_rank, "rank": child_rank},
            )

    cycles: set[tuple[str, ...]] = set()
    max_depth = 0
    for start in sorted(vehicle_map):
        trail: list[str] = []
        positions: dict[str, int] = {}
        current: str | None = start
        while current in vehicle_map and current not in positions:
            positions[current] = len(trail)
            trail.append(current)
            next_id = usable.get(current)
            current = next_id if isinstance(next_id, str) else None
        max_depth = max(max_depth, len(trail))
        if current in positions:
            cycle = trail[positions[current] :]
            signature = tuple(sorted(cycle))
            if signature not in cycles:
                cycles.add(signature)
                collector.add(
                    "GRAPH_CYCLE",
                    Severity.ERROR,
                    "Research graph contains a cycle.",
                    "research_graph",
                    signature[0],
                    "predecessors",
                    {"vehicle_ids": list(signature)},
                )
    return {
        "vehicleCount": len(vehicle_map),
        "edgeCount": edge_count,
        "rootCount": sum(usable.get(vehicle_id) is None for vehicle_id in vehicle_map),
        "cycleCount": len(cycles),
        "missingPredecessorCount": missing_count,
        "maxDepth": max_depth,
    }


def _validate_groups(
    database: dict[str, Any],
    vehicle_map: dict[str, dict[str, Any]],
    collector: _Collector,
) -> None:
    groups = database.get("groups")
    if not isinstance(groups, dict):
        return
    memberships: defaultdict[str, list[str]] = defaultdict(list)
    for group_id in sorted(groups):
        members = groups[group_id]
        if not isinstance(members, list):
            collector.add(
                "SCHEMA_INVALID_TYPE",
                Severity.ERROR,
                "Group members must be an ordered array.",
                "group",
                str(group_id),
                "groups",
                {"actual_type": type(members).__name__},
            )
            continue
        known: list[str] = []
        for index, member in enumerate(members):
            if not isinstance(member, str) or member not in vehicle_map:
                collector.add(
                    "GROUP_UNKNOWN_VEHICLE",
                    Severity.WARNING,
                    "Group contains a vehicle absent from the regular database.",
                    "group",
                    str(group_id),
                    "groups",
                    {"member": member, "index": index},
                    "Check whether the member was intentionally filtered as non-regular.",
                )
                continue
            known.append(member)
            memberships[member].append(str(group_id))
            item = vehicle_map[member]
            if item.get("group") != group_id or item.get("groupIndex") != index:
                collector.add(
                    "GROUP_INDEX_MISMATCH",
                    Severity.WARNING,
                    "Vehicle group metadata disagrees with ordered group membership.",
                    "vehicle",
                    member,
                    "groupIndex",
                    {
                        "group": group_id,
                        "expected_index": index,
                        "vehicle_group": item.get("group"),
                        "vehicle_group_index": item.get("groupIndex"),
                    },
                )
        if len(members) == 1:
            collector.add(
                "GROUP_SINGLE_VEHICLE",
                Severity.INFO,
                "Group contains only one vehicle.",
                "group",
                str(group_id),
                "groups",
            )
        trees = {
            (vehicle_map[member].get("countryId"), vehicle_map[member].get("branchId"))
            for member in known
        }
        if len(trees) > 1:
            collector.add(
                "GROUP_CROSS_TREE",
                Severity.ERROR,
                "Group spans nations or vehicle types.",
                "group",
                str(group_id),
                "groups",
                {"trees": sorted([list(tree) for tree in trees])},
            )
    for member, group_ids in memberships.items():
        if len(set(group_ids)) > 1:
            collector.add(
                "GROUP_CONFLICTING_MEMBERSHIP",
                Severity.ERROR,
                "Vehicle belongs to multiple groups.",
                "vehicle",
                member,
                "group",
                {"groups": sorted(set(group_ids))},
            )


def _validate_rank_unlock(
    database: dict[str, Any],
    vehicle_map: dict[str, dict[str, Any]],
    collector: _Collector,
) -> None:
    config = database.get("rankUnlock")
    if not isinstance(config, dict):
        return
    trees: defaultdict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for item in vehicle_map.values():
        country, branch = item.get("countryId"), item.get("branchId")
        if isinstance(country, str) and isinstance(branch, str):
            trees[(country, branch)].append(item)

    for (country, branch), items in sorted(trees.items()):
        ranks = sorted({item.get("rank") for item in items if _is_integer(item.get("rank"))})
        if not ranks:
            continue
        raw_requirements = config.get(country, {})
        raw_requirements = (
            raw_requirements.get(branch, {}) if isinstance(raw_requirements, dict) else {}
        )
        if not isinstance(raw_requirements, dict):
            collector.add(
                "SCHEMA_INVALID_TYPE",
                Severity.ERROR,
                "Rank unlock configuration must be an object.",
                "research_tree",
                f"{country}/{branch}",
                "rankUnlock",
            )
            continue
        parsed: dict[int, Any] = {}
        for raw_rank, requirement in raw_requirements.items():
            try:
                rank = int(raw_rank)
            except (TypeError, ValueError):
                collector.add(
                    "RANK_UNLOCK_ORDER_CONFLICT",
                    Severity.ERROR,
                    "Rank unlock key is not a numeric rank.",
                    "research_tree",
                    f"{country}/{branch}",
                    "rankUnlock",
                    {"rank_key": raw_rank},
                )
                continue
            parsed[rank] = requirement
        for rank in ranks:
            if rank >= max(ranks):
                continue
            requirement = parsed.get(rank)
            if requirement is None or requirement == 0:
                collector.add(
                    "RANK_UNLOCK_MISSING",
                    Severity.WARNING,
                    "Higher ranks exist but this rank has no unlock requirement.",
                    "research_tree",
                    f"{country}/{branch}",
                    "rankUnlock",
                    {"rank": rank},
                )
                continue
            if not _is_integer(requirement):
                collector.add(
                    "VEHICLE_INVALID_FIELD_TYPE",
                    Severity.ERROR,
                    "Rank unlock requirement must be an integer.",
                    "research_tree",
                    f"{country}/{branch}",
                    "rankUnlock",
                    {"rank": rank, "actual": requirement},
                )
                continue
            if requirement < 0:
                collector.add(
                    "RANK_UNLOCK_NEGATIVE",
                    Severity.ERROR,
                    "Rank unlock requirement must not be negative.",
                    "research_tree",
                    f"{country}/{branch}",
                    "rankUnlock",
                    {"rank": rank, "requirement": requirement},
                )
                continue
            if requirement > 20:
                collector.add(
                    "RANK_UNLOCK_UNREALISTIC",
                    Severity.WARNING,
                    "Rank unlock requirement exceeds the diagnostic threshold of 20.",
                    "research_tree",
                    f"{country}/{branch}",
                    "rankUnlock",
                    {"rank": rank, "requirement": requirement, "threshold": 20},
                )
            available = sum(
                item.get("rank") == rank
                and not item.get("premium")
                and not item.get("special")
                for item in items
            )
            if requirement > available:
                collector.add(
                    "RANK_UNLOCK_EXCEEDS_AVAILABLE",
                    Severity.ERROR,
                    "Rank unlock requirement exceeds available regular vehicles.",
                    "research_tree",
                    f"{country}/{branch}",
                    "rankUnlock",
                    {"rank": rank, "requirement": requirement, "available": available},
                )


def legacy_validation_report(report: HealthReport) -> dict[str, Any]:
    """Preserve the WT_Validation_* shape while sourcing it from structured findings."""
    by_rule: defaultdict[str, list[Finding]] = defaultdict(list)
    for finding in report.findings:
        by_rule[finding.rule_id].append(finding)
    return {
        "schemaVersion": 1,
        "gameVersion": report.game_version,
        "generatedAt": report.generated_at,
        "passed": report.passed,
        "stats": {
            "vehicles": report.vehicle_count,
            "countries": report.country_count,
            "branches": report.tree_count,
            "groups": report.group_count,
        },
        "errors": {
            "duplicates": len(by_rule["VEHICLE_DUPLICATE_ID"]),
            "invalidPredecessors": [
                item.to_dict() for item in by_rule["GRAPH_MISSING_PREDECESSOR"]
            ],
            "crossTreeLinks": [
                item.to_dict()
                for rule in ("GRAPH_CROSS_NATION", "GRAPH_CROSS_BRANCH")
                for item in by_rule[rule]
            ],
            "rankBackwards": [item.to_dict() for item in by_rule["GRAPH_RANK_BACKWARDS"]],
            "cycles": [item.details.get("vehicle_ids", []) for item in by_rule["GRAPH_CYCLE"]],
            "negativeCosts": sorted(
                {
                    item.entity_id
                    for rule in ("COST_NEGATIVE_RP", "COST_NEGATIVE_SL")
                    for item in by_rule[rule]
                    if item.entity_id
                }
            ),
        },
        "warnings": {
            "missingLocalizedNames": [
                item.entity_id
                for rule in ("LOCALIZATION_EMPTY", "LOCALIZATION_INTERNAL_ID")
                for item in by_rule[rule][:500]
                if item.entity_id
            ],
            "missingLocalizedNameCount": sum(
                len(by_rule[rule]) for rule in ("LOCALIZATION_EMPTY", "LOCALIZATION_INTERNAL_ID")
            ),
        },
        "healthReport": f"WT_Health_{report.game_version}.json",
    }


def write_health_reports(report: HealthReport, output: Path) -> tuple[Path, Path]:
    output.mkdir(parents=True, exist_ok=True)
    safe_version = report.game_version.replace("/", "-").replace("\\", "-")
    json_path = output / f"WT_Health_{safe_version}.json"
    text_path = output / f"WT_Health_{safe_version}.txt"
    json_path.write_text(
        json.dumps(report.to_dict(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    text_path.write_text(report.to_text(), encoding="utf-8")
    return json_path, text_path
