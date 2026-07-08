from __future__ import annotations

from collections import deque
from dataclasses import dataclass

from .models import Bar, Pivot, PivotKind


@dataclass(frozen=True, slots=True)
class SwingDetectorConfig:
    left_strength: int = 3
    right_strength: int = 3
    min_prominence_ticks: float = 0.0


class SwingDetector:
    """Confirms swing highs/lows without live look-ahead leakage.

    A pivot is emitted only after `right_strength` later bars are observed. The
    pivot timestamp remains the historical bar timestamp; the confirmation time
    records when the detector actually knew about it.
    """

    __slots__ = ("config", "_bars")

    def __init__(self, config: SwingDetectorConfig | None = None) -> None:
        self.config = config or SwingDetectorConfig()
        if self.config.left_strength <= 0 or self.config.right_strength <= 0:
            raise ValueError("swing strengths must be positive")
        self._bars: deque[Bar] = deque(maxlen=self.config.left_strength + self.config.right_strength + 1)

    def update(self, bar: Bar) -> list[Pivot]:
        self._bars.append(bar)
        if len(self._bars) < self._bars.maxlen:  # type: ignore[arg-type]
            return []
        bars = list(self._bars)
        center_idx = self.config.left_strength
        center = bars[center_idx]
        left = bars[:center_idx]
        right = bars[center_idx + 1 :]
        pivots: list[Pivot] = []

        if all(center.high > b.high for b in left) and all(center.high >= b.high for b in right):
            prominence = center.high - max(max(b.high for b in left), max(b.high for b in right))
            if prominence >= self.config.min_prominence_ticks:
                pivots.append(
                    Pivot(
                        symbol=center.symbol,
                        venue=center.venue,
                        market_type=center.market_type,
                        kind=PivotKind.HIGH,
                        price=center.high,
                        time_ms=center.end_time_ms,
                        confirmed_time_ms=bar.end_time_ms,
                        left_strength=self.config.left_strength,
                        right_strength=self.config.right_strength,
                        volume=center.volume,
                        metadata={"prominence": prominence},
                    )
                )
        if all(center.low < b.low for b in left) and all(center.low <= b.low for b in right):
            prominence = min(min(b.low for b in left), min(b.low for b in right)) - center.low
            if prominence >= self.config.min_prominence_ticks:
                pivots.append(
                    Pivot(
                        symbol=center.symbol,
                        venue=center.venue,
                        market_type=center.market_type,
                        kind=PivotKind.LOW,
                        price=center.low,
                        time_ms=center.end_time_ms,
                        confirmed_time_ms=bar.end_time_ms,
                        left_strength=self.config.left_strength,
                        right_strength=self.config.right_strength,
                        volume=center.volume,
                        metadata={"prominence": prominence},
                    )
                )
        return pivots
