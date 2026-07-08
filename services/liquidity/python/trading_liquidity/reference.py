from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from trading_contracts.enums import LiquidityLevelType

from .models import Bar, CandidateLevel


@dataclass(slots=True)
class _PeriodState:
    key: str
    high: float
    low: float
    high_time_ms: int
    low_time_ms: int
    volume: float


class ReferenceLevelEngine:
    """Tracks previous day/week high/low levels from streaming bars."""

    __slots__ = ("_day", "_week")

    def __init__(self) -> None:
        self._day: _PeriodState | None = None
        self._week: _PeriodState | None = None

    @staticmethod
    def _day_key(ms: int) -> str:
        return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).strftime("%Y-%m-%d")

    @staticmethod
    def _week_key(ms: int) -> str:
        dt = datetime.fromtimestamp(ms / 1000, tz=timezone.utc)
        year, week, _ = dt.isocalendar()
        return f"{year}-W{week:02d}"

    def update(self, bar: Bar) -> list[CandidateLevel]:
        emitted: list[CandidateLevel] = []
        emitted.extend(self._update_period(bar, "day"))
        emitted.extend(self._update_period(bar, "week"))
        return emitted

    def _update_period(self, bar: Bar, period: str) -> list[CandidateLevel]:
        key = self._day_key(bar.end_time_ms) if period == "day" else self._week_key(bar.end_time_ms)
        state = self._day if period == "day" else self._week
        if state is None:
            new_state = _PeriodState(key, bar.high, bar.low, bar.end_time_ms, bar.end_time_ms, bar.volume)
            if period == "day":
                self._day = new_state
            else:
                self._week = new_state
            return []
        if state.key != key:
            emitted = self._emit_completed(bar, period, state)
            new_state = _PeriodState(key, bar.high, bar.low, bar.end_time_ms, bar.end_time_ms, bar.volume)
            if period == "day":
                self._day = new_state
            else:
                self._week = new_state
            return emitted
        if bar.high > state.high:
            state.high = bar.high
            state.high_time_ms = bar.end_time_ms
        if bar.low < state.low:
            state.low = bar.low
            state.low_time_ms = bar.end_time_ms
        state.volume += max(bar.volume, 0.0)
        return []

    def _emit_completed(self, bar: Bar, period: str, state: _PeriodState) -> list[CandidateLevel]:
        high_type = LiquidityLevelType.PREVIOUS_DAY_HIGH if period == "day" else LiquidityLevelType.PREVIOUS_WEEK_HIGH
        low_type = LiquidityLevelType.PREVIOUS_DAY_LOW if period == "day" else LiquidityLevelType.PREVIOUS_WEEK_LOW
        weight = 1.35 if period == "day" else 1.65
        common = {
            "symbol": bar.symbol,
            "venue": bar.venue,
            "market_type": bar.market_type,
            "source": f"previous_{period}",
            "volume": state.volume,
            "weight": weight,
            "metadata": {"period": period, "period_key": state.key},
        }
        return [
            CandidateLevel(level_type=high_type, price=state.high, time_ms=state.high_time_ms, **common),
            CandidateLevel(level_type=low_type, price=state.low, time_ms=state.low_time_ms, **common),
        ]
