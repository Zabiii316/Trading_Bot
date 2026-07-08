from __future__ import annotations

from dataclasses import dataclass
from math import floor

from trading_contracts.enums import LiquidityLevelType

from .models import Bar, CandidateLevel


@dataclass(frozen=True, slots=True)
class RoundNumberConfig:
    step: float = 100.0
    levels_each_side: int = 3
    emit_distance_steps: float = 1.5
    major_step_multiplier: int = 5


class RoundNumberDetector:
    """Emits nearby psychological price levels with deduplication."""

    __slots__ = ("config", "_seen")

    def __init__(self, config: RoundNumberConfig | None = None) -> None:
        self.config = config or RoundNumberConfig()
        if self.config.step <= 0:
            raise ValueError("round number step must be positive")
        self._seen: set[tuple[str, float]] = set()

    def update(self, bar: Bar) -> list[CandidateLevel]:
        step = self.config.step
        center = floor(bar.close / step) * step
        emitted: list[CandidateLevel] = []
        for i in range(-self.config.levels_each_side, self.config.levels_each_side + 1):
            price = center + i * step
            if price <= 0:
                continue
            if abs(price - bar.close) > self.config.emit_distance_steps * step:
                continue
            key = (bar.symbol, round(price, 8))
            if key in self._seen:
                continue
            self._seen.add(key)
            is_major = (round(price / step) % self.config.major_step_multiplier) == 0
            emitted.append(
                CandidateLevel(
                    symbol=bar.symbol,
                    venue=bar.venue,
                    market_type=bar.market_type,
                    level_type=LiquidityLevelType.ROUND_NUMBER,
                    price=price,
                    time_ms=bar.end_time_ms,
                    source="round_number",
                    weight=0.85 if is_major else 0.55,
                    metadata={"step": step, "is_major": is_major},
                )
            )
        return emitted
