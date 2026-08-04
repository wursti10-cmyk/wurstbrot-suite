from __future__ import annotations

from .models import SolveResult


def explain_result(result: SolveResult) -> str:
    lines = [
        "Wurstbrot GE Calculator 2.0 – Explain Mode",
        "=" * 48,
        f"Ziel: {result.target_vehicle_id}",
        "",
    ]

    for line in result.vehicle_lines:
        status = "bereits vorhanden" if line.already_owned else (
            f"{line.remaining_rp:,} RP → {line.ge:,} GE"
        )
        lines.append(
            f"- {line.name} [{line.reason}]: {status}; "
            f"SL {line.sl:,}"
        )

    lines.extend(
        [
            "",
            f"Fehlende RP: {result.total_rp:,}",
            f"GE vor Abzug vorhandener GE: {result.total_ge_before_owned:,}",
            f"Benötigte GE: {result.total_ge_after_owned:,}",
            f"SL: {result.total_sl:,}",
        ]
    )

    if result.convertible_rp_shortfall:
        lines.append(
            f"Fehlende convertible RP: {result.convertible_rp_shortfall:,}"
        )

    if result.warnings:
        lines.append("")
        lines.append("Warnungen:")
        lines.extend(f"- {warning}" for warning in result.warnings)

    return "\n".join(lines)
