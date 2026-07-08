from __future__ import annotations

from dataclasses import dataclass
from math import exp, log1p

from trading_contracts.enums import LiquidityLevelType

from .models import PriceCluster


@dataclass(frozen=True, slots=True)
class LiquidityQualityConfig:
    recency_half_life_ms: int = 86_400_000
    touch_weight: float = 0.30
    recency_weight: float = 0.22
    type_weight: float = 0.24
    volume_weight: float = 0.14
    source_weight: float = 0.10
    prior_sweep_penalty: float = 0.10


_TYPE_WEIGHTS: dict[str, float] = {
    LiquidityLevelType.PREVIOUS_WEEK_HIGH.value: 1.00,
    LiquidityLevelType.PREVIOUS_WEEK_LOW.value: 1.00,
    LiquidityLevelType.PREVIOUS_DAY_HIGH.value: 0.92,
    LiquidityLevelType.PREVIOUS_DAY_LOW.value: 0.92,
    LiquidityLevelType.SESSION_HIGH.value: 0.78,
    LiquidityLevelType.SESSION_LOW.value: 0.78,
    LiquidityLevelType.EQUAL_HIGHS.value: 0.86,
    LiquidityLevelType.EQUAL_LOWS.value: 0.86,
    LiquidityLevelType.SWING_HIGH.value: 0.70,
    LiquidityLevelType.SWING_LOW.value: 0.70,
    LiquidityLevelType.ROUND_NUMBER.value: 0.52,
    LiquidityLevelType.CUSTOM.value: 0.50,
}


class LiquidityQualityScorer:
    __slots__ = ("config",)

    def __init__(self, config: LiquidityQualityConfig | None = None) -> None:
        self.config = config or LiquidityQualityConfig()

    def score(self, cluster: PriceCluster, now_ms: int) -> float:
        touches_score = min(1.0, log1p(max(cluster.touches, 0)) / log1p(8))
        age_ms = max(now_ms - cluster.last_seen_ms, 0)
        if self.config.recency_half_life_ms <= 0:
            recency_score = 1.0
        else:
            recency_score = 0.5 ** (age_ms / self.config.recency_half_life_ms)
        type_key = cluster.level_type.value if hasattr(cluster.level_type, "value") else str(cluster.level_type)
        type_score = _TYPE_WEIGHTS.get(type_key, 0.50)
        volume_score = min(1.0, log1p(max(cluster.total_volume, 0.0)) / log1p(10_000.0)) if cluster.total_volume else 0.0
        source_score = min(1.0, len(cluster.sources) / 4.0)
        prior_sweeps = float(cluster.metadata.get("prior_sweeps", 0) or 0)
        penalty = min(0.45, prior_sweeps * self.config.prior_sweep_penalty)
        raw = (
            self.config.touch_weight * touches_score
            + self.config.recency_weight * recency_score
            + self.config.type_weight * type_score
            + self.config.volume_weight * volume_score
            + self.config.source_weight * source_score
        )
        # total_weight captures reference-level priority and major round numbers.
        weighted = raw * min(1.20, max(0.60, cluster.total_weight / max(cluster.touches, 1)))
        return max(0.0, min(1.0, weighted - penalty))
