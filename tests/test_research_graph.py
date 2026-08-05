from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "core"))

from wurstbrot_core import (
    EdgeType,
    GraphDatabaseAdapter,
    GraphEdge,
    GraphNode,
    NodeType,
    ResearchGraph,
    ResearchGraphBuilder,
    ResearchSolver,
    VehicleDatabase,
)


class ResearchGraphTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.database = VehicleDatabase.from_json(
            ROOT / "data" / "samples" / "WT_Database_2.57.1.67.json"
        )
        cls.graph = ResearchGraphBuilder.from_database(cls.database)

    def test_builder_creates_all_node_and_edge_types(self):
        node_types = {node.node_type for node in self.graph.nodes}
        edge_types = {edge.edge_type for edge in self.graph.edges}
        self.assertEqual(node_types, set(NodeType))
        self.assertEqual(edge_types, set(EdgeType))
        self.assertEqual(
            self.graph.diagnostics().vehicle_node_count,
            len(self.database.vehicles),
        )
        self.assertEqual(
            self.graph.diagnostics().folder_node_count,
            len(self.database.groups),
        )

    def test_graph_closure_matches_legacy_database(self):
        for vehicle_id in self.database.vehicles:
            with self.subTest(vehicle_id=vehicle_id):
                self.assertEqual(
                    self.graph.predecessor_closure(vehicle_id),
                    self.database.closure(vehicle_id),
                )

    def test_adapter_keeps_solver_result_identical(self):
        legacy = ResearchSolver(self.database).solve(
            start_vehicle_id="germ_leopard_2a5",
            target_vehicle_id="germ_leopard_2a7v",
        )
        adapter = GraphDatabaseAdapter(self.database, self.graph)
        mirrored = ResearchSolver(adapter).solve(
            start_vehicle_id="germ_leopard_2a5",
            target_vehicle_id="germ_leopard_2a7v",
        )
        self.assertEqual(mirrored, legacy)

    def test_export_is_deterministic_and_serializable(self):
        first = self.graph.to_dict()
        second = ResearchGraphBuilder.from_database(self.database).to_dict()
        self.assertEqual(first, second)
        json.dumps(first)
        with tempfile.TemporaryDirectory() as directory:
            output = self.graph.write_json(Path(directory) / "graph.json")
            self.assertEqual(json.loads(output.read_text(encoding="utf-8")), first)

    def test_diagnostics_report_cycle_and_disable_longest_path(self):
        nodes = [
            GraphNode("vehicle:a", NodeType.VEHICLE, "a"),
            GraphNode("vehicle:b", NodeType.VEHICLE, "b"),
        ]
        graph = ResearchGraph(
            game_version="test",
            nodes=nodes,
            edges=[
                GraphEdge("vehicle:a", "vehicle:b", EdgeType.PREDECESSOR),
                GraphEdge("vehicle:b", "vehicle:a", EdgeType.PREDECESSOR),
            ],
        )
        diagnostics = graph.diagnostics()
        self.assertEqual(diagnostics.cycles, 1)
        self.assertFalse(diagnostics.is_dag)
        self.assertIsNone(diagnostics.longest_path)

    def test_model_accepts_multiple_predecessors_but_legacy_adapter_rejects_them(self):
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
        self.assertEqual(len(graph.incoming("vehicle:c", EdgeType.PREDECESSOR)), 2)
        with self.assertRaisesRegex(Exception, "Mehrere Vorgänger"):
            graph.predecessor_closure("c")

    def test_sample_diagnostics_are_internally_consistent(self):
        diagnostics = self.graph.diagnostics()
        self.assertTrue(diagnostics.is_dag)
        self.assertEqual(diagnostics.cycles, 0)
        self.assertEqual(
            diagnostics.node_count,
            diagnostics.vehicle_node_count
            + diagnostics.folder_node_count
            + diagnostics.unlock_node_count
            + diagnostics.rank_node_count,
        )
        self.assertGreater(diagnostics.edge_count, 0)
        self.assertGreater(diagnostics.root_node_count, 0)
        self.assertGreater(diagnostics.leaf_node_count, 0)
        self.assertGreater(diagnostics.disconnected_components, 0)
        self.assertIsNotNone(diagnostics.longest_path)
        self.assertGreater(diagnostics.average_branching_factor, 0)


if __name__ == "__main__":
    unittest.main()
