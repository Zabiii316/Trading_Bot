from __future__ import annotations

from collections import deque
from dataclasses import dataclass

from trading_contracts.enums import AggressorSide
from trading_contracts.events import RawAggTradeEvent, RawTradeEvent


@dataclass(slots=True, frozen=True)
class SignedTrade:
    time_ms: int
    price: float
    quantity: float
    signed_quantity: float


class RollingTradeWindow:
    """O(1) rolling delta, volume and count window."""

    __slots__ = ("window_ms", "_trades", "buy_volume", "sell_volume", "trade_count")

    def __init__(self, window_ms: int) -> None:
        if window_ms <= 0:
            raise ValueError("window_ms must be positive")
        self.window_ms = window_ms
        self._trades: deque[SignedTrade] = deque()
        self.buy_volume = 0.0
        self.sell_volume = 0.0
        self.trade_count = 0

    @property
    def trades(self) -> tuple[SignedTrade, ...]:
        return tuple(self._trades)

    @property
    def delta(self) -> float:
        return self.buy_volume - self.sell_volume

    @property
    def total_volume(self) -> float:
        return self.buy_volume + self.sell_volume

    @property
    def normalized_delta(self) -> float:
        total = self.total_volume
        return 0.0 if total <= 0.0 else self.delta / total

    def add(self, trade: SignedTrade) -> None:
        self._trades.append(trade)
        if trade.signed_quantity >= 0.0:
            self.buy_volume += trade.quantity
        else:
            self.sell_volume += trade.quantity
        self.trade_count += 1
        self.evict_older_than(trade.time_ms - self.window_ms)

    def evict_older_than(self, min_time_ms: int) -> None:
        while self._trades and self._trades[0].time_ms < min_time_ms:
            old = self._trades.popleft()
            if old.signed_quantity >= 0.0:
                self.buy_volume -= old.quantity
            else:
                self.sell_volume -= old.quantity
            self.trade_count -= 1

    def reset(self) -> None:
        self._trades.clear()
        self.buy_volume = 0.0
        self.sell_volume = 0.0
        self.trade_count = 0


def signed_trade_from_event(event: RawAggTradeEvent | RawTradeEvent) -> SignedTrade:
    qty = float(event.quantity)
    signed = qty if event.aggressor_side == AggressorSide.BUY else -qty
    return SignedTrade(
        time_ms=event.trade_time_ms,
        price=float(event.price),
        quantity=qty,
        signed_quantity=signed,
    )
