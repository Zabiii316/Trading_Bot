from __future__ import annotations

from math import floor, isfinite


def round_down_to_step(quantity: float, step: float) -> float:
    if step <= 0:
        return quantity
    if quantity <= 0:
        return 0.0
    return floor(quantity / step) * step


def safe_div(numerator: float, denominator: float, default: float = 0.0) -> float:
    if denominator == 0 or not isfinite(numerator) or not isfinite(denominator):
        return default
    return numerator / denominator
