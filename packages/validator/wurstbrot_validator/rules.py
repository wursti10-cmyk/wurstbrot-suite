from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


VALIDATOR_VERSION = "1.1.0"


@dataclass(frozen=True)
class RuleDefinition:
    rule_id: str
    severity: str
    category: str
    description: str
    rationale: str
    example: str
    entity_type: str
    source_field: str


def _rule(
    rule_id: str,
    severity: str,
    category: str,
    description: str,
    rationale: str,
    example: str,
    entity_type: str = "database",
    source_field: str = "",
) -> RuleDefinition:
    return RuleDefinition(
        rule_id,
        severity,
        category,
        description,
        rationale,
        example,
        entity_type,
        source_field,
    )


RULE_DEFINITIONS = {
    item.rule_id: item
    for item in (
        _rule(
            "SCHEMA_MISSING_FIELD",
            "error",
            "schema",
            "A required root field is missing.",
            "Consumers cannot interpret an incomplete root object safely.",
            "The database has no vehicles field.",
            source_field="vehicles",
        ),
        _rule(
            "SCHEMA_INVALID_TYPE",
            "error",
            "schema",
            "A structural field has the wrong JSON type.",
            "Wrong container types make traversal ambiguous or unsafe.",
            "groups is an array instead of an object.",
            source_field="groups",
        ),
        _rule(
            "SCHEMA_INVALID_VERSION",
            "error",
            "schema",
            "The database schema version is unsupported.",
            "Readers only implement the declared schema contract.",
            "schemaVersion is 2 while only version 1 is supported.",
            source_field="schemaVersion",
        ),
        _rule(
            "GAME_VERSION_MISSING",
            "error",
            "schema",
            "The game version is absent or empty.",
            "Outputs must be traceable to an exact datamine version.",
            "gameVersion is an empty string.",
            source_field="gameVersion",
        ),
        _rule(
            "GAME_VERSION_INVALID",
            "error",
            "schema",
            "The game version is not a dotted version value.",
            "Unknown labels cannot identify a reproducible source snapshot.",
            "gameVersion is unbekannt.",
            source_field="gameVersion",
        ),
        _rule(
            "ECONOMY_INVALID_RP_PER_GE",
            "error",
            "economy",
            "RP per GE is not a positive integer.",
            "GE conversion requires an exact positive divisor.",
            "economy.rpPerGE is zero.",
            "economy",
            "rpPerGE",
        ),
        _rule(
            "VEHICLE_DUPLICATE_ID",
            "error",
            "identity",
            "A vehicle ID occurs more than once.",
            "IDs are primary keys throughout graph and progress data.",
            "Two vehicle objects use the ID tank_a.",
            "vehicle",
            "id",
        ),
        _rule(
            "VEHICLE_MISSING_FIELD",
            "error",
            "schema",
            "A required vehicle field is missing.",
            "Core calculations require identity, tree, rank and costs.",
            "Vehicle tank_a has no countryId.",
            "vehicle",
            "countryId",
        ),
        _rule(
            "VEHICLE_INVALID_FIELD_TYPE",
            "error",
            "schema",
            "A vehicle or unlock field has the wrong type.",
            "Implicit coercion can hide datamine format changes.",
            "Vehicle rank is the string two.",
            "vehicle",
            "rank",
        ),
        _rule(
            "RANK_INVALID",
            "error",
            "rank",
            "A vehicle rank is not a positive integer.",
            "Research order requires an exact ordinal rank.",
            "Vehicle tank_a has rank 0.",
            "vehicle",
            "rank",
        ),
        _rule(
            "COST_NON_NUMERIC",
            "error",
            "cost",
            "RP or SL cost is not an integer.",
            "Cost arithmetic must use exact integers.",
            "Vehicle tank_a has rp set to many.",
            "vehicle",
            "rp",
        ),
        _rule(
            "COST_NEGATIVE_RP",
            "error",
            "cost",
            "RP cost is negative.",
            "Negative research cost has no valid calculator meaning.",
            "Vehicle tank_a has rp -1.",
            "vehicle",
            "rp",
        ),
        _rule(
            "COST_NEGATIVE_SL",
            "error",
            "cost",
            "SL cost is negative.",
            "Negative purchase cost has no valid calculator meaning.",
            "Vehicle tank_a has sl -1.",
            "vehicle",
            "sl",
        ),
        _rule(
            "COST_ZERO_RP_WITH_SL",
            "warning",
            "cost",
            "A vehicle has zero RP and positive SL.",
            "This can be intentional but is unusual enough to review.",
            "Vehicle tank_a has rp 0 and sl 1000.",
            "vehicle",
            "rp",
        ),
        _rule(
            "COST_ZERO_SL_WITH_RP",
            "warning",
            "cost",
            "A vehicle has positive RP and zero SL.",
            "This can be intentional but may indicate incomplete economy data.",
            "Vehicle tank_a has rp 1000 and sl 0.",
            "vehicle",
            "sl",
        ),
        _rule(
            "GRAPH_MISSING_PREDECESSOR",
            "error",
            "graph",
            "A predecessor ID does not exist.",
            "A broken prerequisite edge makes the research path incomplete.",
            "tank_b references missing tank_a.",
            "vehicle",
            "predecessors",
        ),
        _rule(
            "GRAPH_SELF_REFERENCE",
            "error",
            "graph",
            "A vehicle references itself as predecessor.",
            "A self-edge is an immediate cycle.",
            "predecessors.tank_a equals tank_a.",
            "vehicle",
            "predecessors",
        ),
        _rule(
            "GRAPH_CYCLE",
            "error",
            "graph",
            "The predecessor graph contains a cycle.",
            "Cyclic prerequisites cannot produce a finite research closure.",
            "tank_a requires tank_b and tank_b requires tank_a.",
            "research_graph",
            "predecessors",
        ),
        _rule(
            "GRAPH_CROSS_NATION",
            "error",
            "graph",
            "A predecessor crosses nations.",
            "Research prerequisites must stay in one national tree.",
            "A German vehicle references a US predecessor.",
            "vehicle",
            "predecessors",
        ),
        _rule(
            "GRAPH_CROSS_BRANCH",
            "error",
            "graph",
            "A predecessor crosses vehicle types.",
            "Research prerequisites must stay in one branch tree.",
            "A tank references an aircraft predecessor.",
            "vehicle",
            "predecessors",
        ),
        _rule(
            "GRAPH_RANK_BACKWARDS",
            "error",
            "graph",
            "A predecessor has a higher rank than its child.",
            "A higher-rank prerequisite contradicts progression order.",
            "Rank 2 tank requires a rank 3 tank.",
            "vehicle",
            "predecessors",
        ),
        _rule(
            "GRAPH_UNREACHABLE",
            "warning",
            "graph",
            "A vehicle has no predecessor-map entry.",
            "The loader would silently treat it as a new root.",
            "tank_a exists but predecessors has no tank_a key.",
            "vehicle",
            "predecessors",
        ),
        _rule(
            "GRAPH_CONFLICTING_PREDECESSORS",
            "error",
            "graph",
            "A vehicle defines multiple predecessor candidates.",
            "Schema version 1 permits at most one direct predecessor.",
            "predecessors.tank_a is an array of two IDs.",
            "vehicle",
            "predecessors",
        ),
        _rule(
            "GROUP_UNKNOWN_VEHICLE",
            "warning",
            "folder",
            "A folder references an absent regular vehicle.",
            "Filtered special vehicles and truly stale IDs must remain visible for review.",
            "Folder group_a contains missing_vehicle.",
            "group",
            "groups",
        ),
        _rule(
            "GROUP_CONFLICTING_MEMBERSHIP",
            "error",
            "folder",
            "A vehicle appears in multiple folders.",
            "One vehicle cannot have two authoritative group positions.",
            "tank_a occurs in group_a and group_b.",
            "vehicle",
            "group",
        ),
        _rule(
            "GROUP_SINGLE_VEHICLE",
            "info",
            "folder",
            "A folder contains one vehicle.",
            "Singleton folders are valid but useful migration diagnostics.",
            "group_a contains only tank_a.",
            "group",
            "groups",
        ),
        _rule(
            "GROUP_INDEX_MISMATCH",
            "warning",
            "folder",
            "Vehicle group metadata disagrees with folder order.",
            "Folder order affects sequential prerequisite normalization.",
            "tank_a is first but groupIndex is 1.",
            "vehicle",
            "groupIndex",
        ),
        _rule(
            "GROUP_CROSS_TREE",
            "error",
            "folder",
            "A folder spans nations or vehicle types.",
            "A research folder must belong to one research tree.",
            "group_a contains a German tank and US tank.",
            "group",
            "groups",
        ),
        _rule(
            "RANK_UNLOCK_NEGATIVE",
            "error",
            "rank_unlock",
            "A rank unlock requirement is negative.",
            "Negative purchase counts have no valid progression meaning.",
            "Rank 1 requires -1 purchases.",
            "research_tree",
            "rankUnlock",
        ),
        _rule(
            "RANK_UNLOCK_UNREALISTIC",
            "warning",
            "rank_unlock",
            "A rank unlock requirement exceeds the diagnostic threshold.",
            "Values above 20 warrant review without claiming a game rule.",
            "Rank 1 requires 21 purchases.",
            "research_tree",
            "rankUnlock",
        ),
        _rule(
            "RANK_UNLOCK_EXCEEDS_AVAILABLE",
            "error",
            "rank_unlock",
            "The requirement exceeds available regular vehicles.",
            "The next rank would be mathematically impossible to unlock.",
            "Two purchases are required but one regular vehicle exists.",
            "research_tree",
            "rankUnlock",
        ),
        _rule(
            "RANK_UNLOCK_MISSING",
            "warning",
            "rank_unlock",
            "A populated higher rank has no positive requirement.",
            "A missing gate may reflect incomplete rank configuration.",
            "Ranks 1 and 2 exist but rank 1 requirement is absent.",
            "research_tree",
            "rankUnlock",
        ),
        _rule(
            "RANK_UNLOCK_ORDER_CONFLICT",
            "error",
            "rank_unlock",
            "A rank unlock key is not numeric.",
            "Non-numeric keys cannot be ordered against vehicle ranks.",
            "rankUnlock uses the key next instead of 1.",
            "research_tree",
            "rankUnlock",
        ),
        _rule(
            "LOCALIZATION_MISSING_NAME",
            "warning",
            "localization",
            "The name field is absent.",
            "A display fallback hides missing localization source data.",
            "Vehicle tank_a has no name key.",
            "vehicle",
            "name",
        ),
        _rule(
            "LOCALIZATION_EMPTY",
            "warning",
            "localization",
            "The localized name is empty.",
            "An empty label is unusable in explanations and UIs.",
            "Vehicle tank_a has name set to an empty string.",
            "vehicle",
            "name",
        ),
        _rule(
            "LOCALIZATION_INTERNAL_ID",
            "warning",
            "localization",
            "The visible name equals the internal ID.",
            "This usually indicates localization fallback rather than a translated name.",
            "Vehicle tank_a is displayed as tank_a.",
            "vehicle",
            "name",
        ),
        _rule(
            "LOCALIZATION_DUPLICATE_NAME",
            "info",
            "localization",
            "A visible name is duplicated in one tree.",
            "Duplicate labels are valid but create ambiguous human output.",
            "Two German tanks are both named Example.",
            "research_tree",
            "name",
        ),
        _rule(
            "SPECIAL_HIDDEN_RESEARCH",
            "info",
            "special_case",
            "A hidden research vehicle is retained.",
            "Hidden legacy content must be explicit rather than silently ignored.",
            "tank_a has hiddenResearch true.",
            "vehicle",
            "hiddenResearch",
        ),
        _rule(
            "SPECIAL_EXTERNAL_UNLOCK",
            "info",
            "special_case",
            "A vehicle has an external unlock condition.",
            "External unlocks require semantics outside the predecessor graph.",
            "tank_a has reqUnlock event_x.",
            "vehicle",
            "reqUnlock",
        ),
        _rule(
            "SPECIAL_RESERVE",
            "info",
            "special_case",
            "A reserve vehicle is retained.",
            "The solver treats reserves as initially available, so the classification is material.",
            "tank_a has reserve true and zero costs.",
            "vehicle",
            "reserve",
        ),
        _rule(
            "SPECIAL_PREMIUM",
            "info",
            "special_case",
            "A premium vehicle is present.",
            "Premium acquisition is outside regular research progression.",
            "tank_a has premium true.",
            "vehicle",
            "premium",
        ),
        _rule(
            "SPECIAL_NON_REGULAR",
            "info",
            "special_case",
            "An event, squadron or legacy vehicle is present.",
            "The current schema merges several non-regular acquisition classes.",
            "tank_a has special true.",
            "vehicle",
            "special",
        ),
    )
}


def discover_tested_rules(paths: Iterable[Path]) -> tuple[str, ...]:
    """Discover rule IDs referenced by executable rule-matrix files."""
    tested: set[str] = set()
    pattern = re.compile(r"[\"']([A-Z][A-Z0-9_]+)[\"']")
    for path in paths:
        if not path.is_file():
            continue
        content = path.read_text(encoding="utf-8")
        tested.update(match for match in pattern.findall(content) if match in RULE_DEFINITIONS)
    return tuple(sorted(tested))


def render_rule_documentation() -> str:
    lines = [
        "# Validator Rule Reference",
        "",
        "Generated from `RULE_DEFINITIONS`; edit the registry, then regenerate this file.",
        "",
    ]
    for rule_id in sorted(RULE_DEFINITIONS):
        rule = RULE_DEFINITIONS[rule_id]
        output = {
            "rule_id": rule.rule_id,
            "severity": rule.severity,
            "message": rule.description,
            "entity_type": rule.entity_type,
            "source_field": rule.source_field,
            "details": {},
        }
        lines.extend(
            [
                f"## {rule.rule_id}",
                "",
                f"- **Severity:** `{rule.severity}`",
                f"- **Category:** `{rule.category}`",
                f"- **Description:** {rule.description}",
                f"- **Rationale:** {rule.rationale}",
                f"- **Example:** {rule.example}",
                "- **Example output:**",
                "",
                "```json",
                json.dumps(output, ensure_ascii=False, indent=2),
                "```",
                "",
            ]
        )
    return "\n".join(lines)
