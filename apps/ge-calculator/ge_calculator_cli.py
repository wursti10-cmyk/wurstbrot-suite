from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "packages" / "core"))

from wurstbrot_core import (  # noqa: E402
    PlayerProgress,
    ResearchSolver,
    SolveOptions,
    VehicleDatabase,
    VehicleProgress,
)
from wurstbrot_core.explain import explain_result  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Wurstbrot GE Calculator 2.0 Alpha"
    )
    parser.add_argument("--database", required=True)
    parser.add_argument("--target", required=True)
    parser.add_argument("--start")
    parser.add_argument(
        "--optimize",
        choices=("ge", "rp", "sl", "vehicles"),
        default="ge",
    )
    parser.add_argument("--include-start", action="store_true")
    parser.add_argument("--legacy", action="store_true")
    parser.add_argument("--sl-discount", type=int, default=0)
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
    args = build_parser().parse_args()
    database = VehicleDatabase.from_json(args.database)

    vehicle_progress: dict[str, VehicleProgress] = {}
    for vehicle_id in args.owned:
        vehicle_progress[vehicle_id] = VehicleProgress(
            researched=True, purchased=True
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
    result = ResearchSolver(database).solve(
        target_vehicle_id=args.target,
        start_vehicle_id=args.start,
        progress=progress,
        options=SolveOptions(
            optimize_for=args.optimize,
            include_start_vehicle=args.include_start,
            include_hidden_legacy=args.legacy,
            sl_discount_percent=args.sl_discount,
        ),
    )
    print(explain_result(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
