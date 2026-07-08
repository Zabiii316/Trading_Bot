from decimal import Decimal

from trading_contracts.enums import AggressorSide, EventType, MarketType, Venue
from trading_contracts.events import RawAggTradeEvent
from trading_features.book_view import BookView
from trading_features.engine import OrderFlowEngine, OrderFlowEngineConfig


def trade(qty: str, side: str, t: int) -> RawAggTradeEvent:
    is_buyer_maker = side == "sell"
    return RawAggTradeEvent(
        event_type=EventType.RAW_AGG_TRADE,
        source="test",
        venue=Venue.BINANCE_USDM,
        market_type=MarketType.PERPETUAL_FUTURES,
        symbol="BTCUSDT",
        event_time_ms=t,
        received_time_ms=t,
        agg_trade_id=t,
        price=Decimal("100"),
        quantity=Decimal(qty),
        first_trade_id=t,
        last_trade_id=t,
        trade_time_ms=t,
        is_buyer_maker=is_buyer_maker,
        aggressor_side=AggressorSide.SELL if is_buyer_maker else AggressorSide.BUY,
    )


def book(update_id: int, bid_qty: float, ask_qty: float, bid_px=100.0, ask_px=100.1):
    return BookView.from_levels(
        symbol="BTCUSDT",
        venue="binance_usdm",
        market_type="perpetual_futures",
        event_time_ms=1000 + update_id,
        received_time_ms=1000 + update_id,
        last_update_id=update_id,
        bids=[(bid_px, bid_qty), (99.9, 5.0), (99.8, 4.0), (99.7, 3.0), (99.6, 2.0)],
        asks=[(ask_px, ask_qty), (100.2, 5.0), (100.3, 4.0), (100.4, 3.0), (100.5, 2.0)],
    )


def test_engine_calculates_feature_event() -> None:
    engine = OrderFlowEngine(OrderFlowEngineConfig(window_ms=1000))
    engine.on_book(book(1, 10.0, 8.0))
    engine.on_trade(trade("2", "buy", 1010))
    engine.on_trade(trade("1", "sell", 1020))
    engine.on_book(book(2, 12.0, 4.0))
    event = engine.to_event()
    assert event.event_type == EventType.ORDER_FLOW_FEATURE
    assert event.trade_count == 2
    assert event.buy_volume == Decimal("2.0")
    assert event.sell_volume == Decimal("1.0")
    assert event.delta == Decimal("1.0")
    assert event.cumulative_volume_delta == Decimal("1.0")
    assert event.queue_imbalance_l1 == Decimal("0.5")
    assert event.ofi_l1 == Decimal("6.0")
    assert event.depth_depletion_ask is not None
    assert event.depth_replenishment_bid is not None


def test_engine_fail_closed_on_unhealthy_book() -> None:
    engine = OrderFlowEngine()
    engine.on_book(book(1, 10.0, 8.0))
    bad = BookView.from_levels(
        symbol="BTCUSDT",
        venue="binance_usdm",
        market_type="perpetual_futures",
        event_time_ms=2000,
        received_time_ms=2000,
        last_update_id=2,
        bids=[(100, 1)],
        asks=[(101, 1)],
        is_sequence_healthy=False,
    )
    engine.on_book(bad)
    try:
        engine.to_event()
    except RuntimeError:
        pass
    else:
        raise AssertionError("expected feature emission to fail after unhealthy book")
