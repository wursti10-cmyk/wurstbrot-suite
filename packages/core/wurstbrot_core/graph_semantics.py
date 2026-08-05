from __future__ import annotations

from dataclasses import dataclass

from .research_graph import EdgeType, NodeType


@dataclass(frozen=True)
class EdgeSemantics:
    edge_type: EdgeType
    source_type: NodeType
    target_type: NodeType
    direction: str
    cardinality: str
    obligation: str
    research_eligibility: str
    purchase_eligibility: str
    rank_progress: str
    cost_calculation: str

    def to_dict(self) -> dict[str, str]:
        return {
            "edgeType": self.edge_type.value,
            "sourceType": self.source_type.value,
            "targetType": self.target_type.value,
            "direction": self.direction,
            "cardinality": self.cardinality,
            "obligation": self.obligation,
            "researchEligibility": self.research_eligibility,
            "purchaseEligibility": self.purchase_eligibility,
            "rankProgress": self.rank_progress,
            "costCalculation": self.cost_calculation,
        }


EDGE_SEMANTICS = {
    EdgeType.PREDECESSOR: EdgeSemantics(
        EdgeType.PREDECESSOR,
        NodeType.VEHICLE,
        NodeType.VEHICLE,
        "prerequisite vehicle to dependent vehicle",
        "zero or more in the graph; zero or one in the legacy adapter",
        "mandatory when exactly one edge is present; multiple edges are unresolved",
        "the predecessor must be fulfilled before research eligibility",
        "no independent purchase rule is proven",
        "fulfilled vehicles may count when the rank rule qualifies them",
        "adds no cost itself; unresolved vehicles are costed only by the legacy solver",
    ),
    EdgeType.FOLDER_MEMBER: EdgeSemantics(
        EdgeType.FOLDER_MEMBER,
        NodeType.FOLDER,
        NodeType.VEHICLE,
        "folder to ordered member vehicle",
        "one folder to zero or more members; a vehicle should have at most one folder",
        "membership is factual; no additional eligibility obligation is proven",
        "no effect beyond separately encoded predecessor edges",
        "no independent purchase rule is proven",
        "membership alone never changes rank counting",
        "membership alone never changes cost",
    ),
    EdgeType.UNLOCK_REQUIREMENT: EdgeSemantics(
        EdgeType.UNLOCK_REQUIREMENT,
        NodeType.UNLOCK,
        NodeType.VEHICLE,
        "unlock condition to affected vehicle",
        "zero or more; multiple different conditions are contradictory until specified",
        "mandatory token, but external token truth may be unobservable",
        "blocks when internally false; external unknown is unresolved",
        "no separate purchase rule is proven",
        "an unresolved externally unlocked vehicle is not silently counted",
        "the edge has no numeric cost and external acquisition cost is unknown",
    ),
    EdgeType.RANK_REQUIREMENT: EdgeSemantics(
        EdgeType.RANK_REQUIREMENT,
        NodeType.RANK,
        NodeType.VEHICLE,
        "rank gate to every vehicle in the following rank",
        "one gate to zero or more following-rank vehicles",
        "mandatory when requiredVehicles is positive",
        "required vehicle count gates research in the following rank",
        "the graph proves no additional purchase rule beyond the count source",
        "qualifying owned, reserve, start and mandatory-path vehicles contribute",
        "the edge has no cost; candidate selection belongs to a later optimizer",
    ),
}


def semantics_for(edge_type: EdgeType) -> EdgeSemantics:
    return EDGE_SEMANTICS[edge_type]
