from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Iterable

from trading_contracts.events import OrderBookSnapshotEvent, PriceLevel, ReconstructedBookEvent


@dataclass(frozen=True, slots=True)
class Level:
    """Fast immutable level representation used inside the feature engine.

    The contract layer keeps exact Decimals. For low-latency feature calculations we use
    floats internally and convert back to Decimal at the event boundary.
    """

    price: float
    quantity: float

    @classmethod
    def from_contract(cls, level: PriceLevel) -> "Level":
        return cls(price=float(level.price), quantity=float(level.quantity))

    def to_contract(self) -> PriceLevel:
        return PriceLevel(price=Decimal(str(self.price)), quantity=Decimal(str(self.quantity)))


@dataclass(frozen=True, slots=True)
class BookView:
    """Top-N view of a local order book for order-flow feature calculations."""

    symbol: str
    event_time_ms: int
    received_time_ms: int
    venue: str
    market_type: str
    last_update_id: int
    bids: tuple[Level, ...]
    asks: tuple[Level, ...]
    is_sequence_healthy: bool = True

    @property
    def best_bid(self) -> Level | None:
        return self.bids[0] if self.bids else None

    @property
    def best_ask(self) -> Level | None:
        return self.asks[0] if self.asks else None

    @property
    def mid_price(self) -> float | None:
        if not self.best_bid or not self.best_ask:
            return None
        return (self.best_bid.price + self.best_ask.price) / 2.0

    @property
    def spread(self) -> float | None:
        if not self.best_bid or not self.best_ask:
            return None
        return self.best_ask.price - self.best_bid.price

    def top(self, side: str, n: int) -> tuple[Level, ...]:
        if n <= 0:
            return ()
        if side == "bid":
            return self.bids[:n]
        if side == "ask":
            return self.asks[:n]
        raise ValueError("side must be 'bid' or 'ask'")

    def depth_qty(self, side: str, n: int) -> float:
        return sum(level.quantity for level in self.top(side, n))

    def depth_notional(self, side: str, n: int) -> float:
        return sum(level.price * level.quantity for level in self.top(side, n))

    def qty_at(self, side: str, price: float) -> float:
        levels = self.bids if side == "bid" else self.asks
        for level in levels:
            if level.price == price:
                return level.quantity
        return 0.0

    @classmethod
    def from_levels(
        cls,
        *,
        symbol: str,
        event_time_ms: int,
        received_time_ms: int,
        venue: str,
        market_type: str,
        last_update_id: int,
        bids: Iterable[PriceLevel | Level | tuple[float, float]],
        asks: Iterable[PriceLevel | Level | tuple[float, float]],
        is_sequence_healthy: bool = True,
    ) -> "BookView":
        def normalize(item: PriceLevel | Level | tuple[float, float]) -> Level:
            if isinstance(item, Level):
                return item
            if isinstance(item, PriceLevel):
                return Level.from_contract(item)
            return Level(price=float(item[0]), quantity=float(item[1]))

        bid_levels = tuple(normalize(x) for x in bids)
        ask_levels = tuple(normalize(x) for x in asks)
        return cls(
            symbol=symbol.upper(),
            event_time_ms=event_time_ms,
            received_time_ms=received_time_ms,
            venue=venue,
            market_type=market_type,
            last_update_id=last_update_id,
            bids=bid_levels,
            asks=ask_levels,
            is_sequence_healthy=is_sequence_healthy,
        )

    @classmethod
    def from_snapshot(cls, event: OrderBookSnapshotEvent, depth: int = 20) -> "BookView":
        return cls.from_levels(
            symbol=event.symbol,
            event_time_ms=event.event_time_ms,
            received_time_ms=event.received_time_ms,
            venue=event.venue,
            market_type=event.market_type,
            last_update_id=event.last_update_id,
            bids=event.bids[:depth],
            asks=event.asks[:depth],
            is_sequence_healthy=True,
        )

    @classmethod
    def from_reconstructed(cls, event: ReconstructedBookEvent) -> "BookView":
        # Phase 3 reconstructed-book events contain best bid/ask only by default. Phase 5
        # can still compute L1 features from them, while higher-level features use full
        # BookView snapshots emitted by the reconstructor or replay tool.
        return cls.from_levels(
            symbol=event.symbol,
            event_time_ms=event.event_time_ms,
            received_time_ms=event.received_time_ms,
            venue=event.venue,
            market_type=event.market_type,
            last_update_id=event.last_update_id,
            bids=(event.best_bid,),
            asks=(event.best_ask,),
            is_sequence_healthy=event.is_sequence_healthy,
        )
