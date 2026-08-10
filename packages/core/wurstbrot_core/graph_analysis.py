from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any

from .database import VehicleDatabase
from .graph_evaluation import EvaluationStatus, GraphRuleEvaluator
from .models import SolveOptions
from .research_graph import ResearchGraph
from .solver import ResearchSolver


@dataclass(frozen=True)
class MirrorEvaluationSummary:
    exact_match: int
    unresolved_expected: int
    mismatch: int
    unsupported: int
    details: tuple[dict[str, Any], ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "exact_match": self.exact_match,
            "unresolved_expected": self.unresolved_expected,
            "mismatch": self.mismatch,
            "unsupported": self.unsupported,
            "details": list(self.details),
        }


def run_mirror_evaluation(
    database: VehicleDatabase, graph: ResearchGraph
) -> MirrorEvaluationSummary:
    solver = ResearchSolver(database)
    evaluator = GraphRuleEvaluator(graph)
    counts: Counter[str] = Counter()
    details: list[dict[str, Any]] = []

    for target in sorted(database.vehicles.values(), key=lambda item: item.id):
        start_id = database.predecessors.get(target.id)
        report = evaluator.evaluate(
            target_vehicle_id=target.id,
            start_vehicle_id=start_id,
            options=SolveOptions(),
        )
        unresolved_rules = sorted(
            item.rule_id
            for item in report.evaluations
            if item.status is EvaluationStatus.UNRESOLVED
        )
        if target.hidden_research:
            category = "unsupported"
            reason = "hiddenResearch target is rejected by the default legacy contract"
        elif unresolved_rules:
            category = "unresolved_expected"
            reason = f"unresolved graph rules: {', '.join(unresolved_rules)}"
        else:
            try:
                legacy = solver.solve(
                    target_vehicle_id=target.id,
                    start_vehicle_id=start_id,
                    options=SolveOptions(),
                )
            except Exception as exc:
                category = "unsupported"
                reason = f"legacy solver did not produce a result: {exc}"
            else:
                legacy_direct = tuple(
                    line.vehicle_id for line in legacy.vehicle_lines if line.reason == "direct_path"
                )
                graph_direct = tuple(
                    report.by_rule("PREDECESSOR_REQUIREMENTS").evidence.get(
                        "requiredVehicleIds", ()
                    )
                )
                if legacy_direct == graph_direct:
                    category = "exact_match"
                    reason = "legacy direct prerequisites equal graph evaluation"
                else:
                    category = "mismatch"
                    reason = f"legacy={legacy_direct!r} graph={graph_direct!r}"
        counts[category] += 1
        if category != "exact_match":
            details.append(
                {
                    "targetVehicleId": target.id,
                    "category": category,
                    "reason": reason,
                }
            )

    return MirrorEvaluationSummary(
        exact_match=counts["exact_match"],
        unresolved_expected=counts["unresolved_expected"],
        mismatch=counts["mismatch"],
        unsupported=counts["unsupported"],
        details=tuple(details),
    )


def build_special_case_matrix(
    database: VehicleDatabase, graph: ResearchGraph
) -> tuple[dict[str, Any], ...]:
    evaluator = GraphRuleEvaluator(graph)
    rows: list[dict[str, Any]] = []
    for vehicle in sorted(database.vehicles.values(), key=lambda item: item.id):
        if not vehicle.hidden_research and not vehicle.req_unlock:
            continue
        report = evaluator.evaluate(target_vehicle_id=vehicle.id)
        unlock = report.by_rule("UNLOCK_REQUIREMENT")
        visibility = report.by_rule("TARGET_VISIBILITY")
        folder = report.by_rule("FOLDER_MEMBERSHIP")
        decisive = unlock if vehicle.req_unlock else visibility
        if vehicle.req_unlock:
            reason = "reqUnlock state is not represented in PlayerProgress"
            needed = f"authoritative state mapping for token {vehicle.req_unlock}"
        else:
            reason = "hiddenResearch availability is outside the default legacy contract"
            needed = "authoritative acquisition and availability classification"
        rows.append(
            {
                "vehicleId": vehicle.id,
                "countryId": vehicle.country_id,
                "branchId": vehicle.branch_id,
                "rank": vehicle.rank,
                "hiddenResearch": vehicle.hidden_research,
                "reqUnlock": vehicle.req_unlock or None,
                "folder": vehicle.group,
                "premium": vehicle.premium,
                "event": None,
                "squadron": None,
                "legacy": True if vehicle.hidden_research else None,
                "evaluationStatus": decisive.status.value,
                "unlockClassification": unlock.evidence.get("classification"),
                "folderStatus": folder.status.value,
                "broadRegressionBlocker": reason,
                "additionalDataRequired": needed,
            }
        )
    return tuple(rows)


def render_special_case_matrix_markdown(rows: tuple[dict[str, Any], ...]) -> str:
    lines = [
        "# Graph Special Case Matrix",
        "",
        "Generated from the normalized sample database and graph evaluation. `—` means the current "
        "schema does not contain an authoritative classification.",
        "",
        "| Vehicle | hiddenResearch | reqUnlock | Folder | Premium | Event | Squadron | "
        "Legacy | Status | Why not broadly regressible | Additional data required |",
        "|---|---:|---|---|---:|---|---|---|---|---|---|",
    ]
    for row in rows:
        values = [
            row["vehicleId"],
            _cell(row["hiddenResearch"]),
            _cell(row["reqUnlock"]),
            _cell(row["folder"]),
            _cell(row["premium"]),
            _cell(row["event"]),
            _cell(row["squadron"]),
            _cell(row["legacy"]),
            row["evaluationStatus"],
            row["broadRegressionBlocker"],
            row["additionalDataRequired"],
        ]
        lines.append("| " + " | ".join(str(value).replace("|", "\\|") for value in values) + " |")
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "- `hiddenResearch` targets are `unsatisfied` under default solver options and "
            "classified as legacy only because that source flag is explicit.",
            "- Recognized external `reqUnlock` tokens are ohne Eingabeevidenz `unresolved`; "
            "ein exakt passender",
            "  `PlayerProgress.fulfilled_unlocks`-Token oder die explizite Option erfüllt sie.",
            "- Event and Squadron stay `—`: the released regular database does not preserve "
            "evidence for those acquisition classes.",
            "- Classification is the sprint goal. No row is silently promoted to a solved "
            "regression case.",
            "",
        ]
    )
    return "\n".join(lines)


def _cell(value: Any) -> str:
    if value is None or value == "":
        return "—"
    if value is True:
        return "yes"
    if value is False:
        return "no"
    return str(value)
