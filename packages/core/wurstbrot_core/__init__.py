"""Wurstbrot GE Calculator 2.0 core engine."""

__version__ = "0.9.0-beta"

from .database import VehicleDatabase
from .graph_adapter import GraphDatabaseAdapter
from .models import PlayerProgress, SolveOptions, SolveResult, VehicleProgress
from .research_graph import (
    EdgeType,
    GraphDiagnostics,
    GraphEdge,
    GraphNode,
    NodeType,
    ResearchGraph,
    ResearchGraphBuilder,
)
from .solver import ResearchSolver

__all__ = [
    "VehicleDatabase",
    "GraphDatabaseAdapter",
    "NodeType",
    "EdgeType",
    "GraphNode",
    "GraphEdge",
    "GraphDiagnostics",
    "ResearchGraph",
    "ResearchGraphBuilder",
    "VehicleProgress",
    "PlayerProgress",
    "SolveOptions",
    "SolveResult",
    "ResearchSolver",
    "__version__",
]
