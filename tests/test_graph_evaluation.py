from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "core"))

from wurstbrot_core import (
    EDGE_SEMANTICS,
    EdgeType,
    EvaluationStatus,
    GraphEdge,
    GraphNode,
    GraphRuleEvaluator,
    NodeType,
    PlayerProgress,
    ResearchGraph,
    ResearchGraphBuilder,
    SolveOptions,
    UnlockClassification,
    VehicleDatabase,
    VehicleProgress,
    build_special_case_matrix,
    render_special_case_matrix_markdown,
    run_mirror_evaluation,
)


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
    }
    result.update(overrides)
    return result


def database(
    *vehicles,
    predecessors=None,
    groups=None,
    rank_unlock=None,
) -> VehicleDatabase:
    raw = {
        "schemaVersion": 1,
        "gameVersion": "2.57.1.67",
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


class GraphEvaluationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sample_database = VehicleDatabase.from_json(
            ROOT / "data" / "samples" / "WT_Database_2.57.1.67.json"
        )
        cls.sample_graph = ResearchGraphBuilder.from_database(cls.sample_database)

    def test_every_edge_type_has_complete_semantics(self):
        self.assertEqual(set(EDGE_SEMANTICS), set(EdgeType))
        for edge_type, semantics in EDGE_SEMANTICS.items():
            with self.subTest(edge_type=edge_type):
                payload = semantics.to_dict()
                self.assertEqual(payload["edgeType"], edge_type.value)
                for value in payload.values():
                    self.assertTrue(value)

    def test_predecessor_statuses_and_start_vehicle(self):
        db = database(
            vehicle("a"),
            vehicle("b", rank=2),
            predecessors={"a": None, "b": "a"},
        )
        evaluator = GraphRuleEvaluator(ResearchGraphBuilder.from_database(db))
        unsatisfied = evaluator.evaluate(target_vehicle_id="b")
        self.assertEqual(
            unsatisfied.by_rule("PREDECESSOR_REQUIREMENTS").status,
            EvaluationStatus.UNSATISFIED,
        )
        owned = evaluator.evaluate(
            target_vehicle_id="b",
            progress=PlayerProgress(
                vehicles={"a": VehicleProgress(researched=True, purchased=True)}
            ),
        )
        self.assertEqual(
            owned.by_rule("PREDECESSOR_REQUIREMENTS").status,
            EvaluationStatus.SATISFIED,
        )
        started = evaluator.evaluate(target_vehicle_id="b", start_vehicle_id="a")
        self.assertEqual(
            started.by_rule("PREDECESSOR_REQUIREMENTS").evidence["requiredVehicleIds"],
            ["b"],
        )
        root = evaluator.evaluate(target_vehicle_id="a")
        self.assertEqual(
            root.by_rule("PREDECESSOR_REQUIREMENTS").status,
            EvaluationStatus.NOT_APPLICABLE,
        )

    def test_start_vehicle_in_different_tree_is_unsatisfied(self):
        db = database(
            vehicle("a", countryId="country_other"),
            vehicle("b"),
        )
        rule = GraphRuleEvaluator(ResearchGraphBuilder.from_database(db)).evaluate(
            target_vehicle_id="b", start_vehicle_id="a"
        ).by_rule("START_TREE_COMPATIBILITY")
        self.assertEqual(rule.status, EvaluationStatus.UNSATISFIED)
        self.assertTrue(rule.blocking)

    def test_multiple_predecessors_are_unresolved_with_all_edges(self):
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
        rule = (
            GraphRuleEvaluator(graph)
            .evaluate(target_vehicle_id="c")
            .by_rule("PREDECESSOR_REQUIREMENTS")
        )
        self.assertEqual(rule.status, EvaluationStatus.UNRESOLVED)
        self.assertEqual(len(rule.source_edge_ids), 2)
        self.assertTrue(rule.blocking)

    def test_folder_regular_single_owned_hidden_missing_and_order(self):
        cases = [
            (
                "regular",
                database(
                    vehicle("a", group="g", groupIndex=0),
                    vehicle("b", group="g", groupIndex=1),
                    groups={"g": ["a", "b"]},
                ),
                "a",
                EvaluationStatus.SATISFIED,
            ),
            (
                "single",
                database(vehicle("a", group="g"), groups={"g": ["a"]}),
                "a",
                EvaluationStatus.SATISFIED,
            ),
            (
                "missing",
                database(vehicle("a", group="g"), groups={"g": ["a", "missing"]}),
                "a",
                EvaluationStatus.UNRESOLVED,
            ),
            (
                "hidden",
                database(
                    vehicle("a", group="g", hiddenResearch=True),
                    groups={"g": ["a"]},
                ),
                "a",
                EvaluationStatus.UNRESOLVED,
            ),
            (
                "order",
                database(
                    vehicle("a", group="g", groupIndex=1),
                    groups={"g": ["a"]},
                ),
                "a",
                EvaluationStatus.UNRESOLVED,
            ),
        ]
        for name, db, target, expected in cases:
            with self.subTest(name=name):
                rule = (
                    GraphRuleEvaluator(ResearchGraphBuilder.from_database(db))
                    .evaluate(target_vehicle_id=target)
                    .by_rule("FOLDER_MEMBERSHIP")
                )
                self.assertEqual(rule.status, expected)
        owned_db = database(vehicle("a", group="g"), groups={"g": ["a"]})
        owned_rule = (
            GraphRuleEvaluator(ResearchGraphBuilder.from_database(owned_db))
            .evaluate(
                target_vehicle_id="a",
                progress=PlayerProgress(
                    vehicles={"a": VehicleProgress(researched=True, purchased=True)}
                ),
            )
            .by_rule("FOLDER_MEMBERSHIP")
        )
        self.assertTrue(owned_rule.evidence["owned"])

    def test_unlock_classifications(self):
        internal_db = database(
            vehicle("a"),
            vehicle("b", reqUnlock="vehicle:a"),
        )
        evaluator = GraphRuleEvaluator(ResearchGraphBuilder.from_database(internal_db))
        internal = evaluator.evaluate(target_vehicle_id="b").by_rule("UNLOCK_REQUIREMENT")
        self.assertEqual(
            internal.evidence["classification"],
            UnlockClassification.INTERNALLY_RESOLVABLE.value,
        )
        self.assertEqual(internal.status, EvaluationStatus.UNSATISFIED)

        external_db = database(vehicle("a", reqUnlock="ch_heli_unlocked_test"))
        external_evaluator = GraphRuleEvaluator(ResearchGraphBuilder.from_database(external_db))
        unresolved = external_evaluator.evaluate(target_vehicle_id="a").by_rule(
            "UNLOCK_REQUIREMENT"
        )
        self.assertEqual(
            unresolved.evidence["classification"],
            UnlockClassification.EXTERNAL_NOT_CHECKABLE.value,
        )
        assumed = external_evaluator.evaluate(
            target_vehicle_id="a",
            assumed_external_unlocks={"ch_heli_unlocked_test"},
        ).by_rule("UNLOCK_REQUIREMENT")
        self.assertEqual(assumed.status, EvaluationStatus.SATISFIED)

        unknown_db = database(vehicle("a", reqUnlock="mystery"))
        unknown = (
            GraphRuleEvaluator(ResearchGraphBuilder.from_database(unknown_db))
            .evaluate(target_vehicle_id="a")
            .by_rule("UNLOCK_REQUIREMENT")
        )
        self.assertEqual(unknown.evidence["classification"], UnlockClassification.UNKNOWN.value)

    def test_contradictory_unlocks_are_unresolved(self):
        base = ResearchGraphBuilder.from_database(database(vehicle("a")))
        unlock_one = GraphNode("unlock:one", NodeType.UNLOCK, "one")
        unlock_two = GraphNode("unlock:two", NodeType.UNLOCK, "two")
        graph = ResearchGraph(
            game_version=base.game_version,
            nodes=[*base.nodes, unlock_one, unlock_two],
            edges=[
                *base.edges,
                GraphEdge(
                    unlock_one.node_id,
                    "vehicle:a",
                    EdgeType.UNLOCK_REQUIREMENT,
                ),
                GraphEdge(
                    unlock_two.node_id,
                    "vehicle:a",
                    EdgeType.UNLOCK_REQUIREMENT,
                ),
            ],
        )
        rule = (
            GraphRuleEvaluator(graph).evaluate(target_vehicle_id="a").by_rule("UNLOCK_REQUIREMENT")
        )
        self.assertEqual(rule.evidence["classification"], UnlockClassification.CONTRADICTORY.value)
        self.assertEqual(rule.status, EvaluationStatus.UNRESOLVED)

    def test_rank_evaluation_lists_counts_candidates_and_exclusions(self):
        db = database(
            vehicle("a"),
            vehicle("b"),
            vehicle("hidden", hiddenResearch=True),
            vehicle("premium", premium=True),
            vehicle("target", rank=2),
            rank_unlock={"country_test": {"army": {"1": 2}}},
        )
        rule = (
            GraphRuleEvaluator(ResearchGraphBuilder.from_database(db))
            .evaluate(
                target_vehicle_id="target",
                progress=PlayerProgress(
                    vehicles={"a": VehicleProgress(researched=True, purchased=True)}
                ),
            )
            .by_rule("RANK_REQUIREMENT_1")
        )
        self.assertEqual(rule.status, EvaluationStatus.UNSATISFIED)
        self.assertEqual(rule.evidence["requiredVehicleCount"], 2)
        self.assertEqual(rule.evidence["qualifyingVehicleIds"], ["a"])
        self.assertEqual(rule.evidence["missingVehicleCount"], 1)
        self.assertEqual(rule.evidence["candidateVehicleIds"], ["b"])
        self.assertEqual(
            {item["reason"] for item in rule.evidence["excludedCandidates"]},
            {"hiddenResearch", "premium"},
        )
        self.assertFalse(rule.evidence["selectionPerformed"])

    def test_evidence_is_deterministic_and_all_statuses_serialize(self):
        evaluator = GraphRuleEvaluator(self.sample_graph)
        first = evaluator.evaluate(target_vehicle_id="germ_leopard_2a7v").to_dict()
        second = evaluator.evaluate(target_vehicle_id="germ_leopard_2a7v").to_dict()
        self.assertEqual(first, second)
        json.dumps(first)
        statuses = set(first["counts"])
        self.assertEqual(statuses, {item.value for item in EvaluationStatus})

    def test_refined_diagnostics_are_complete(self):
        diagnostics = self.sample_graph.diagnostics()
        self.assertEqual(sum(diagnostics.root_nodes_by_type.values()), diagnostics.root_node_count)
        self.assertEqual(sum(diagnostics.leaf_nodes_by_type.values()), diagnostics.leaf_node_count)
        self.assertIn("regular", diagnostics.components_by_vehicle_class)
        self.assertIn("premium", diagnostics.components_by_vehicle_class)
        self.assertIn("cycles", diagnostics.diagnostic_categories)
        self.assertEqual(diagnostics.diagnostic_categories["cycles"], "expected")

    def test_special_case_matrix_has_exactly_49_deterministic_rows(self):
        first = build_special_case_matrix(self.sample_database, self.sample_graph)
        second = build_special_case_matrix(self.sample_database, self.sample_graph)
        self.assertEqual(first, second)
        self.assertEqual(len(first), 49)
        self.assertEqual(sum(bool(item["hiddenResearch"]) for item in first), 18)
        self.assertEqual(sum(bool(item["reqUnlock"]) for item in first), 31)
        committed = (ROOT / "docs" / "21_GRAPH_SPECIAL_CASE_MATRIX.md").read_text(encoding="utf-8")
        self.assertEqual(committed, render_special_case_matrix_markdown(first))

    def test_full_mirror_evaluation_has_no_mismatch(self):
        summary = run_mirror_evaluation(self.sample_database, self.sample_graph)
        self.assertEqual(summary.mismatch, 0)
        self.assertEqual(
            summary.exact_match + summary.unresolved_expected + summary.unsupported,
            len(self.sample_database.vehicles),
        )


if __name__ == "__main__":
    unittest.main()
