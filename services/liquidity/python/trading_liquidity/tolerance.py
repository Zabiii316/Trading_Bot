from __future__ import annotations

from dataclasses import dataclass
from math import isfinite


@dataclass(frozen=True, slots=True)
class ZoneToleranceConfig:
    min_ticks: int = 4
    tick_size: float = 0.1
    atr_fraction: float = 0.08
    volatility_fraction: float = 0.08
    min_absolute: float = 0.0


class ToleranceModel:
    """Computes adaptive liquidity-zone width.

    Uses the maximum of tick, ATR, and short-term volatility components. Keeping
    this logic isolated prevents hidden inconsistency between swing, equality and
    clustering detectors.
    """

    __slots__ = ("config", "_last_atr", "_last_volatility")

    def __init__(self, config: ZoneToleranceConfig | None = None) -> None:
        self.config = config or ZoneToleranceConfig()
        self._last_atr = 0.0
        self._last_volatility = 0.0

    def update_context(self, atr: float | None = None, volatility: float | None = None) -> None:
        if atr is not None and isfinite(atr) and atr >= 0:
            self._last_atr = atr
        if volatility is not None and isfinite(volatility) and volatility >= 0:
            self._last_volatility = volatility

    def tolerance(self, reference_price: float | None = None) -> float:
        tick_component = self.config.min_ticks * self.config.tick_size
        atr_component = self.config.atr_fraction * self._last_atr
        vol_component = self.config.volatility_fraction * self._last_volatility
        base = max(tick_component, atr_component, vol_component, self.config.min_absolute)
        if reference_price and reference_price > 0:
            # Prevent pathologically tiny zones on high-price instruments when tick_size is unknown.
            base = max(base, reference_price * 0.000005)  # 0.05 bps floor
        return base
