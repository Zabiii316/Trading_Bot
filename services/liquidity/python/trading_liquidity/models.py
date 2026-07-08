from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from trading_contracts.enums import LiquidityLevelType, MarketType, Venue


class PivotKind(str, Enum):
    HIGH = "high"
    LOW = "low"


@dataclass(frozen=True, slots=True)
class Bar:
    """Normalized OHLCV bar used by the liquidity engine.

    The engine accepts bars rather than raw ticks because structural levels are
    inherently time-windowed. Upstream services may build these bars from
    exchange klines, reconstructed mid-prices, or replayed trades.
    """

    symbol: str
    venue: Venue | str
    market_type: MarketType | str
    start_time_ms: int
    end_time_ms: int
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0
    trade_count: int = 0

    def __post_init__(self) -> None:
        if self.end_time_ms < self.start_time_ms:
            raise ValueError("bar end_time_ms cannot be before start_time_ms")
        if min(self.open, self.high, self.low, self.close) <= 0:
            raise ValueError("bar prices must be positive")
        if self.high < max(self.open, self.close, self.low):
            raise ValueError("bar high must be >= open, close and low")
        if self.low > min(self.open, self.close, self.high):
            raise ValueError("bar low must be <= open, close and high")

    @property
    def event_time_ms(self) -> int:
        return self.end_time_ms

    @property
    def typical_price(self) -> float:
        return (self.high + self.low + self.close) / 3.0


@dataclass(frozen=True, slots=True)
class Pivot:
    symbol: str
    venue: Venue | str
    market_type: MarketType | str
    kind: PivotKind
    price: float
    time_ms: int
    confirmed_time_ms: int
    left_strength: int
    right_strength: int
    volume: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class CandidateLevel:
    symbol: str
    venue: Venue | str
    market_type: MarketType | str
    level_type: LiquidityLevelType
    price: float
    time_ms: int
    source: str
    volume: float = 0.0
    weight: float = 1.0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class PriceCluster:
    symbol: str
    venue: Venue | str
    market_type: MarketType | str
    level_type: LiquidityLevelType
    price: float
    zone_low: float
    zone_high: float
    touches: int
    first_seen_ms: int
    last_seen_ms: int
    total_weight: float = 0.0
    total_volume: float = 0.0
    sources: set[str] = field(default_factory=set)
    metadata: dict[str, Any] = field(default_factory=dict)

    def can_absorb(self, candidate: CandidateLevel, tolerance: float) -> bool:
        if candidate.symbol != self.symbol:
            return False
        if candidate.level_type != self.level_type:
            return False
        return candidate.price >= self.zone_low - tolerance and candidate.price <= self.zone_high + tolerance

    def absorb(self, candidate: CandidateLevel, tolerance: float) -> None:
        new_weight = max(candidate.weight, 0.000001)
        weighted_notional = self.price * max(self.total_weight, 0.000001) + candidate.price * new_weight
        self.total_weight += new_weight
        self.price = weighted_notional / max(self.total_weight, 0.000001)
        self.zone_low = min(self.zone_low, candidate.price - tolerance)
        self.zone_high = max(self.zone_high, candidate.price + tolerance)
        self.touches += 1
        self.first_seen_ms = min(self.first_seen_ms, candidate.time_ms)
        self.last_seen_ms = max(self.last_seen_ms, candidate.time_ms)
        self.total_volume += max(candidate.volume, 0.0)
        self.sources.add(candidate.source)
        self.metadata.update(candidate.metadata)
