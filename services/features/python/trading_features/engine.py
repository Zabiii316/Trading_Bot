from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from uuid import uuid4

from trading_contracts.enums import EventType, MarketType, Venue
from trading_contracts.events import OrderFlowFeatureEvent, RawAggTradeEvent, RawTradeEvent

from .absorption import absorption_ratio
from .book_view import BookView
from .ofi import best_level_ofi, depth_delta_ofi, depth_depletion, depth_replenishment, queue_imbalance
from .rolling import RollingTradeWindow, signed_trade_from_event


@dataclass(frozen=True, slots=True)
class OrderFlowEngineConfig:
    window_ms: int = 1_000
    queue_levels: tuple[int, ...] = (1, 5, 10)
    ofi_levels: tuple[int, ...] = (1, 5)
    depletion_levels: int = 10
    queue_decay_lambda: float | None = None
    epsilon_price: float = 1e-9
    source: str = "feature-engine"


class OrderFlowEngine:
    """Incremental order-flow feature engine.

    This engine is intentionally stateful. It keeps only the rolling trade window, CVD and
    previous/current book views required for microstructure features. It never replays the
    full history inside the hot path.
    """

    __slots__ = ("config", "window", "cumulative_volume_delta", "previous_book", "current_book")

    def __init__(self, config: OrderFlowEngineConfig | None = None) -> None:
        self.config = config or OrderFlowEngineConfig()
        self.window = RollingTradeWindow(self.config.window_ms)
        self.cumulative_volume_delta = 0.0
        self.previous_book: BookView | None = None
        self.current_book: BookView | None = None

    def reset(self) -> None:
        self.window.reset()
        self.cumulative_volume_delta = 0.0
        self.previous_book = None
        self.current_book = None

    def on_trade(self, event: RawAggTradeEvent | RawTradeEvent) -> None:
        trade = signed_trade_from_event(event)
        self.window.add(trade)
        self.cumulative_volume_delta += trade.signed_quantity

    def on_book(self, book: BookView) -> None:
        if not book.is_sequence_healthy:
            # Fail closed: do not produce features from sequence-broken books.
            self.previous_book = None
            self.current_book = None
            return
        self.previous_book = self.current_book
        self.current_book = book
        self.window.evict_older_than(book.event_time_ms - self.config.window_ms)

    def snapshot_features(self) -> dict[str, float | int | None]:
        book = self.current_book
        prev = self.previous_book
        if book is None:
            raise RuntimeError("cannot calculate order-flow features before first book")

        qi1 = queue_imbalance(book, 1, self.config.queue_decay_lambda)
        qi5 = queue_imbalance(book, 5, self.config.queue_decay_lambda)
        qi10 = queue_imbalance(book, 10, self.config.queue_decay_lambda)
        ofi1 = best_level_ofi(prev, book)
        ofi5 = depth_delta_ofi(prev, book, 5)
        absorb = absorption_ratio(
            trade_window=self.window,
            previous_mid_price=prev.mid_price if prev else None,
            current_mid_price=book.mid_price,
            epsilon_price=self.config.epsilon_price,
        )
        dep_bid = depth_depletion(prev, book, "bid", self.config.depletion_levels)
        dep_ask = depth_depletion(prev, book, "ask", self.config.depletion_levels)
        rep_bid = depth_replenishment(prev, book, "bid", self.config.depletion_levels)
        rep_ask = depth_replenishment(prev, book, "ask", self.config.depletion_levels)
        return {
            "trade_count": self.window.trade_count,
            "buy_volume": self.window.buy_volume,
            "sell_volume": self.window.sell_volume,
            "delta": self.window.delta,
            "normalized_delta": self.window.normalized_delta,
            "cumulative_volume_delta": self.cumulative_volume_delta,
            "queue_imbalance_l1": qi1,
            "queue_imbalance_l5": qi5,
            "queue_imbalance_l10": qi10,
            "ofi_l1": ofi1,
            "ofi_l5": ofi5,
            "absorption_ratio": absorb,
            "depth_depletion_bid": dep_bid,
            "depth_depletion_ask": dep_ask,
            "depth_replenishment_bid": rep_bid,
            "depth_replenishment_ask": rep_ask,
        }

    @staticmethod
    def _decimal_or_none(value: float | int | None, precision: int = 12) -> Decimal | None:
        if value is None:
            return None
        # str(round()) avoids binary float noise while retaining enough precision for
        # signal generation. Raw data remains stored with full exchange precision.
        return Decimal(str(round(float(value), precision)))

    def to_event(self) -> OrderFlowFeatureEvent:
        book = self.current_book
        if book is None:
            raise RuntimeError("cannot emit features before first book")
        f = self.snapshot_features()
        return OrderFlowFeatureEvent(
            event_id=uuid4(),
            event_type=EventType.ORDER_FLOW_FEATURE,
            source=self.config.source,
            venue=Venue(book.venue),
            market_type=MarketType(book.market_type),
            symbol=book.symbol,
            event_time_ms=book.event_time_ms,
            received_time_ms=book.received_time_ms,
            window_ms=self.config.window_ms,
            trade_count=int(f["trade_count"] or 0),
            buy_volume=self._decimal_or_none(f["buy_volume"]) or Decimal("0"),
            sell_volume=self._decimal_or_none(f["sell_volume"]) or Decimal("0"),
            delta=self._decimal_or_none(f["delta"]) or Decimal("0"),
            normalized_delta=self._decimal_or_none(f["normalized_delta"]) or Decimal("0"),
            cumulative_volume_delta=self._decimal_or_none(f["cumulative_volume_delta"]) or Decimal("0"),
            queue_imbalance_l1=self._decimal_or_none(f["queue_imbalance_l1"]),
            queue_imbalance_l5=self._decimal_or_none(f["queue_imbalance_l5"]),
            queue_imbalance_l10=self._decimal_or_none(f["queue_imbalance_l10"]),
            ofi_l1=self._decimal_or_none(f["ofi_l1"]),
            ofi_l5=self._decimal_or_none(f["ofi_l5"]),
            absorption_ratio=self._decimal_or_none(f["absorption_ratio"]),
            depth_depletion_bid=self._decimal_or_none(f["depth_depletion_bid"]),
            depth_depletion_ask=self._decimal_or_none(f["depth_depletion_ask"]),
            depth_replenishment_bid=self._decimal_or_none(f["depth_replenishment_bid"]),
            depth_replenishment_ask=self._decimal_or_none(f["depth_replenishment_ask"]),
        )
