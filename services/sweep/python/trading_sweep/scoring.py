from __future__ import annotations

import math
from dataclasses import dataclass

from trading_contracts.enums import SweepOutcome
from trading_contracts.events import OrderFlowFeatureEvent

from .models import ResolutionBias, SweepDirection, outcome_bias


def clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, value))


def _safe_float(value) -> float | None:
    if value is None:
        return None
    return float(value)


def signed_alignment(value: float | None, sign: int, scale: float = 1.0) -> float:
    """Map a signed value into [0, 1] using a smooth tanh transform."""

    if value is None:
        return 0.5
    if scale <= 0:
        scale = 1.0
    return clamp(0.5 + 0.5 * math.tanh((sign * value) / scale))


@dataclass(frozen=True, slots=True)
class SweepScoringConfig:
    delta_weight: float = 0.35
    ofi_weight: float = 0.25
    depletion_weight: float = 0.20
    replenishment_weight: float = 0.10
    absorption_weight: float = 0.10
    ofi_scale: float = 5.0
    replenishment_scale: float = 2.0
    absorption_scale: float = 10.0


class SweepScorer:
    """Fast deterministic scoring for sweep consumption and resolution.

    Scores use only current order-flow feature snapshots. They are intentionally
    lightweight and explainable; ML ranking will come in a later phase.
    """

    __slots__ = ("config",)

    def __init__(self, config: SweepScoringConfig | None = None) -> None:
        self.config = config or SweepScoringConfig()

    def consumption_score(self, feature: OrderFlowFeatureEvent | None, direction: SweepDirection) -> float:
        if feature is None:
            return 0.0
        sign = 1 if direction == SweepDirection.UPSIDE else -1
        norm_delta = _safe_float(feature.normalized_delta)
        ofi = _safe_float(feature.ofi_l1 if feature.ofi_l1 is not None else feature.ofi_l5)
        if direction == SweepDirection.UPSIDE:
            depletion = _safe_float(feature.depth_depletion_ask)
            replenishment = _safe_float(feature.depth_replenishment_bid)
        else:
            depletion = _safe_float(feature.depth_depletion_bid)
            replenishment = _safe_float(feature.depth_replenishment_ask)
        absorption = _safe_float(feature.absorption_ratio)
        cfg = self.config
        return clamp(
            cfg.delta_weight * signed_alignment(norm_delta, sign, scale=0.50)
            + cfg.ofi_weight * signed_alignment(ofi, sign, scale=cfg.ofi_scale)
            + cfg.depletion_weight * clamp(depletion or 0.0)
            + cfg.replenishment_weight * clamp((replenishment or 0.0) / cfg.replenishment_scale)
            + cfg.absorption_weight * clamp((absorption or 0.0) / cfg.absorption_scale)
        )

    def resolution_score(self, feature: OrderFlowFeatureEvent | None, outcome: SweepOutcome) -> float:
        if feature is None:
            return 0.0
        bias = outcome_bias(outcome)
        if bias == ResolutionBias.NEUTRAL:
            return 0.0
        sign = 1 if bias == ResolutionBias.BULLISH else -1
        norm_delta = _safe_float(feature.normalized_delta)
        ofi = _safe_float(feature.ofi_l1 if feature.ofi_l1 is not None else feature.ofi_l5)
        if sign > 0:
            replenishment = _safe_float(feature.depth_replenishment_bid)
            opposite_depletion = _safe_float(feature.depth_depletion_ask)
        else:
            replenishment = _safe_float(feature.depth_replenishment_ask)
            opposite_depletion = _safe_float(feature.depth_depletion_bid)
        absorption = _safe_float(feature.absorption_ratio)
        cfg = self.config
        return clamp(
            cfg.delta_weight * signed_alignment(norm_delta, sign, scale=0.50)
            + cfg.ofi_weight * signed_alignment(ofi, sign, scale=cfg.ofi_scale)
            + cfg.replenishment_weight * clamp((replenishment or 0.0) / cfg.replenishment_scale)
            + cfg.depletion_weight * clamp(opposite_depletion or 0.0)
            + cfg.absorption_weight * clamp((absorption or 0.0) / cfg.absorption_scale)
        )
