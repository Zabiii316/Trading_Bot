from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable

from trading_contracts.enums import LiquidityLevelType

from .models import Bar, CandidateLevel


@dataclass(frozen=True, slots=True)
class SessionSpec:
    name: str
    start_hour_utc: int
    end_hour_utc: int

    def contains_hour(self, hour: int) -> bool:
        if self.start_hour_utc == self.end_hour_utc:
            return True
        if self.start_hour_utc < self.end_hour_utc:
            return self.start_hour_utc <= hour < self.end_hour_utc
        return hour >= self.start_hour_utc or hour < self.end_hour_utc


@dataclass(slots=True)
class _SessionState:
    session_key: str
    high: float
    low: float
    high_time_ms: int
    low_time_ms: int
    volume: float


DEFAULT_SESSIONS = (
    SessionSpec("asia", 0, 8),
    SessionSpec("london", 8, 13),
    SessionSpec("new_york", 13, 21),
)


class SessionLevelEngine:
    """Tracks current-session highs/lows and emits prior session levels at rollover."""

    __slots__ = ("sessions", "_state_by_name")

    def __init__(self, sessions: Iterable[SessionSpec] = DEFAULT_SESSIONS) -> None:
        self.sessions = tuple(sessions)
        self._state_by_name: dict[str, _SessionState] = {}

    @staticmethod
    def _day_key(ms: int) -> str:
        dt = datetime.fromtimestamp(ms / 1000, tz=timezone.utc)
        return dt.strftime("%Y-%m-%d")

    @staticmethod
    def _hour(ms: int) -> int:
        return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).hour

    def _key(self, spec: SessionSpec, bar: Bar) -> str:
        # Overnight sessions that begin before midnight but contain post-midnight bars belong
        # to the previous date if the bar hour is before the session end.
        dt = datetime.fromtimestamp(bar.end_time_ms / 1000, tz=timezone.utc)
        date = dt.date()
        if spec.start_hour_utc > spec.end_hour_utc and dt.hour < spec.end_hour_utc:
            date = datetime.fromtimestamp((bar.end_time_ms - 86_400_000) / 1000, tz=timezone.utc).date()
        return f"{bar.symbol}:{spec.name}:{date.isoformat()}"

    def update(self, bar: Bar) -> list[CandidateLevel]:
        hour = self._hour(bar.end_time_ms)
        emitted: list[CandidateLevel] = []
        for spec in self.sessions:
            if not spec.contains_hour(hour):
                continue
            key = self._key(spec, bar)
            state = self._state_by_name.get(spec.name)
            if state is None or state.session_key != key:
                if state is not None:
                    emitted.extend(self._emit_completed_session(bar, spec, state))
                self._state_by_name[spec.name] = _SessionState(
                    session_key=key,
                    high=bar.high,
                    low=bar.low,
                    high_time_ms=bar.end_time_ms,
                    low_time_ms=bar.end_time_ms,
                    volume=bar.volume,
                )
            else:
                if bar.high > state.high:
                    state.high = bar.high
                    state.high_time_ms = bar.end_time_ms
                if bar.low < state.low:
                    state.low = bar.low
                    state.low_time_ms = bar.end_time_ms
                state.volume += max(bar.volume, 0.0)
        return emitted

    def _emit_completed_session(self, bar: Bar, spec: SessionSpec, state: _SessionState) -> list[CandidateLevel]:
        common = {
            "symbol": bar.symbol,
            "venue": bar.venue,
            "market_type": bar.market_type,
            "source": f"session:{spec.name}",
            "volume": state.volume,
            "weight": 1.0,
            "metadata": {"session": spec.name, "session_key": state.session_key},
        }
        return [
            CandidateLevel(
                level_type=LiquidityLevelType.SESSION_HIGH,
                price=state.high,
                time_ms=state.high_time_ms,
                **common,
            ),
            CandidateLevel(
                level_type=LiquidityLevelType.SESSION_LOW,
                price=state.low,
                time_ms=state.low_time_ms,
                **common,
            ),
        ]
