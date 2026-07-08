from decimal import Decimal

from trading_contracts.enums import AggressorSide, EventType, MarketType, Venue
from trading_contracts.events import RawAggTradeEvent
from trading_features.rolling import RollingTradeWindow, signed_trade_from_event


def agg_trade(qty: str, buyer_maker: bool, t: int) -> RawAggTradeEvent:
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
        is_buyer_maker=buyer_maker,
        aggressor_side=AggressorSide.SELL if buyer_maker else AggressorSide.BUY,
    )


def test_signed_trade_from_binance_maker_flag() -> None:
    buy = signed_trade_from_event(agg_trade("2", buyer_maker=False, t=1))
    sell = signed_trade_from_event(agg_trade("3", buyer_maker=True, t=2))
    assert buy.signed_quantity == 2.0
    assert sell.signed_quantity == -3.0


def test_rolling_delta_and_eviction() -> None:
    window = RollingTradeWindow(window_ms=100)
    window.add(signed_trade_from_event(agg_trade("2", False, 1000)))
    window.add(signed_trade_from_event(agg_trade("1", True, 1050)))
    assert window.buy_volume == 2.0
    assert window.sell_volume == 1.0
    assert window.delta == 1.0
    assert round(window.normalized_delta, 6) == round(1 / 3, 6)
    window.add(signed_trade_from_event(agg_trade("4", False, 1201)))
    assert window.trade_count == 1
    assert window.buy_volume == 4.0
    assert window.sell_volume == 0.0
