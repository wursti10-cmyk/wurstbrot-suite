from __future__ import annotations

import math


def ge_for_remaining_rp(remaining_rp: int, rp_per_ge: int) -> int:
    """War Thunder rounds the conversion up for each vehicle separately."""
    if remaining_rp <= 0:
        return 0
    if rp_per_ge <= 0:
        raise ValueError("rp_per_ge muss größer als 0 sein.")
    return math.ceil(remaining_rp / rp_per_ge)


def apply_discount(value: int, discount_percent: int) -> int:
    if not 0 <= discount_percent <= 100:
        raise ValueError("Rabatt muss zwischen 0 und 100 liegen.")
    return round(value * (1 - discount_percent / 100))
