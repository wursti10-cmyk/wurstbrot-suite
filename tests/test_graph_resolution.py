from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "core"))

from wurstbrot_core import (  # noqa: E402
    GraphEdge,
    GraphPrerequisiteResolver,
    LegacyRankCompatibilityStrategy,
    NodeType,
    PlayerProgress,
    PrerequisiteResolution,
    RankCompatibilitySelection,
    ResearchGraph,
    ResearchGraphBuilder,
    ResolutionStatus,
    ShadowCase,
    SolveOptions,
    VehicleDatabase,
    VehicleProgress,
    build_player_progress_scenarios,
    build_resolution_special_case_matrix,
    render_resolution_special_case_markdown,
    run_shadow_comparison,
)
from wurstbrot_core.research_graph import EdgeType, GraphNode  # noqa: E402


def vehicle(vehicle_id: str, **overrides):
    result = {
        "id": vehicle_id,
        "name": vehicle_id,
        "countryId": "country_test",
        "branchId": "army",
        "rank": 1,
        "rp": 1_000,
        "sl": 2_000,
        "reserve": False,
        "premium": False,
        "special": False,
        "hiddenResearch": False,
        "reqUnlock": "",
        "group": None,
        "groupIndex": 0,
        "column": 0,
        "order": 0,
    }
    result.update(overrides)
    return result


def database(*vehicles, predecessors=None, groups=None, rank_unlock=None):
    raw = {
        "schemaVersion": 1,
        "gameVersion": "test",
        "economy": {"rpPerGE": 45},
        "vehicles": list(vehicles),
        "predecessors": (
            predecessors if predecessors is not None else {item["id"]: None for item in vehicles}
        ),
        "groups": groups or {},
        "rankUnlock": rank_unlock or {},
    }
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "db.json"
        path.write_text(json.dumps(raw), encoding="utf-8")
        return VehicleDatabase.from_json(path)


def resolver(db: VehicleDatabase, *, compatibility: bool = False):
    graph = ResearchGraphBuilder.from_database(db)
    strategy = LegacyRankCompatibilityStrategy(db) if compatibility else None
    return GraphPrerequisiteResolver(graph, rank_compatibility_strategy=strategy)


class GraphResolutionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sample_database = VehicleDatabase.from_json(
            ROOT / "data" / "samples" / "WT_Database_2.57.1.67.json"
        )
        cls.sample_graph = ResearchGraphBuilder.from_database(cls.sample_database)

    def test_resolution_contract_is_deterministic_and_json_serializable(self):
        db = database(
            vehicle("a", column=2),
            vehicle("b", rank=2, column=1),
            predecessors={"a": None, "b": "a"},
        )
        engine = resolver(db)
        first = engine.resolve(target_vehicle_id="b").to_dict()
        second = engine.resolve(target_vehicle_id="b").to_dict()
        self.assertEqual(first, second)
        json.dumps(first)
        self.assertEqual(
            set(first),
            {
                "target_vehicle_id",
                "start_vehicle_id",
                "required_vehicle_ids",
                "satisfied_vehicle_ids",
                "blocking_rule_results",
                "unresolved_rule_results",
                "rank_requirements",
                "folder_requirements",
                "unlock_requirements",
                "resolution_status",
                "evidence",
                "explanation_trace",
                "compatibility_mode",
            },
        )
        self.assertEqual(first["required_vehicle_ids"], ["a", "b"])
        self.assertEqual(first["resolution_status"], "resolved")
        self.assertFalse(first["evidence"]["graphCostCalculationPerformed"])
        self.assertFalse(first["evidence"]["costValuesEmitted"])
        self.assertFalse(first["evidence"]["optimizerSelectionPerformed"])
        self.assertFalse(first["evidence"]["legacyCompatibilityModeEnabled"])
        self.assertFalse({"rp", "ge", "sl", "euro"} & set(first))

    def test_linear_predecessors_start_and_progress_are_resolved(self):
        db = database(
            vehicle("root", reserve=True),
            vehicle("a"),
            vehicle("b", rank=2),
            predecessors={"root": None, "a": "root", "b": "a"},
        )
        engine = resolver(db)
        baseline = engine.resolve(target_vehicle_id="b")
        self.assertEqual(baseline.required_vehicle_ids, ("a", "root", "b"))
        self.assertFalse(
            set(baseline.required_vehicle_ids) & set(baseline.satisfied_vehicle_ids)
        )

        started = engine.resolve(target_vehicle_id="b", start_vehicle_id="a")
        self.assertEqual(started.required_vehicle_ids, ("b",))
        self.assertIn("a", started.satisfied_vehicle_ids)

        include_start = engine.resolve(
            target_vehicle_id="b",
            start_vehicle_id="a",
            options=SolveOptions(include_start_vehicle=True),
        )
        self.assertEqual(include_start.required_vehicle_ids, ("a", "b"))

        researched_only = engine.resolve(
            target_vehicle_id="b",
            progress=PlayerProgress(
                vehicles={"a": VehicleProgress(researched=True, purchased=False)}
            ),
        )
        self.assertIn("a", researched_only.required_vehicle_ids)

        owned = engine.resolve(
            target_vehicle_id="b",
            progress=PlayerProgress(
                vehicles={"a": VehicleProgress(researched=True, purchased=True)}
            ),
        )
        self.assertEqual(owned.required_vehicle_ids, ("b",))
        self.assertIn("a", owned.satisfied_vehicle_ids)

        partial_target = engine.resolve(
            target_vehicle_id="b",
            progress=PlayerProgress(vehicles={"b": VehicleProgress(researched_rp=500)}),
        )
        self.assertIn("b", partial_target.required_vehicle_ids)

    def test_folder_resolution_distinguishes_membership_required_and_ambiguity(self):
        db = database(
            vehicle("a", group="g", groupIndex=0),
            vehicle("b", group="g", groupIndex=1),
            predecessors={"a": None, "b": "a"},
            groups={"g": ["a", "b"]},
        )
        result = resolver(db).resolve(target_vehicle_id="b")
        by_vehicle = {item.vehicle_id: item for item in result.folder_requirements}
        self.assertEqual(by_vehicle["a"].relationship, "required_member")
        self.assertEqual(by_vehicle["b"].relationship, "membership_only")

        owned = resolver(db).resolve(
            target_vehicle_id="b",
            progress=PlayerProgress(
                vehicles={"a": VehicleProgress(researched=True, purchased=True)}
            ),
        )
        self.assertEqual(
            {item.vehicle_id: item.relationship for item in owned.folder_requirements}["a"],
            "satisfied_member",
        )

        ambiguous_db = database(
            vehicle("a", group="g", groupIndex=1),
            groups={"g": ["a", "missing"]},
        )
        ambiguous = resolver(ambiguous_db).resolve(target_vehicle_id="a")
        self.assertEqual(ambiguous.resolution_status, ResolutionStatus.UNRESOLVED)
        self.assertTrue(ambiguous.unresolved_rule_results)

    def test_unlock_resolution_requires_explicit_evidence(self):
        internal = database(
            vehicle("key"),
            vehicle("target", reqUnlock="vehicle:key"),
        )
        required = resolver(internal).resolve(target_vehicle_id="target")
        self.assertEqual(required.resolution_status, ResolutionStatus.RESOLVED)
        self.assertIn("key", required.required_vehicle_ids)
        self.assertEqual(required.unlock_requirements[0].classification, "internally_resolvable")

        fulfilled = resolver(internal).resolve(
            target_vehicle_id="target",
            progress=PlayerProgress(
                vehicles={"key": VehicleProgress(researched=True, purchased=True)}
            ),
        )
        self.assertNotIn("key", fulfilled.required_vehicle_ids)

        fulfilled_by_start = resolver(internal).resolve(
            target_vehicle_id="target",
            start_vehicle_id="key",
        )
        self.assertEqual(fulfilled_by_start.resolution_status, ResolutionStatus.RESOLVED)
        self.assertEqual(fulfilled_by_start.unlock_requirements[0].status, "satisfied")

        external = database(vehicle("target", reqUnlock="ch_heli_unlocked_test"))
        unresolved = resolver(external).resolve(target_vehicle_id="target")
        self.assertEqual(unresolved.resolution_status, ResolutionStatus.UNRESOLVED)

        assumed = resolver(external).resolve(
            target_vehicle_id="target",
            options=SolveOptions(assume_external_unlocks=True),
        )
        self.assertEqual(assumed.resolution_status, ResolutionStatus.RESOLVED)
        self.assertEqual(
            assumed.unlock_requirements[0].classification,
            "external_assumed_satisfied",
        )

        progress_fulfilled = resolver(external).resolve(
            target_vehicle_id="target",
            progress=PlayerProgress(fulfilled_unlocks=frozenset({"ch_heli_unlocked_test"})),
        )
        self.assertEqual(progress_fulfilled.resolution_status, ResolutionStatus.RESOLVED)
        self.assertEqual(
            progress_fulfilled.unlock_requirements[0].classification,
            "fulfilled_by_progress",
        )

        already_owned = resolver(external).resolve(
            target_vehicle_id="target",
            progress=PlayerProgress(
                vehicles={"target": VehicleProgress(researched=True, purchased=True)}
            ),
        )
        self.assertEqual(already_owned.resolution_status, ResolutionStatus.RESOLVED)
        self.assertEqual(
            already_owned.unlock_requirements[0].classification,
            "fulfilled_by_progress",
        )

    def test_fulfilled_folder_member_does_not_reopen_ambiguous_membership(self):
        db = database(
            vehicle("a", group="g", groupIndex=1),
            vehicle("target", rank=2),
            predecessors={"a": None, "target": "a"},
            groups={"g": ["a", "missing"]},
        )
        result = resolver(db).resolve(target_vehicle_id="target", start_vehicle_id="a")
        self.assertEqual(result.resolution_status, ResolutionStatus.RESOLVED)
        self.assertEqual(result.folder_requirements[0].relationship, "satisfied_member")
        self.assertEqual(result.folder_requirements[0].status, "satisfied")

    def test_multiple_predecessors_and_unknown_target_propagate_status(self):
        graph = ResearchGraph(
            game_version="future",
            nodes=[
                GraphNode("vehicle:a", NodeType.VEHICLE, "a"),
                GraphNode("vehicle:b", NodeType.VEHICLE, "b"),
                GraphNode("vehicle:c", NodeType.VEHICLE, "c"),
            ],
            edges=[
                GraphEdge("vehicle:a", "vehicle:c", EdgeType.PREDECESSOR),
                GraphEdge("vehicle:b", "vehicle:c", EdgeType.PREDECESSOR),
            ],
        )
        unresolved = GraphPrerequisiteResolver(graph).resolve(target_vehicle_id="c")
        self.assertEqual(unresolved.resolution_status, ResolutionStatus.UNRESOLVED)
        self.assertTrue(unresolved.unresolved_rule_results)
        self.assertTrue(unresolved.blocking_rule_results)

        unsupported = GraphPrerequisiteResolver(graph).resolve(target_vehicle_id="missing")
        self.assertEqual(unsupported.resolution_status, ResolutionStatus.UNSUPPORTED)
        self.assertTrue(unsupported.explanation_trace)

        hidden_db = database(vehicle("hidden", hiddenResearch=True))
        blocked = resolver(hidden_db).resolve(target_vehicle_id="hidden")
        self.assertEqual(blocked.resolution_status, ResolutionStatus.BLOCKED)
        self.assertTrue(blocked.blocking_rule_results)

    def test_rank_resolution_explains_without_selecting_and_compatibility_selects(self):
        db = database(
            vehicle("a", reserve=True, rp=0),
            vehicle("candidate", column=1),
            vehicle("other", column=2),
            vehicle("target", rank=2),
            rank_unlock={"country_test": {"army": {"1": 2}}},
        )
        unresolved = resolver(db).resolve(target_vehicle_id="target")
        self.assertEqual(unresolved.resolution_status, ResolutionStatus.UNRESOLVED)
        rank = unresolved.rank_requirements[0]
        self.assertEqual(rank.required_count, 2)
        self.assertEqual(rank.satisfied_count, 1)
        self.assertEqual(rank.missing_count, 1)
        self.assertEqual(rank.candidate_vehicle_ids, ("candidate", "other"))
        self.assertFalse(rank.compatibility_mode)

        compatible = resolver(db, compatibility=True).resolve(target_vehicle_id="target")
        self.assertEqual(compatible.resolution_status, ResolutionStatus.RESOLVED)
        self.assertTrue(compatible.compatibility_mode)
        self.assertEqual(compatible.rank_requirements[0].missing_count, 0)
        self.assertTrue(compatible.rank_requirements[0].selected_vehicle_ids)

    def test_rank_candidate_accepts_explicitly_fulfilled_unlock_token(self):
        db = database(
            vehicle("reserve", reserve=True),
            vehicle("locked", reqUnlock="ch_heli_unlocked_test"),
            vehicle("target", rank=2),
            rank_unlock={"country_test": {"army": {"1": 2}}},
        )
        without_evidence = resolver(db).resolve(target_vehicle_id="target")
        self.assertNotIn(
            "locked", without_evidence.rank_requirements[0].candidate_vehicle_ids
        )
        with_evidence = resolver(db).resolve(
            target_vehicle_id="target",
            progress=PlayerProgress(
                fulfilled_unlocks=frozenset({"ch_heli_unlocked_test"})
            ),
        )
        self.assertIn("locked", with_evidence.rank_requirements[0].candidate_vehicle_ids)

    def test_rank_candidate_explains_unresolved_prerequisite_closure(self):
        db = database(
            vehicle("reserve", reserve=True),
            vehicle("locked", reqUnlock="ch_heli_unlocked_test"),
            vehicle("candidate"),
            vehicle("target", rank=2),
            predecessors={
                "reserve": None,
                "locked": None,
                "candidate": "locked",
                "target": None,
            },
            rank_unlock={"country_test": {"army": {"1": 3}}},
        )
        without_evidence = resolver(db).resolve(target_vehicle_id="target")
        rank = without_evidence.rank_requirements[0]
        self.assertNotIn("candidate", rank.candidate_vehicle_ids)
        self.assertIn(
            {"vehicle_id": "candidate", "reason": "predecessor_reqUnlock_unresolved"},
            rank.excluded_candidates,
        )

        with_evidence = resolver(db).resolve(
            target_vehicle_id="target",
            progress=PlayerProgress(
                fulfilled_unlocks=frozenset({"ch_heli_unlocked_test"})
            ),
        )
        self.assertIn(
            "candidate", with_evidence.rank_requirements[0].candidate_vehicle_ids
        )

    def test_shadow_comparison_has_reproducible_mismatch_diagnostics(self):
        db = database(
            vehicle("cheap", rp=1, column=1),
            vehicle("expensive", rp=9_000, column=2),
            vehicle("target", rank=2),
            rank_unlock={"country_test": {"army": {"1": 1}}},
        )

        class WrongCompatibility:
            mode_name = "test_wrong_compatibility"

            def select(self, **_kwargs):
                return RankCompatibilitySelection(
                    selected_vehicle_ids=("expensive",),
                    selection_reason="intentional test divergence",
                )

            def sort_vehicle_ids(self, vehicle_ids):
                return tuple(sorted(vehicle_ids))

        graph = ResearchGraphBuilder.from_database(db)
        summary = run_shadow_comparison(
            db,
            graph,
            (
                ShadowCase(
                    scenario_id="intentional_mismatch",
                    target_vehicle_id="target",
                ),
            ),
            rank_compatibility_strategy=WrongCompatibility(),
        )
        self.assertEqual(summary.mismatch, 1)
        detail = summary.details[0].to_dict()
        for key in (
            "target_vehicle_id",
            "start_vehicle_id",
            "player_progress_scenario",
            "legacy_vehicle_ids",
            "graph_vehicle_ids",
            "only_legacy",
            "only_graph",
            "divergent_rules",
            "evidence",
            "explanation_trace",
        ):
            self.assertIn(key, detail)
        self.assertEqual(detail, summary.details[0].to_dict())

    def test_equivalent_match_is_only_used_for_equal_vehicle_sets(self):
        db = database(
            vehicle("a"),
            vehicle("b"),
            predecessors={"a": None, "b": "a"},
        )

        class ReverseRepresentation:
            mode_name = "test_reverse_representation"

            def select(self, **_kwargs):
                return RankCompatibilitySelection((), "No rank selection needed.")

            def sort_vehicle_ids(self, vehicle_ids):
                return tuple(sorted(set(vehicle_ids), reverse=True))

        summary = run_shadow_comparison(
            db,
            ResearchGraphBuilder.from_database(db),
            (ShadowCase("representation_only", "b"),),
            rank_compatibility_strategy=ReverseRepresentation(),
        )
        self.assertEqual(summary.equivalent_match, 1)
        self.assertEqual(summary.mismatch, 0)
        detail = summary.details[0]
        self.assertEqual(set(detail.legacy_vehicle_ids), set(detail.graph_vehicle_ids))

    def test_player_progress_matrix_and_special_matrix_are_deterministic(self):
        first = build_player_progress_scenarios(self.sample_database)
        second = build_player_progress_scenarios(self.sample_database)
        self.assertEqual(first, second)
        self.assertEqual(len(first), 13)
        self.assertEqual(
            {item.scenario_id for item in first},
            {
                "no_progress",
                "start_vehicle_owned",
                "start_researched_not_purchased",
                "target_partially_researched",
                "single_predecessor_owned",
                "multiple_progress_vehicles_owned",
                "rank_satisfied",
                "rank_partial",
                "folder_member_owned",
                "hidden_allowed",
                "hidden_disallowed",
                "external_unlock_assumed",
                "external_unlock_not_assumed",
            },
        )

        progress_summary = run_shadow_comparison(
            self.sample_database,
            self.sample_graph,
            first,
            rank_compatibility_strategy=LegacyRankCompatibilityStrategy(self.sample_database),
        )
        self.assertEqual(progress_summary.scenario_count, 13)
        self.assertEqual(progress_summary.mismatch, 0)
        self.assertEqual(
            progress_summary.exact_match
            + progress_summary.equivalent_match
            + progress_summary.unresolved_expected
            + progress_summary.unsupported,
            13,
        )

        matrix = build_resolution_special_case_matrix(
            self.sample_database,
            self.sample_graph,
            rank_compatibility_strategy=LegacyRankCompatibilityStrategy(self.sample_database),
        )
        self.assertEqual(matrix, build_resolution_special_case_matrix(
            self.sample_database,
            self.sample_graph,
            rank_compatibility_strategy=LegacyRankCompatibilityStrategy(self.sample_database),
        ))
        self.assertEqual(len(matrix.rows), 49)
        self.assertEqual(matrix.previous_resolved, 0)
        self.assertEqual(
            matrix.current_resolved
            + matrix.unresolved
            + matrix.unsupported
            + matrix.mismatch,
            49,
        )
        self.assertEqual(matrix.mismatch, 0)
        self.assertTrue(
            all(
                "FOLDER_MEMBERSHIP" in row["reason"]
                for row in matrix.rows
                if row["currentCategory"] == "unresolved_expected"
            )
        )
        committed = (
            ROOT / "docs" / "24_GRAPH_RESOLUTION_SPECIAL_CASE_MATRIX.md"
        ).read_text(encoding="utf-8")
        self.assertEqual(committed, render_resolution_special_case_markdown(matrix))


if __name__ == "__main__":
    unittest.main()
