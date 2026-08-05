"""Wurstbrot GE Calculator 2.0 core engine."""

__version__ = "0.9.0-beta"

from .database import VehicleDatabase
from .graph_adapter import GraphDatabaseAdapter
from .graph_analysis import (
    MirrorEvaluationSummary,
    build_special_case_matrix,
    render_special_case_matrix_markdown,
    run_mirror_evaluation,
)
from .graph_evaluation import (
    EvaluationStatus,
    GraphEvaluationReport,
    GraphRuleEvaluator,
    RuleEvaluation,
    UnlockClassification,
)
from .graph_semantics import EDGE_SEMANTICS, EdgeSemantics, semantics_for
from .graph_resolution import (
    FolderRequirementResolution,
    GraphPrerequisiteResolver,
    LegacyRankCompatibilityStrategy,
    PrerequisiteResolution,
    RankCompatibilitySelection,
    RankRequirementResolution,
    ResolutionStatus,
    UnlockRequirementResolution,
)
from .graph_resolution_analysis import (
    ResolutionSpecialCaseSummary,
    ShadowCase,
    ShadowComparisonDetail,
    ShadowComparisonSummary,
    build_full_shadow_cases,
    build_player_progress_scenarios,
    build_resolution_special_case_matrix,
    render_resolution_special_case_markdown,
    run_shadow_comparison,
)
from .models import PlayerProgress, SolveOptions, SolveResult, VehicleProgress
from .research_graph import (
    EdgeType,
    DiagnosticCategory,
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
    "MirrorEvaluationSummary",
    "run_mirror_evaluation",
    "build_special_case_matrix",
    "render_special_case_matrix_markdown",
    "NodeType",
    "EdgeType",
    "DiagnosticCategory",
    "GraphNode",
    "GraphEdge",
    "GraphDiagnostics",
    "ResearchGraph",
    "ResearchGraphBuilder",
    "EdgeSemantics",
    "EDGE_SEMANTICS",
    "semantics_for",
    "EvaluationStatus",
    "UnlockClassification",
    "RuleEvaluation",
    "GraphEvaluationReport",
    "GraphRuleEvaluator",
    "ResolutionStatus",
    "RankCompatibilitySelection",
    "RankRequirementResolution",
    "FolderRequirementResolution",
    "UnlockRequirementResolution",
    "PrerequisiteResolution",
    "GraphPrerequisiteResolver",
    "LegacyRankCompatibilityStrategy",
    "ShadowCase",
    "ShadowComparisonDetail",
    "ShadowComparisonSummary",
    "ResolutionSpecialCaseSummary",
    "run_shadow_comparison",
    "build_full_shadow_cases",
    "build_player_progress_scenarios",
    "build_resolution_special_case_matrix",
    "render_resolution_special_case_markdown",
    "VehicleProgress",
    "PlayerProgress",
    "SolveOptions",
    "SolveResult",
    "ResearchSolver",
    "__version__",
]
