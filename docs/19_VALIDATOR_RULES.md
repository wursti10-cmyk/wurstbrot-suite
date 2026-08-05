# Validator Rule Reference

Generated from `RULE_DEFINITIONS`; edit the registry, then regenerate this file.

## COST_NEGATIVE_RP

- **Severity:** `error`
- **Category:** `cost`
- **Description:** RP cost is negative.
- **Rationale:** Negative research cost has no valid calculator meaning.
- **Example:** Vehicle tank_a has rp -1.
- **Example output:**

```json
{
  "rule_id": "COST_NEGATIVE_RP",
  "severity": "error",
  "message": "RP cost is negative.",
  "entity_type": "vehicle",
  "source_field": "rp",
  "details": {}
}
```

## COST_NEGATIVE_SL

- **Severity:** `error`
- **Category:** `cost`
- **Description:** SL cost is negative.
- **Rationale:** Negative purchase cost has no valid calculator meaning.
- **Example:** Vehicle tank_a has sl -1.
- **Example output:**

```json
{
  "rule_id": "COST_NEGATIVE_SL",
  "severity": "error",
  "message": "SL cost is negative.",
  "entity_type": "vehicle",
  "source_field": "sl",
  "details": {}
}
```

## COST_NON_NUMERIC

- **Severity:** `error`
- **Category:** `cost`
- **Description:** RP or SL cost is not an integer.
- **Rationale:** Cost arithmetic must use exact integers.
- **Example:** Vehicle tank_a has rp set to many.
- **Example output:**

```json
{
  "rule_id": "COST_NON_NUMERIC",
  "severity": "error",
  "message": "RP or SL cost is not an integer.",
  "entity_type": "vehicle",
  "source_field": "rp",
  "details": {}
}
```

## COST_ZERO_RP_WITH_SL

- **Severity:** `warning`
- **Category:** `cost`
- **Description:** A vehicle has zero RP and positive SL.
- **Rationale:** This can be intentional but is unusual enough to review.
- **Example:** Vehicle tank_a has rp 0 and sl 1000.
- **Example output:**

```json
{
  "rule_id": "COST_ZERO_RP_WITH_SL",
  "severity": "warning",
  "message": "A vehicle has zero RP and positive SL.",
  "entity_type": "vehicle",
  "source_field": "rp",
  "details": {}
}
```

## COST_ZERO_SL_WITH_RP

- **Severity:** `warning`
- **Category:** `cost`
- **Description:** A vehicle has positive RP and zero SL.
- **Rationale:** This can be intentional but may indicate incomplete economy data.
- **Example:** Vehicle tank_a has rp 1000 and sl 0.
- **Example output:**

```json
{
  "rule_id": "COST_ZERO_SL_WITH_RP",
  "severity": "warning",
  "message": "A vehicle has positive RP and zero SL.",
  "entity_type": "vehicle",
  "source_field": "sl",
  "details": {}
}
```

## ECONOMY_INVALID_RP_PER_GE

- **Severity:** `error`
- **Category:** `economy`
- **Description:** RP per GE is not a positive integer.
- **Rationale:** GE conversion requires an exact positive divisor.
- **Example:** economy.rpPerGE is zero.
- **Example output:**

```json
{
  "rule_id": "ECONOMY_INVALID_RP_PER_GE",
  "severity": "error",
  "message": "RP per GE is not a positive integer.",
  "entity_type": "economy",
  "source_field": "rpPerGE",
  "details": {}
}
```

## GAME_VERSION_INVALID

- **Severity:** `error`
- **Category:** `schema`
- **Description:** The game version is not a dotted version value.
- **Rationale:** Unknown labels cannot identify a reproducible source snapshot.
- **Example:** gameVersion is unbekannt.
- **Example output:**

```json
{
  "rule_id": "GAME_VERSION_INVALID",
  "severity": "error",
  "message": "The game version is not a dotted version value.",
  "entity_type": "database",
  "source_field": "gameVersion",
  "details": {}
}
```

## GAME_VERSION_MISSING

- **Severity:** `error`
- **Category:** `schema`
- **Description:** The game version is absent or empty.
- **Rationale:** Outputs must be traceable to an exact datamine version.
- **Example:** gameVersion is an empty string.
- **Example output:**

```json
{
  "rule_id": "GAME_VERSION_MISSING",
  "severity": "error",
  "message": "The game version is absent or empty.",
  "entity_type": "database",
  "source_field": "gameVersion",
  "details": {}
}
```

## GRAPH_CONFLICTING_PREDECESSORS

- **Severity:** `error`
- **Category:** `graph`
- **Description:** A vehicle defines multiple predecessor candidates.
- **Rationale:** Schema version 1 permits at most one direct predecessor.
- **Example:** predecessors.tank_a is an array of two IDs.
- **Example output:**

```json
{
  "rule_id": "GRAPH_CONFLICTING_PREDECESSORS",
  "severity": "error",
  "message": "A vehicle defines multiple predecessor candidates.",
  "entity_type": "vehicle",
  "source_field": "predecessors",
  "details": {}
}
```

## GRAPH_CROSS_BRANCH

- **Severity:** `error`
- **Category:** `graph`
- **Description:** A predecessor crosses vehicle types.
- **Rationale:** Research prerequisites must stay in one branch tree.
- **Example:** A tank references an aircraft predecessor.
- **Example output:**

```json
{
  "rule_id": "GRAPH_CROSS_BRANCH",
  "severity": "error",
  "message": "A predecessor crosses vehicle types.",
  "entity_type": "vehicle",
  "source_field": "predecessors",
  "details": {}
}
```

## GRAPH_CROSS_NATION

- **Severity:** `error`
- **Category:** `graph`
- **Description:** A predecessor crosses nations.
- **Rationale:** Research prerequisites must stay in one national tree.
- **Example:** A German vehicle references a US predecessor.
- **Example output:**

```json
{
  "rule_id": "GRAPH_CROSS_NATION",
  "severity": "error",
  "message": "A predecessor crosses nations.",
  "entity_type": "vehicle",
  "source_field": "predecessors",
  "details": {}
}
```

## GRAPH_CYCLE

- **Severity:** `error`
- **Category:** `graph`
- **Description:** The predecessor graph contains a cycle.
- **Rationale:** Cyclic prerequisites cannot produce a finite research closure.
- **Example:** tank_a requires tank_b and tank_b requires tank_a.
- **Example output:**

```json
{
  "rule_id": "GRAPH_CYCLE",
  "severity": "error",
  "message": "The predecessor graph contains a cycle.",
  "entity_type": "research_graph",
  "source_field": "predecessors",
  "details": {}
}
```

## GRAPH_MISSING_PREDECESSOR

- **Severity:** `error`
- **Category:** `graph`
- **Description:** A predecessor ID does not exist.
- **Rationale:** A broken prerequisite edge makes the research path incomplete.
- **Example:** tank_b references missing tank_a.
- **Example output:**

```json
{
  "rule_id": "GRAPH_MISSING_PREDECESSOR",
  "severity": "error",
  "message": "A predecessor ID does not exist.",
  "entity_type": "vehicle",
  "source_field": "predecessors",
  "details": {}
}
```

## GRAPH_RANK_BACKWARDS

- **Severity:** `error`
- **Category:** `graph`
- **Description:** A predecessor has a higher rank than its child.
- **Rationale:** A higher-rank prerequisite contradicts progression order.
- **Example:** Rank 2 tank requires a rank 3 tank.
- **Example output:**

```json
{
  "rule_id": "GRAPH_RANK_BACKWARDS",
  "severity": "error",
  "message": "A predecessor has a higher rank than its child.",
  "entity_type": "vehicle",
  "source_field": "predecessors",
  "details": {}
}
```

## GRAPH_SELF_REFERENCE

- **Severity:** `error`
- **Category:** `graph`
- **Description:** A vehicle references itself as predecessor.
- **Rationale:** A self-edge is an immediate cycle.
- **Example:** predecessors.tank_a equals tank_a.
- **Example output:**

```json
{
  "rule_id": "GRAPH_SELF_REFERENCE",
  "severity": "error",
  "message": "A vehicle references itself as predecessor.",
  "entity_type": "vehicle",
  "source_field": "predecessors",
  "details": {}
}
```

## GRAPH_UNREACHABLE

- **Severity:** `warning`
- **Category:** `graph`
- **Description:** A vehicle has no predecessor-map entry.
- **Rationale:** The loader would silently treat it as a new root.
- **Example:** tank_a exists but predecessors has no tank_a key.
- **Example output:**

```json
{
  "rule_id": "GRAPH_UNREACHABLE",
  "severity": "warning",
  "message": "A vehicle has no predecessor-map entry.",
  "entity_type": "vehicle",
  "source_field": "predecessors",
  "details": {}
}
```

## GROUP_CONFLICTING_MEMBERSHIP

- **Severity:** `error`
- **Category:** `folder`
- **Description:** A vehicle appears in multiple folders.
- **Rationale:** One vehicle cannot have two authoritative group positions.
- **Example:** tank_a occurs in group_a and group_b.
- **Example output:**

```json
{
  "rule_id": "GROUP_CONFLICTING_MEMBERSHIP",
  "severity": "error",
  "message": "A vehicle appears in multiple folders.",
  "entity_type": "vehicle",
  "source_field": "group",
  "details": {}
}
```

## GROUP_CROSS_TREE

- **Severity:** `error`
- **Category:** `folder`
- **Description:** A folder spans nations or vehicle types.
- **Rationale:** A research folder must belong to one research tree.
- **Example:** group_a contains a German tank and US tank.
- **Example output:**

```json
{
  "rule_id": "GROUP_CROSS_TREE",
  "severity": "error",
  "message": "A folder spans nations or vehicle types.",
  "entity_type": "group",
  "source_field": "groups",
  "details": {}
}
```

## GROUP_INDEX_MISMATCH

- **Severity:** `warning`
- **Category:** `folder`
- **Description:** Vehicle group metadata disagrees with folder order.
- **Rationale:** Folder order affects sequential prerequisite normalization.
- **Example:** tank_a is first but groupIndex is 1.
- **Example output:**

```json
{
  "rule_id": "GROUP_INDEX_MISMATCH",
  "severity": "warning",
  "message": "Vehicle group metadata disagrees with folder order.",
  "entity_type": "vehicle",
  "source_field": "groupIndex",
  "details": {}
}
```

## GROUP_SINGLE_VEHICLE

- **Severity:** `info`
- **Category:** `folder`
- **Description:** A folder contains one vehicle.
- **Rationale:** Singleton folders are valid but useful migration diagnostics.
- **Example:** group_a contains only tank_a.
- **Example output:**

```json
{
  "rule_id": "GROUP_SINGLE_VEHICLE",
  "severity": "info",
  "message": "A folder contains one vehicle.",
  "entity_type": "group",
  "source_field": "groups",
  "details": {}
}
```

## GROUP_UNKNOWN_VEHICLE

- **Severity:** `warning`
- **Category:** `folder`
- **Description:** A folder references an absent regular vehicle.
- **Rationale:** Filtered special vehicles and truly stale IDs must remain visible for review.
- **Example:** Folder group_a contains missing_vehicle.
- **Example output:**

```json
{
  "rule_id": "GROUP_UNKNOWN_VEHICLE",
  "severity": "warning",
  "message": "A folder references an absent regular vehicle.",
  "entity_type": "group",
  "source_field": "groups",
  "details": {}
}
```

## LOCALIZATION_DUPLICATE_NAME

- **Severity:** `info`
- **Category:** `localization`
- **Description:** A visible name is duplicated in one tree.
- **Rationale:** Duplicate labels are valid but create ambiguous human output.
- **Example:** Two German tanks are both named Example.
- **Example output:**

```json
{
  "rule_id": "LOCALIZATION_DUPLICATE_NAME",
  "severity": "info",
  "message": "A visible name is duplicated in one tree.",
  "entity_type": "research_tree",
  "source_field": "name",
  "details": {}
}
```

## LOCALIZATION_EMPTY

- **Severity:** `warning`
- **Category:** `localization`
- **Description:** The localized name is empty.
- **Rationale:** An empty label is unusable in explanations and UIs.
- **Example:** Vehicle tank_a has name set to an empty string.
- **Example output:**

```json
{
  "rule_id": "LOCALIZATION_EMPTY",
  "severity": "warning",
  "message": "The localized name is empty.",
  "entity_type": "vehicle",
  "source_field": "name",
  "details": {}
}
```

## LOCALIZATION_INTERNAL_ID

- **Severity:** `warning`
- **Category:** `localization`
- **Description:** The visible name equals the internal ID.
- **Rationale:** This usually indicates localization fallback rather than a translated name.
- **Example:** Vehicle tank_a is displayed as tank_a.
- **Example output:**

```json
{
  "rule_id": "LOCALIZATION_INTERNAL_ID",
  "severity": "warning",
  "message": "The visible name equals the internal ID.",
  "entity_type": "vehicle",
  "source_field": "name",
  "details": {}
}
```

## LOCALIZATION_MISSING_NAME

- **Severity:** `warning`
- **Category:** `localization`
- **Description:** The name field is absent.
- **Rationale:** A display fallback hides missing localization source data.
- **Example:** Vehicle tank_a has no name key.
- **Example output:**

```json
{
  "rule_id": "LOCALIZATION_MISSING_NAME",
  "severity": "warning",
  "message": "The name field is absent.",
  "entity_type": "vehicle",
  "source_field": "name",
  "details": {}
}
```

## RANK_INVALID

- **Severity:** `error`
- **Category:** `rank`
- **Description:** A vehicle rank is not a positive integer.
- **Rationale:** Research order requires an exact ordinal rank.
- **Example:** Vehicle tank_a has rank 0.
- **Example output:**

```json
{
  "rule_id": "RANK_INVALID",
  "severity": "error",
  "message": "A vehicle rank is not a positive integer.",
  "entity_type": "vehicle",
  "source_field": "rank",
  "details": {}
}
```

## RANK_UNLOCK_EXCEEDS_AVAILABLE

- **Severity:** `error`
- **Category:** `rank_unlock`
- **Description:** The requirement exceeds available regular vehicles.
- **Rationale:** The next rank would be mathematically impossible to unlock.
- **Example:** Two purchases are required but one regular vehicle exists.
- **Example output:**

```json
{
  "rule_id": "RANK_UNLOCK_EXCEEDS_AVAILABLE",
  "severity": "error",
  "message": "The requirement exceeds available regular vehicles.",
  "entity_type": "research_tree",
  "source_field": "rankUnlock",
  "details": {}
}
```

## RANK_UNLOCK_MISSING

- **Severity:** `warning`
- **Category:** `rank_unlock`
- **Description:** A populated higher rank has no positive requirement.
- **Rationale:** A missing gate may reflect incomplete rank configuration.
- **Example:** Ranks 1 and 2 exist but rank 1 requirement is absent.
- **Example output:**

```json
{
  "rule_id": "RANK_UNLOCK_MISSING",
  "severity": "warning",
  "message": "A populated higher rank has no positive requirement.",
  "entity_type": "research_tree",
  "source_field": "rankUnlock",
  "details": {}
}
```

## RANK_UNLOCK_NEGATIVE

- **Severity:** `error`
- **Category:** `rank_unlock`
- **Description:** A rank unlock requirement is negative.
- **Rationale:** Negative purchase counts have no valid progression meaning.
- **Example:** Rank 1 requires -1 purchases.
- **Example output:**

```json
{
  "rule_id": "RANK_UNLOCK_NEGATIVE",
  "severity": "error",
  "message": "A rank unlock requirement is negative.",
  "entity_type": "research_tree",
  "source_field": "rankUnlock",
  "details": {}
}
```

## RANK_UNLOCK_ORDER_CONFLICT

- **Severity:** `error`
- **Category:** `rank_unlock`
- **Description:** A rank unlock key is not numeric.
- **Rationale:** Non-numeric keys cannot be ordered against vehicle ranks.
- **Example:** rankUnlock uses the key next instead of 1.
- **Example output:**

```json
{
  "rule_id": "RANK_UNLOCK_ORDER_CONFLICT",
  "severity": "error",
  "message": "A rank unlock key is not numeric.",
  "entity_type": "research_tree",
  "source_field": "rankUnlock",
  "details": {}
}
```

## RANK_UNLOCK_UNREALISTIC

- **Severity:** `warning`
- **Category:** `rank_unlock`
- **Description:** A rank unlock requirement exceeds the diagnostic threshold.
- **Rationale:** Values above 20 warrant review without claiming a game rule.
- **Example:** Rank 1 requires 21 purchases.
- **Example output:**

```json
{
  "rule_id": "RANK_UNLOCK_UNREALISTIC",
  "severity": "warning",
  "message": "A rank unlock requirement exceeds the diagnostic threshold.",
  "entity_type": "research_tree",
  "source_field": "rankUnlock",
  "details": {}
}
```

## SCHEMA_INVALID_TYPE

- **Severity:** `error`
- **Category:** `schema`
- **Description:** A structural field has the wrong JSON type.
- **Rationale:** Wrong container types make traversal ambiguous or unsafe.
- **Example:** groups is an array instead of an object.
- **Example output:**

```json
{
  "rule_id": "SCHEMA_INVALID_TYPE",
  "severity": "error",
  "message": "A structural field has the wrong JSON type.",
  "entity_type": "database",
  "source_field": "groups",
  "details": {}
}
```

## SCHEMA_INVALID_VERSION

- **Severity:** `error`
- **Category:** `schema`
- **Description:** The database schema version is unsupported.
- **Rationale:** Readers only implement the declared schema contract.
- **Example:** schemaVersion is 2 while only version 1 is supported.
- **Example output:**

```json
{
  "rule_id": "SCHEMA_INVALID_VERSION",
  "severity": "error",
  "message": "The database schema version is unsupported.",
  "entity_type": "database",
  "source_field": "schemaVersion",
  "details": {}
}
```

## SCHEMA_MISSING_FIELD

- **Severity:** `error`
- **Category:** `schema`
- **Description:** A required root field is missing.
- **Rationale:** Consumers cannot interpret an incomplete root object safely.
- **Example:** The database has no vehicles field.
- **Example output:**

```json
{
  "rule_id": "SCHEMA_MISSING_FIELD",
  "severity": "error",
  "message": "A required root field is missing.",
  "entity_type": "database",
  "source_field": "vehicles",
  "details": {}
}
```

## SPECIAL_EXTERNAL_UNLOCK

- **Severity:** `info`
- **Category:** `special_case`
- **Description:** A vehicle has an external unlock condition.
- **Rationale:** External unlocks require semantics outside the predecessor graph.
- **Example:** tank_a has reqUnlock event_x.
- **Example output:**

```json
{
  "rule_id": "SPECIAL_EXTERNAL_UNLOCK",
  "severity": "info",
  "message": "A vehicle has an external unlock condition.",
  "entity_type": "vehicle",
  "source_field": "reqUnlock",
  "details": {}
}
```

## SPECIAL_HIDDEN_RESEARCH

- **Severity:** `info`
- **Category:** `special_case`
- **Description:** A hidden research vehicle is retained.
- **Rationale:** Hidden legacy content must be explicit rather than silently ignored.
- **Example:** tank_a has hiddenResearch true.
- **Example output:**

```json
{
  "rule_id": "SPECIAL_HIDDEN_RESEARCH",
  "severity": "info",
  "message": "A hidden research vehicle is retained.",
  "entity_type": "vehicle",
  "source_field": "hiddenResearch",
  "details": {}
}
```

## SPECIAL_NON_REGULAR

- **Severity:** `info`
- **Category:** `special_case`
- **Description:** An event, squadron or legacy vehicle is present.
- **Rationale:** The current schema merges several non-regular acquisition classes.
- **Example:** tank_a has special true.
- **Example output:**

```json
{
  "rule_id": "SPECIAL_NON_REGULAR",
  "severity": "info",
  "message": "An event, squadron or legacy vehicle is present.",
  "entity_type": "vehicle",
  "source_field": "special",
  "details": {}
}
```

## SPECIAL_PREMIUM

- **Severity:** `info`
- **Category:** `special_case`
- **Description:** A premium vehicle is present.
- **Rationale:** Premium acquisition is outside regular research progression.
- **Example:** tank_a has premium true.
- **Example output:**

```json
{
  "rule_id": "SPECIAL_PREMIUM",
  "severity": "info",
  "message": "A premium vehicle is present.",
  "entity_type": "vehicle",
  "source_field": "premium",
  "details": {}
}
```

## SPECIAL_RESERVE

- **Severity:** `info`
- **Category:** `special_case`
- **Description:** A reserve vehicle is retained.
- **Rationale:** The solver treats reserves as initially available, so the classification is material.
- **Example:** tank_a has reserve true and zero costs.
- **Example output:**

```json
{
  "rule_id": "SPECIAL_RESERVE",
  "severity": "info",
  "message": "A reserve vehicle is retained.",
  "entity_type": "vehicle",
  "source_field": "reserve",
  "details": {}
}
```

## VEHICLE_DUPLICATE_ID

- **Severity:** `error`
- **Category:** `identity`
- **Description:** A vehicle ID occurs more than once.
- **Rationale:** IDs are primary keys throughout graph and progress data.
- **Example:** Two vehicle objects use the ID tank_a.
- **Example output:**

```json
{
  "rule_id": "VEHICLE_DUPLICATE_ID",
  "severity": "error",
  "message": "A vehicle ID occurs more than once.",
  "entity_type": "vehicle",
  "source_field": "id",
  "details": {}
}
```

## VEHICLE_INVALID_FIELD_TYPE

- **Severity:** `error`
- **Category:** `schema`
- **Description:** A vehicle or unlock field has the wrong type.
- **Rationale:** Implicit coercion can hide datamine format changes.
- **Example:** Vehicle rank is the string two.
- **Example output:**

```json
{
  "rule_id": "VEHICLE_INVALID_FIELD_TYPE",
  "severity": "error",
  "message": "A vehicle or unlock field has the wrong type.",
  "entity_type": "vehicle",
  "source_field": "rank",
  "details": {}
}
```

## VEHICLE_MISSING_FIELD

- **Severity:** `error`
- **Category:** `schema`
- **Description:** A required vehicle field is missing.
- **Rationale:** Core calculations require identity, tree, rank and costs.
- **Example:** Vehicle tank_a has no countryId.
- **Example output:**

```json
{
  "rule_id": "VEHICLE_MISSING_FIELD",
  "severity": "error",
  "message": "A required vehicle field is missing.",
  "entity_type": "vehicle",
  "source_field": "countryId",
  "details": {}
}
```
