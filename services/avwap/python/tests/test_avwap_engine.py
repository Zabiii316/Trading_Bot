from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

from trading_contracts.enums import EventType, LiquidityLevelType, MarketType, SweepOutcome, SweepState, Venue
from trading_contracts.events import (
    LiquidityLevelEvent,
    LiquiditySweepEvent,
    PriceLevel,
    RawAggTradeEvent,
    ReconstructedBookEvent,
)
from trading_avwap.engine import AnchoredVwapEngine, AvwapEngineConfig
from trading_avwap.models import AnchorKind


def trade(price: str, qty: str, t: int) -> RawAggTradeEvent:
    return RawAggTradeEvent(
        event_type=EventType.RAW_AGG_TRADE,
        source="test",
        venue=Venue.BINANCE_USDM,
        market_type=MarketType.PERPETUAL_FUTURES,
        symbol="BTCUSDT",
        event_time_ms=t,
        received_time_ms=t,
        agg_trade_id=t,
        price=Decimal(price),
        quantity=Decimal(qty),
        first_trade_id=t,
        last_trade_id=t,
        trade_time_ms=t,
        is_buyer_maker=False,
        aggressor_side="buy",
    )


def level(t: int = 1_000) -> LiquidityLevelEvent:
    return LiquidityLevelEvent(
        event_type=EventType.LIQUIDITY_LEVEL,
        source="test",
        venue=Venue.BINANCE_USDM,
        market_type=MarketType.PERPETUAL_FUTURES,
        symbol="BTCUSDT",
        event_time_ms=t,
        received_time_ms=t,
        level_id=uuid4(),
        level_type=LiquidityLevelType.SWING_LOW,
        price=Decimal("100"),
        zone_low=Decimal("99.9"),
        zone_high=Decimal("100.1"),
        quality_score=Decimal("0.8"),
        touches=3,
        first_seen_ms=t,
        last_seen_ms=t,
        is_active=True,
    )


def sweep(state: SweepState, outcome: SweepOutcome, t: int, sid=None) -> LiquiditySweepEvent:
    return LiquiditySweepEvent(
        event_type=EventType.LIQUIDITY_SWEEP,
        source="test",
        venue=Venue.BINANCE_USDM,
        market_type=MarketType.PERPETUAL_FUTURES,
        symbol="BTCUSDT",
        event_time_ms=t,
        received_time_ms=t,
        sweep_id=sid or uuid4(),
        level_id=uuid4(),
        state=state,
        outcome=outcome,
        level_price=Decimal("100"),
        sweep_extreme_price=Decimal("99.5"),
        liquidity_score=Decimal("0.8"),
        order_flow_score=Decimal("0.7"),
    )


def book(mid: str, t: int) -> ReconstructedBookEvent:
    m = Decimal(mid)
    bid = m - Decimal("0.05")
    ask = m + Decimal("0.05")
    return ReconstructedBookEvent(
        event_type=EventType.RECONSTRUCTED_BOOK,
        source="test",
        venue=Venue.BINANCE_USDM,
        market_type=MarketType.PERPETUAL_FUTURES,
        symbol="BTCUSDT",
        event_time_ms=t,
        received_time_ms=t,
        last_update_id=t,
        best_bid=PriceLevel(price=bid, quantity=Decimal("10")),
        best_ask=PriceLevel(price=ask, quantity=Decimal("10")),
        spread=Decimal("0.10"),
        spread_bps=Decimal("10"),
        bid_depth_notional_10=Decimal("1000"),
        ask_depth_notional_10=Decimal("1000"),
        is_sequence_healthy=True,
    )


def test_structural_anchor_updates_from_trades():
    engine = AnchoredVwapEngine(AvwapEngineConfig(session_anchor_hours_utc=()))
    engine.on_liquidity_level(level())
    assert engine.active_anchors("BTCUSDT")[0].anchor_kind == AnchorKind.STRUCTURAL
    assert engine.on_trade(trade("100", "1", 1_010)) == []
    out = engine.on_trade(trade("102", "1", 1_020))
    assert out
    assert out[-1].anchor_type == "structural"
    assert out[-1].avwap == Decimal("101.0")


def test_session_anchor_created_at_configured_hour():
    engine = AnchoredVwapEngine(AvwapEngineConfig(session_anchor_hours_utc=(0,)))
    engine.on_trade(trade("100", "1", 0))
    anchors = engine.active_anchors("BTCUSDT")
    assert any(a.anchor_kind == AnchorKind.SESSION for a in anchors)


def test_sweep_anchor_and_reclaim_event():
    engine = AnchoredVwapEngine(AvwapEngineConfig(session_anchor_hours_utc=()))
    sid = uuid4()
    engine.on_sweep(sweep(SweepState.CONSUMPTION_CONFIRMED, SweepOutcome.BULLISH_REJECTION, 1_000, sid))
    engine.on_trade(trade("100", "1", 1_010))
    engine.on_trade(trade("100", "1", 1_020))
    engine.on_book(book("99", 1_030))
    out = engine.on_book(book("101", 1_040))
    assert out
    assert out[-1].is_reclaim is True
    assert out[-1].sweep_id == sid
    assert out[-1].confirmation_score >= Decimal("0")


def test_unhealthy_book_is_ignored():
    engine = AnchoredVwapEngine()
    b = book("100", 1_000)
    b.is_sequence_healthy = False
    assert engine.on_book(b) == []
