from __future__ import annotations

import copy
from typing import Any


def vehicle(vehicle_id: str, **overrides: Any) -> dict[str, Any]:
    result = {
        "id": vehicle_id,
        "name": f"Vehicle {vehicle_id}",
        "countryId": "country_test",
        "branchId": "army",
        "rank": 1,
        "rp": 1_000,
        "sl": 2_000,
        "reserve": False,
        "hiddenResearch": False,
        "reqUnlock": "",
        "premium": False,
        "special": False,
        "group": None,
        "groupIndex": 0,
    }
    result.update(overrides)
    return result


def database(*vehicles: dict[str, Any]) -> dict[str, Any]:
    return {
        "schemaVersion": 1,
        "gameVersion": "2.57.1.67",
        "generatedAt": "2026-01-01T00:00:00+00:00",
        "economy": {"rpPerGE": 45},
        "vehicles": list(vehicles),
        "predecessors": {item["id"]: None for item in vehicles if "id" in item},
        "groups": {},
        "rankUnlock": {},
    }


def _copy(value: dict[str, Any]) -> dict[str, Any]:
    return copy.deepcopy(value)


def rule_cases() -> dict[str, tuple[dict[str, Any], dict[str, Any]]]:
    base = database(vehicle("a"))
    two_ranks = database(vehicle("a"), vehicle("b", rank=2))
    matrix: dict[str, tuple[dict[str, Any], dict[str, Any]]] = {}

    bad = _copy(base)
    del bad["vehicles"]
    matrix["SCHEMA_MISSING_FIELD"] = (bad, _copy(base))
    bad = _copy(base)
    bad["groups"] = []
    matrix["SCHEMA_INVALID_TYPE"] = (bad, _copy(base))
    bad = _copy(base)
    bad["schemaVersion"] = 99
    matrix["SCHEMA_INVALID_VERSION"] = (bad, _copy(base))
    bad = _copy(base)
    bad["gameVersion"] = ""
    matrix["GAME_VERSION_MISSING"] = (bad, _copy(base))
    bad = _copy(base)
    bad["gameVersion"] = "unknown"
    matrix["GAME_VERSION_INVALID"] = (bad, _copy(base))
    bad = _copy(base)
    bad["economy"]["rpPerGE"] = 0
    matrix["ECONOMY_INVALID_RP_PER_GE"] = (bad, _copy(base))
    matrix["VEHICLE_DUPLICATE_ID"] = (
        database(vehicle("a"), vehicle("a")),
        _copy(base),
    )
    bad = _copy(base)
    del bad["vehicles"][0]["countryId"]
    matrix["VEHICLE_MISSING_FIELD"] = (bad, _copy(base))
    bad = _copy(base)
    bad["vehicles"][0]["countryId"] = 7
    matrix["VEHICLE_INVALID_FIELD_TYPE"] = (bad, _copy(base))
    bad = _copy(base)
    bad["vehicles"][0]["rank"] = 0
    matrix["RANK_INVALID"] = (bad, _copy(base))
    bad = _copy(base)
    bad["vehicles"][0]["rp"] = "many"
    matrix["COST_NON_NUMERIC"] = (bad, _copy(base))
    bad = _copy(base)
    bad["vehicles"][0]["rp"] = -1
    matrix["COST_NEGATIVE_RP"] = (bad, _copy(base))
    bad = _copy(base)
    bad["vehicles"][0]["sl"] = -1
    matrix["COST_NEGATIVE_SL"] = (bad, _copy(base))
    bad = _copy(base)
    bad["vehicles"][0].update(rp=0, sl=1)
    matrix["COST_ZERO_RP_WITH_SL"] = (bad, _copy(base))
    bad = _copy(base)
    bad["vehicles"][0].update(rp=1, sl=0)
    matrix["COST_ZERO_SL_WITH_RP"] = (bad, _copy(base))

    bad = _copy(two_ranks)
    bad["predecessors"]["b"] = "missing"
    matrix["GRAPH_MISSING_PREDECESSOR"] = (bad, _copy(two_ranks))
    bad = _copy(base)
    bad["predecessors"]["a"] = "a"
    matrix["GRAPH_SELF_REFERENCE"] = (bad, _copy(base))
    bad = _copy(two_ranks)
    bad["predecessors"] = {"a": "b", "b": "a"}
    matrix["GRAPH_CYCLE"] = (bad, _copy(two_ranks))
    bad = database(vehicle("a"), vehicle("b", countryId="country_other"))
    bad["predecessors"]["b"] = "a"
    matrix["GRAPH_CROSS_NATION"] = (bad, _copy(two_ranks))
    bad = database(vehicle("a"), vehicle("b", branchId="aviation"))
    bad["predecessors"]["b"] = "a"
    matrix["GRAPH_CROSS_BRANCH"] = (bad, _copy(two_ranks))
    bad = database(vehicle("a", rank=2), vehicle("b", rank=1))
    bad["predecessors"]["b"] = "a"
    matrix["GRAPH_RANK_BACKWARDS"] = (bad, _copy(two_ranks))
    bad = _copy(base)
    del bad["predecessors"]["a"]
    matrix["GRAPH_UNREACHABLE"] = (bad, _copy(base))
    bad = _copy(two_ranks)
    bad["predecessors"]["b"] = ["a", "missing"]
    matrix["GRAPH_CONFLICTING_PREDECESSORS"] = (bad, _copy(two_ranks))

    bad = _copy(base)
    bad["groups"] = {"g": ["missing"]}
    matrix["GROUP_UNKNOWN_VEHICLE"] = (bad, _copy(base))
    bad = database(vehicle("a", group="g1"))
    bad["groups"] = {"g1": ["a"], "g2": ["a"]}
    good = database(vehicle("a", group="g1"))
    good["groups"] = {"g1": ["a"]}
    matrix["GROUP_CONFLICTING_MEMBERSHIP"] = (bad, good)
    bad = database(vehicle("a", group="g"))
    bad["groups"] = {"g": ["a"]}
    good = database(vehicle("a", group="g", groupIndex=0), vehicle("b", group="g", groupIndex=1))
    good["groups"] = {"g": ["a", "b"]}
    matrix["GROUP_SINGLE_VEHICLE"] = (bad, good)
    bad = database(vehicle("a", group="g", groupIndex=1), vehicle("b", group="g", groupIndex=0))
    bad["groups"] = {"g": ["a", "b"]}
    matrix["GROUP_INDEX_MISMATCH"] = (bad, _copy(good))
    bad = database(
        vehicle("a", group="g"), vehicle("b", group="g", countryId="other", groupIndex=1)
    )
    bad["groups"] = {"g": ["a", "b"]}
    matrix["GROUP_CROSS_TREE"] = (bad, _copy(good))

    bad = _copy(two_ranks)
    bad["rankUnlock"] = {"country_test": {"army": {"1": -1}}}
    good_rank = _copy(two_ranks)
    good_rank["rankUnlock"] = {"country_test": {"army": {"1": 1}}}
    matrix["RANK_UNLOCK_NEGATIVE"] = (bad, _copy(good_rank))
    bad = _copy(two_ranks)
    bad["rankUnlock"] = {"country_test": {"army": {"1": 21}}}
    matrix["RANK_UNLOCK_UNREALISTIC"] = (bad, _copy(good_rank))
    bad = _copy(two_ranks)
    bad["rankUnlock"] = {"country_test": {"army": {"1": 2}}}
    matrix["RANK_UNLOCK_EXCEEDS_AVAILABLE"] = (bad, _copy(good_rank))
    matrix["RANK_UNLOCK_MISSING"] = (_copy(two_ranks), _copy(good_rank))
    bad = _copy(two_ranks)
    bad["rankUnlock"] = {"country_test": {"army": {"next": 1}}}
    matrix["RANK_UNLOCK_ORDER_CONFLICT"] = (bad, _copy(good_rank))

    bad = _copy(base)
    del bad["vehicles"][0]["name"]
    matrix["LOCALIZATION_MISSING_NAME"] = (bad, _copy(base))
    bad = _copy(base)
    bad["vehicles"][0]["name"] = ""
    matrix["LOCALIZATION_EMPTY"] = (bad, _copy(base))
    bad = _copy(base)
    bad["vehicles"][0]["name"] = "a"
    matrix["LOCALIZATION_INTERNAL_ID"] = (bad, _copy(base))
    bad = database(vehicle("a", name="Same"), vehicle("b", name="Same"))
    matrix["LOCALIZATION_DUPLICATE_NAME"] = (bad, _copy(two_ranks))
    for rule_id, field, value in (
        ("SPECIAL_HIDDEN_RESEARCH", "hiddenResearch", True),
        ("SPECIAL_EXTERNAL_UNLOCK", "reqUnlock", "external"),
        ("SPECIAL_RESERVE", "reserve", True),
        ("SPECIAL_PREMIUM", "premium", True),
        ("SPECIAL_NON_REGULAR", "special", True),
    ):
        bad = _copy(base)
        bad["vehicles"][0][field] = value
        if rule_id == "SPECIAL_RESERVE":
            bad["vehicles"][0].update(rp=0, sl=0)
        matrix[rule_id] = (bad, _copy(base))

    return matrix
