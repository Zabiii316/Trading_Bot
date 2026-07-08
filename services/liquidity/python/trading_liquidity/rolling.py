from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from statistics import fmean

from .models import Bar


@dataclass(frozen=True, slots=True)
class AtrConfig:
    period: int = 14


class RollingAtr:
    __slots__ = ("period", "_trs", "_prev_close")

    def __init__(self, period: int = 14) -> None:
        if period <= 0:
            raise ValueError("ATR period must be positive")
        self.period = period
        self._trs: deque[float] = deque(maxlen=period)
        self._prev_close: float | None = None

    def update(self, bar: Bar) -> float:
        if self._prev_close is None:
            tr = bar.high - bar.low
        else:
            tr = max(bar.high - bar.low, abs(bar.high - self._prev_close), abs(bar.low - self._prev_close))
        self._trs.append(max(tr, 0.0))
        self._prev_close = bar.close
        return self.value

    @property
    def value(self) -> float:
        if not self._trs:
            return 0.0
        return float(fmean(self._trs))


class RollingVolatility:
    __slots__ = ("period", "_ranges")

    def __init__(self, period: int = 20) -> None:
        if period <= 0:
            raise ValueError("volatility period must be positive")
        self.period = period
        self._ranges: deque[float] = deque(maxlen=period)

    def update(self, bar: Bar) -> float:
        self._ranges.append(max(bar.high - bar.low, 0.0))
        return self.value

    @property
    def value(self) -> float:
        if not self._ranges:
            return 0.0
        return float(fmean(self._ranges))
