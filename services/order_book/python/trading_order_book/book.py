from __future__ import annotations

import bisect
import hashlib
from dataclasses import dataclass
from decimal import Decimal
from typing import Iterable

from trading_contracts.events import PriceLevel


class BookIntegrityError(RuntimeError):
    """Raised when the local book becomes internally inconsistent."""


@dataclass(slots=True, frozen=True)
class TopOfBook:
    bid: PriceLevel
    ask: PriceLevel
    spread: Decimal
    spread_bps: Decimal


class SideBook:
    """Efficient mutable side of an order book.

    The implementation keeps a price -> quantity map plus a sorted price index. It avoids
    re-sorting the full side on every update while preserving exact Decimal prices.

    For asks, the sorted key is price. For bids, the sorted key is -price, so index 0 is
    always the best level for both sides.
    """

    __slots__ = ("side", "_levels", "_keys")

    def __init__(self, side: str) -> None:
        if side not in {"bid", "ask"}:
            raise ValueError("side must be 'bid' or 'ask'")
        self.side = side
        self._levels: dict[Decimal, Decimal] = {}
        self._keys: list[Decimal] = []

    def __len__(self) -> int:
        return len(self._levels)

    def _key(self, price: Decimal) -> Decimal:
        return -price if self.side == "bid" else price

    def clear(self) -> None:
        self._levels.clear()
        self._keys.clear()

    def load_snapshot(self, levels: Iterable[PriceLevel]) -> None:
        self.clear()
        for level in levels:
            if level.quantity > 0:
                self._levels[level.price] = level.quantity
        self._keys = sorted(self._key(price) for price in self._levels)

    def apply_level(self, price: Decimal, quantity: Decimal) -> None:
        """Apply one Binance depth delta level.

        Quantity == 0 removes a level. Quantity > 0 inserts or replaces the level.
        """
        if price <= 0:
            raise BookIntegrityError("price must be positive")
        if quantity < 0:
            raise BookIntegrityError("quantity cannot be negative")

        exists = price in self._levels
        key = self._key(price)
        if quantity == 0:
            if exists:
                del self._levels[price]
                pos = bisect.bisect_left(self._keys, key)
                if pos >= len(self._keys) or self._keys[pos] != key:
                    raise BookIntegrityError("price index missing for existing level")
                self._keys.pop(pos)
            return

        self._levels[price] = quantity
        if not exists:
            bisect.insort_left(self._keys, key)

    def best(self) -> PriceLevel | None:
        if not self._keys:
            return None
        key = self._keys[0]
        price = -key if self.side == "bid" else key
        qty = self._levels.get(price)
        if qty is None:
            raise BookIntegrityError("price index references missing level")
        return PriceLevel(price=price, quantity=qty)

    def top_n(self, n: int) -> list[PriceLevel]:
        if n <= 0:
            return []
        out: list[PriceLevel] = []
        for key in self._keys[:n]:
            price = -key if self.side == "bid" else key
            qty = self._levels[price]
            out.append(PriceLevel(price=price, quantity=qty))
        return out

    def depth_notional(self, n: int) -> Decimal:
        total = Decimal("0")
        for level in self.top_n(n):
            total += level.price * level.quantity
        return total


class LocalOrderBook:
    """Mutable local limit order book reconstructed from snapshot + diff updates."""

    __slots__ = ("symbol", "bids", "asks", "last_update_id", "sequence_healthy", "snapshot_time_ms")

    def __init__(self, symbol: str) -> None:
        self.symbol = symbol.upper()
        self.bids = SideBook("bid")
        self.asks = SideBook("ask")
        self.last_update_id: int | None = None
        self.sequence_healthy = False
        self.snapshot_time_ms: int | None = None

    @property
    def is_initialized(self) -> bool:
        return self.last_update_id is not None

    def load_snapshot(
        self,
        *,
        last_update_id: int,
        bids: Iterable[PriceLevel],
        asks: Iterable[PriceLevel],
        snapshot_time_ms: int | None = None,
    ) -> None:
        self.bids.load_snapshot(bids)
        self.asks.load_snapshot(asks)
        self.last_update_id = last_update_id
        self.snapshot_time_ms = snapshot_time_ms
        self.sequence_healthy = True
        self.validate_not_crossed()

    def apply_delta(self, *, update_id: int, bids: Iterable[PriceLevel], asks: Iterable[PriceLevel]) -> None:
        if self.last_update_id is None:
            raise BookIntegrityError("cannot apply delta before snapshot")
        for level in bids:
            self.bids.apply_level(level.price, level.quantity)
        for level in asks:
            self.asks.apply_level(level.price, level.quantity)
        self.last_update_id = update_id
        self.validate_not_crossed()

    def best_bid(self) -> PriceLevel:
        best = self.bids.best()
        if best is None:
            raise BookIntegrityError("book has no bids")
        return best

    def best_ask(self) -> PriceLevel:
        best = self.asks.best()
        if best is None:
            raise BookIntegrityError("book has no asks")
        return best

    def top(self) -> TopOfBook:
        bid = self.best_bid()
        ask = self.best_ask()
        spread = ask.price - bid.price
        if spread < 0:
            raise BookIntegrityError("book is crossed")
        midpoint = (ask.price + bid.price) / Decimal("2")
        spread_bps = Decimal("0") if midpoint == 0 else (spread / midpoint) * Decimal("10000")
        return TopOfBook(bid=bid, ask=ask, spread=spread, spread_bps=spread_bps)

    def validate_not_crossed(self) -> None:
        if len(self.bids) == 0 or len(self.asks) == 0:
            return
        if self.best_bid().price > self.best_ask().price:
            self.sequence_healthy = False
            raise BookIntegrityError("crossed local book after update")

    def depth_notional(self, side: str, n: int) -> Decimal:
        if side == "bid":
            return self.bids.depth_notional(n)
        if side == "ask":
            return self.asks.depth_notional(n)
        raise ValueError("side must be bid or ask")

    def checksum(self, depth: int = 10) -> str:
        """Deterministic local checksum for audit/replay, not Binance's CRC checksum."""
        parts: list[str] = []
        for side_book in (self.bids, self.asks):
            for level in side_book.top_n(depth):
                parts.append(f"{level.price}:{level.quantity}")
        return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()
