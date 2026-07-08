from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from trading_contracts.enums import AvwapConfirmation, SweepOutcome

from .models import AvwapAnchor


BULLISH_OUTCOMES = {SweepOutcome.BULLISH_REJECTION.value, SweepOutcome.BULLISH_ACCEPTANCE.value}
BEARISH_OUTCOMES = {SweepOutcome.BEARISH_REJECTION.value, SweepOutcome.BEARISH_ACCEPTANCE.value}


@dataclass(frozen=True, slots=True)
class AvwapScoringConfig:
    max_good_distance_bps: float = 8.0
    max_extension_bps: float = 35.0
    slope_normalizer: float = 1.0
    band_extension_z: float = 2.0
    strong_threshold: float = 0.75
    weak_threshold: float = 0.55


class AvwapScorer:
    __slots__ = ("config",)

    def __init__(self, config: AvwapScoringConfig | None = None) -> None:
        self.config = config or AvwapScoringConfig()

    def bias_for_outcome(self, outcome: SweepOutcome | str | None) -> bool | None:
        if outcome is None:
            return None
        value = outcome.value if hasattr(outcome, "value") else str(outcome)
        if value in BULLISH_OUTCOMES:
            return True
        if value in BEARISH_OUTCOMES:
            return False
        return None

    def score(
        self,
        *,
        anchor: AvwapAnchor,
        price: float,
        outcome: SweepOutcome | str | None = None,
        is_reclaim: bool = False,
        is_failure: bool = False,
    ) -> tuple[Decimal, AvwapConfirmation, float | None, float]:
        avwap = anchor.avwap
        if avwap is None or price <= 0:
            return Decimal("0"), AvwapConfirmation.NEUTRAL, None, 0.0
        bullish = self.bias_for_outcome(outcome or anchor.sweep_outcome)
        distance_bps = ((price - avwap) / avwap) * 10_000.0
        sigma = anchor.sigma or 0.0
        z = ((price - avwap) / sigma) if sigma > 0 else None

        if bullish is None:
            position_score = 0.5
            slope_score = 0.5
        elif bullish:
            position_score = 1.0 if price >= avwap else 0.0
            slope_score = 1.0 if anchor.last_slope >= 0 else 0.25
        else:
            position_score = 1.0 if price <= avwap else 0.0
            slope_score = 1.0 if anchor.last_slope <= 0 else 0.25

        abs_distance = abs(distance_bps)
        if abs_distance <= self.config.max_good_distance_bps:
            distance_score = 1.0
        elif abs_distance >= self.config.max_extension_bps:
            distance_score = 0.0
        else:
            span = self.config.max_extension_bps - self.config.max_good_distance_bps
            distance_score = max(0.0, 1.0 - ((abs_distance - self.config.max_good_distance_bps) / span))

        band_score = 1.0
        if z is not None and abs(z) > self.config.band_extension_z:
            band_score = max(0.0, 1.0 - (abs(z) - self.config.band_extension_z) * 0.25)

        transition_score = 1.0 if is_reclaim else 0.5
        if is_failure:
            transition_score = 0.0

        raw = (
            0.35 * position_score
            + 0.20 * slope_score
            + 0.25 * distance_score
            + 0.10 * band_score
            + 0.10 * transition_score
        )
        raw = max(0.0, min(1.0, raw))

        if bullish is True:
            confirmation = AvwapConfirmation.STRONG_BULLISH if raw >= self.config.strong_threshold else (
                AvwapConfirmation.WEAK_BULLISH if raw >= self.config.weak_threshold else AvwapConfirmation.NEUTRAL
            )
        elif bullish is False:
            confirmation = AvwapConfirmation.STRONG_BEARISH if raw >= self.config.strong_threshold else (
                AvwapConfirmation.WEAK_BEARISH if raw >= self.config.weak_threshold else AvwapConfirmation.NEUTRAL
            )
        else:
            confirmation = AvwapConfirmation.NEUTRAL
        return Decimal(str(round(raw, 8))), confirmation, z, distance_bps
