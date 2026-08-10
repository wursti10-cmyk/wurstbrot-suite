from __future__ import annotations

import argparse
import sys

from . import __version__
from .database import VehicleDatabase
from .engine_execution import (
    CalculationEngine,
    CalculationExecutionResult,
    EngineFeatureFlags,
    ExecutionMode,
)
from .explain import explain_result
from .models import PlayerProgress, SolveOptions, VehicleProgress


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Wurstbrot GE Calculator 2.0 RC")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("--database", required=True)
    parser.add_argument("--target", required=True)
    parser.add_argument("--start")
    parser.add_argument(
        "--engine",
        choices=("legacy", "shadow", "graph-experimental"),
        default="legacy",
        help=(
            "Rechenquelle (Standard: legacy). graph-experimental muss in jedem "
            "Aufruf ausdrücklich gewählt werden."
        ),
    )
    parser.add_argument("--optimize", choices=("ge", "rp", "sl", "vehicles"), default="ge")
    parser.add_argument("--include-start", action="store_true")
    parser.add_argument(
        "--include-hidden-legacy",
        "--legacy",
        dest="include_hidden_legacy",
        action="store_true",
        help="Ausgeblendete Altbestandsfahrzeuge einbeziehen (--legacy bleibt Alias).",
    )
    parser.add_argument("--sl-discount", type=int, choices=(0, 30, 50), default=0)
    parser.add_argument("--convertible-rp", type=int)
    parser.add_argument("--owned-ge", type=int, default=0)
    parser.add_argument(
        "--progress",
        action="append",
        default=[],
        metavar="ID:RP",
        help="Angeforschte RP, z. B. germ_leopard_2a5:120000",
    )
    parser.add_argument(
        "--owned",
        action="append",
        default=[],
        metavar="ID",
        help="Erforschtes und gekauftes Fahrzeug",
    )
    return parser


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(errors="replace")
    args = build_parser().parse_args()
    database = VehicleDatabase.from_json(args.database)

    vehicle_progress: dict[str, VehicleProgress] = {}
    for vehicle_id in args.owned:
        vehicle = database.get(vehicle_id)
        vehicle_progress[vehicle_id] = VehicleProgress(
            researched_rp=vehicle.rp,
            researched=True,
            purchased=True,
        )
    for item in args.progress:
        vehicle_id, separator, rp_text = item.partition(":")
        if not separator:
            raise SystemExit(f"Ungültiges --progress: {item}")
        existing = vehicle_progress.get(vehicle_id, VehicleProgress())
        existing.researched_rp = int(rp_text)
        vehicle_progress[vehicle_id] = existing

    progress = PlayerProgress(
        vehicles=vehicle_progress,
        convertible_rp=args.convertible_rp,
        owned_ge=args.owned_ge,
    )
    mode = ExecutionMode(args.engine.replace("-", "_"))
    flags = (
        EngineFeatureFlags.explicit_graph_experimental()
        if mode is ExecutionMode.GRAPH_EXPERIMENTAL
        else EngineFeatureFlags()
    )
    execution = CalculationEngine(database, feature_flags=flags).calculate(
        target_vehicle_id=args.target,
        start_vehicle_id=args.start,
        progress=progress,
        options=SolveOptions(
            optimize_for=args.optimize,
            include_start_vehicle=args.include_start,
            include_hidden_legacy=args.include_hidden_legacy,
            sl_discount_percent=args.sl_discount,
        ),
        mode=mode,
    )
    print(_execution_summary(execution))
    if execution.result is None:
        print("Keine darstellbare Berechnung verfügbar.")
        return 2
    print()
    print(explain_result(execution.result))
    return 0


def _execution_summary(execution: CalculationExecutionResult) -> str:
    source = execution.result_source.value if execution.result_source else "keine"
    graph_status = execution.graph_status.value if execution.graph_status else "nicht ausgeführt"
    comparison = (
        execution.comparison_status.value if execution.comparison_status else "nicht ausgeführt"
    )
    fallback_reason = execution.fallback_reason.value if execution.fallback_reason else "keiner"
    lines = []
    if execution.experimental:
        lines.append("WARNUNG: Graph Experimental ist nicht die empfohlene Rechenquelle für RC.1.")
    lines.extend(
        (
            f"Rechenmodus: {execution.requested_mode.value}",
            f"Ergebnisquelle: {source}",
            f"Fallback: {'ja' if execution.fallback_applied else 'nein'}",
            f"Fallback-Grund: {fallback_reason}",
            (
                "Shadow-Vergleich: "
                f"{'vorhanden' if execution.shadow_comparison_exists else 'nicht vorhanden'}"
            ),
            f"Comparison Status: {comparison}",
            f"Ergebnisstatus: {execution.calculation_status.value}",
            f"Graph-Status: {graph_status}",
        )
    )
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
