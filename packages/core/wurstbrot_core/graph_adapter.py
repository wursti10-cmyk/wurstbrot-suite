from __future__ import annotations

from .database import VehicleDatabase
from .models import Vehicle
from .research_graph import ResearchGraph, ResearchGraphBuilder


class GraphDatabaseAdapter:
    """VehicleDatabase-compatible read adapter backed by the parallel graph.

    Non-graph reads deliberately delegate to the legacy database. The existing
    ResearchSolver can therefore run unchanged while every prerequisite closure
    is resolved through ResearchGraph.
    """

    def __init__(
        self,
        database: VehicleDatabase,
        graph: ResearchGraph | None = None,
    ) -> None:
        self.database = database
        self.graph = graph or ResearchGraphBuilder.from_database(database)
        self.game_version = database.game_version
        self.rp_per_ge = database.rp_per_ge
        self.vehicles = database.vehicles
        self.predecessors = database.predecessors
        self.groups = database.groups
        self.raw_groups = database.raw_groups
        self.rank_unlock = database.rank_unlock

    def get(self, vehicle_id: str) -> Vehicle:
        return self.database.get(vehicle_id)

    def closure(self, vehicle_id: str) -> tuple[str, ...]:
        return self.graph.predecessor_closure(vehicle_id)

    def tree_vehicles(self, country_id: str, branch_id: str) -> tuple[Vehicle, ...]:
        return self.database.tree_vehicles(country_id, branch_id)

    def rank_requirement(self, country_id: str, branch_id: str, rank: int) -> int:
        return self.database.rank_requirement(country_id, branch_id, rank)
