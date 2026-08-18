from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "core"))

from wurstbrot_core import (  # noqa: E402
    ResearchSolver,
    SolveOptions,
    VehicleDatabase,
    build_visual_tree_highlight,
    build_visual_tree_layout,
)


class VisualTreeLayoutContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.database = VehicleDatabase.from_json(
            ROOT / "data" / "samples" / "WT_Database_2.57.1.67.json"
        )
        cls.solver = ResearchSolver(cls.database)
        cls.tree_keys = sorted(
            {
                (vehicle.country_id, vehicle.branch_id)
                for vehicle in cls.database.vehicles.values()
            }
        )
        cls.layouts = {
            key: build_visual_tree_layout(
                cls.database,
                country_id=key[0],
                branch_id=key[1],
            )
            for key in cls.tree_keys
        }

    def test_full_dataset_has_one_deterministic_node_per_vehicle(self):
        self.assertEqual(len(self.tree_keys), 44)
        all_ids = [
            node.vehicle_id
            for layout in self.layouts.values()
            for node in layout.nodes
        ]
        self.assertEqual(len(all_ids), len(set(all_ids)))
        self.assertEqual(set(all_ids), set(self.database.vehicles))

        for key, layout in self.layouts.items():
            repeated = build_visual_tree_layout(
                self.database,
                country_id=key[0],
                branch_id=key[1],
            )
            self.assertEqual(layout, repeated)
            self.assertEqual(layout.fingerprint, repeated.fingerprint)

    def test_nodes_preserve_tree_rank_column_order_and_visibility(self):
        for key, layout in self.layouts.items():
            self.assertEqual(layout.country_id, key[0])
            self.assertEqual(layout.branch_id, key[1])
            for node in layout.nodes:
                source = self.database.get(node.vehicle_id)
                self.assertEqual(node.country_id, source.country_id)
                self.assertEqual(node.branch_id, source.branch_id)
                self.assertEqual(node.rank, source.rank)
                self.assertEqual(node.column, source.column)
                self.assertEqual(node.order, source.order)
                self.assertEqual(node.hidden_research, source.hidden_research)
                self.assertEqual(node.req_unlock, source.req_unlock)

            for rank in layout.ranks:
                for column in layout.columns:
                    members = [
                        node
                        for node in layout.nodes
                        if node.rank == rank and node.column == column
                    ]
                    expected = sorted(members, key=lambda node: (node.order, node.vehicle_id))
                    self.assertEqual(
                        [node.visual_slot for node in expected],
                        list(range(len(expected))),
                    )

    def test_edges_are_exact_reverse_index_without_cycles_or_inventions(self):
        emitted = {
            (edge.source_vehicle_id, edge.target_vehicle_id)
            for layout in self.layouts.values()
            for edge in layout.edges
        }
        expected = {
            (predecessor_id, vehicle_id)
            for vehicle_id, predecessor_id in self.database.predecessors.items()
            if predecessor_id is not None
        }
        self.assertEqual(emitted, expected)

        for layout in self.layouts.values():
            node_by_id = {node.vehicle_id: node for node in layout.nodes}
            for node in layout.nodes:
                expected_successors = sorted(
                    target
                    for source, target in emitted
                    if source == node.vehicle_id
                )
                self.assertEqual(sorted(node.successor_ids), expected_successors)

                seen: set[str] = set()
                current = node.vehicle_id
                while current is not None:
                    self.assertNotIn(current, seen)
                    seen.add(current)
                    current = node_by_id[current].predecessor_id

    def test_folder_contract_accounts_for_present_and_missing_members(self):
        emitted_folders = {
            folder.group_id: folder
            for layout in self.layouts.values()
            for folder in layout.folders
        }
        expected_group_ids = {
            vehicle.group
            for vehicle in self.database.vehicles.values()
            if vehicle.group
        }
        self.assertEqual(set(emitted_folders), expected_group_ids)

        for group_id, folder in emitted_folders.items():
            declared = tuple(self.database.raw_groups[group_id])
            self.assertEqual(folder.declared_member_ids, declared)
            self.assertEqual(
                set(folder.present_member_ids) | set(folder.missing_member_ids),
                set(declared),
            )
            self.assertFalse(set(folder.present_member_ids) & set(folder.missing_member_ids))
            for index, vehicle_id in enumerate(folder.present_member_ids):
                self.assertEqual(self.database.get(vehicle_id).group, group_id)
                self.assertEqual(
                    self.database.get(vehicle_id).group_index,
                    declared.index(vehicle_id),
                )

        emitted_missing = sum(
            len(folder.missing_member_ids) for folder in emitted_folders.values()
        )
        all_missing = {
            member_id
            for members in self.database.raw_groups.values()
            for member_id in members
            if member_id not in self.database.vehicles
        }
        unassignable_groups = {
            group_id
            for group_id, members in self.database.raw_groups.items()
            if not any(member_id in self.database.vehicles for member_id in members)
        }
        self.assertEqual(emitted_missing, 10)
        self.assertEqual(len(all_missing), 28)
        self.assertEqual(
            sum(len(self.database.raw_groups[group_id]) for group_id in unassignable_groups),
            18,
        )

    def test_ab_highlight_matches_the_user_visible_solver_result_exactly(self):
        layout = self.layouts[("country_germany", "army")]
        result = self.solver.solve(
            start_vehicle_id="germ_pzkpfw_VI_ausf_h1_tiger",
            target_vehicle_id="germ_leopard_2a7v",
        )
        highlight = build_visual_tree_highlight(
            layout,
            result,
            user_result_source="legacy",
            calculation_status="complete",
        )
        self.assertTrue(highlight.complete)
        self.assertEqual(highlight.start_vehicle_id, result.start_vehicle_id)
        self.assertEqual(highlight.target_vehicle_id, result.target_vehicle_id)

        for line in result.vehicle_lines:
            self.assertIn(
                f"required_{line.reason}",
                highlight.node_states[line.vehicle_id],
            )
        highlighted_required = {
            vehicle_id
            for vehicle_id, states in highlight.node_states.items()
            if any(state.startswith("required_") for state in states)
        }
        self.assertEqual(highlighted_required, set(result.required_vehicle_ids))

        direct_path = {
            line.vehicle_id for line in result.vehicle_lines if line.reason == "direct_path"
        }
        path_nodes = direct_path | {result.start_vehicle_id}
        expected_edges = {
            f"{edge.source_vehicle_id}->{edge.target_vehicle_id}"
            for edge in layout.edges
            if edge.source_vehicle_id in path_nodes and edge.target_vehicle_id in direct_path
        }
        self.assertEqual(set(highlight.required_edge_ids), expected_edges)

        prototype = json.loads(
            (ROOT / "apps" / "visual-tech-tree-prototype" / "germany-army.json")
            .read_text(encoding="utf-8")
        )
        serialized_layout = json.loads(json.dumps(layout.to_dict()))
        serialized_highlight = json.loads(json.dumps(highlight.to_dict()))
        self.assertEqual(prototype["layout"], serialized_layout)
        self.assertEqual(prototype["highlight"], serialized_highlight)
        self.assertEqual(
            prototype["solverSummary"]["requiredVehicleIds"],
            list(result.required_vehicle_ids),
        )
        manifest = (ROOT / "MANIFEST.in").read_text(encoding="utf-8")
        apps_rule = next(
            line for line in manifest.splitlines() if line.startswith("recursive-include apps ")
        )
        self.assertIn("*.json", apps_rule.split())

    def test_all_14_known_partial_cases_remain_visible_and_incomplete(self):
        dossier = json.loads(
            (ROOT / "accuracy" / "research" / "partial_folder_cases_2.57.1.67.json")
            .read_text(encoding="utf-8")
        )
        self.assertEqual(dossier["caseCount"], 14)
        for case in dossier["caseEvidence"]:
            vehicle_id = case["target_vehicle_id"]
            vehicle = self.database.get(vehicle_id)
            result = self.solver.solve(
                target_vehicle_id=vehicle_id,
                options=SolveOptions(
                    include_hidden_legacy=True,
                    assume_external_unlocks=True,
                ),
            )
            layout = self.layouts[(vehicle.country_id, vehicle.branch_id)]
            highlight = build_visual_tree_highlight(
                layout,
                result,
                user_result_source="legacy",
                calculation_status="partial",
                fallback_reason="FOLDER_MEMBERSHIP",
                unresolved_vehicle_ids=(vehicle_id,),
                unresolved_folder_ids=(vehicle.group,),
            )
            self.assertFalse(highlight.complete)
            self.assertIn("partial_unresolved", highlight.node_states[vehicle_id])
            self.assertEqual(highlight.fallback_reason, "FOLDER_MEMBERSHIP")


if __name__ == "__main__":
    unittest.main()
