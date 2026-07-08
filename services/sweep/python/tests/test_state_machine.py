from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

from trading_contracts.enums import EventType, LiquidityLevelType, MarketType, SweepOutcome, SweepState, Venue
from trading_contracts.events import LiquidityLevelEvent, OrderFlowFeatureEvent, PriceLevel, ReconstructedBookEvent
from trading_features.book_view import BookView
from trading_sweep.state_machine import LiquiditySweepStateMachine, SweepEngineConfig


def level(level_type=LiquidityLevelType.EQUAL_HIGHS, price="100.00") -> LiquidityLevelEvent:
    p = Decimal(price)
    return LiquidityLevelEvent(
        event_type=EventType.LIQUIDITY_LEVEL,
        source="test",
        venue=Venue.BINANCE_USDM,
        market_type=MarketType.PERPETUAL_FUTURES,
        symbol="BTCUSDT",
        event_time_ms=1_000,
        received_time_ms=1_000,
        level_id=uuid4(),
        level_type=level_type,
        price=p,
        zone_low=p - Decimal("0.10"),
        zone_high=p + Decimal("0.10"),
        quality_score=Decimal("0.80"),
        touches=3,
        first_seen_ms=500,
        last_seen_ms=1_000,
        is_active=True,
    )


def book(mid: float, t: int) -> BookView:
    bid = mid - 0.05
    ask = mid + 0.05
    event = ReconstructedBookEvent(
        event_type=EventType.RECONSTRUCTED_BOOK,
        source="test",
        venue=Venue.BINANCE_USDM,
        market_type=MarketType.PERPETUAL_FUTURES,
        symbol="BTCUSDT",
        event_time_ms=t,
        received_time_ms=t,
        last_update_id=t,
        best_bid=PriceLevel(price=Decimal(str(bid)), quantity=Decimal("10")),
        best_ask=PriceLevel(price=Decimal(str(ask)), quantity=Decimal("10")),
        spread=Decimal("0.10"),
        spread_bps=Decimal("10"),
        bid_depth_notional_10=Decimal("1000"),
        ask_depth_notional_10=Decimal("1000"),
        is_sequence_healthy=True,
    )
    return BookView.from_reconstructed(event)


def flow(norm_delta: str, ofi: str, t: int) -> OrderFlowFeatureEvent:
    nd = Decimal(norm_delta)
    buy = Decimal("10") if nd >= 0 else Decimal("2")
    sell = Decimal("2") if nd >= 0 else Decimal("10")
    # override volumes to exactly match requested delta sign for validator
    if nd >= 0:
        buy, sell = Decimal("8"), Decimal("2")
    else:
        buy, sell = Decimal("2"), Decimal("8")
    delta = buy - sell
    normalized = delta / (buy + sell)
    return OrderFlowFeatureEvent(
        event_type=EventType.ORDER_FLOW_FEATURE,
        source="test",
        venue=Venue.BINANCE_USDM,
        market_type=MarketType.PERPETUAL_FUTURES,
        symbol="BTCUSDT",
        event_time_ms=t,
        received_time_ms=t,
        window_ms=1_000,
        trade_count=10,
        buy_volume=buy,
        sell_volume=sell,
        delta=delta,
        normalized_delta=normalized,
        cumulative_volume_delta=delta,
        queue_imbalance_l1=normalized,
        queue_imbalance_l5=normalized,
        queue_imbalance_l10=normalized,
        ofi_l1=Decimal(ofi),
        ofi_l5=Decimal(ofi),
        absorption_ratio=Decimal("12"),
        depth_depletion_bid=Decimal("0.7"),
        depth_depletion_ask=Decimal("0.7"),
        depth_replenishment_bid=Decimal("3"),
        depth_replenishment_ask=Decimal("3"),
    )


def test_upside_sweep_rejection_lifecycle():
    cfg = SweepEngineConfig(tick_size=0.01, atr_value=10, min_penetration_atr=0.001, min_penetration_ticks=2, acceptance_hold_ms=1_000)
    engine = LiquiditySweepStateMachine(cfg)
    lv = level(LiquidityLevelType.EQUAL_HIGHS, "100")

    armed = engine.on_liquidity_level(lv)
    assert armed[0].state == SweepState.LEVEL_ARMED

    approaching = engine.on_book(book(99.95, 1_100))
    assert approaching[-1].state == SweepState.APPROACHING_LEVEL

    engine.on_order_flow(flow("0.6", "10", 1_150))
    penetrating = engine.on_book(book(100.20, 1_200))
    assert penetrating[-1].state == SweepState.PENETRATING_LEVEL

    consumed = engine.on_book(book(100.25, 1_250))
    assert consumed[-1].state == SweepState.CONSUMPTION_CONFIRMED

    engine.on_order_flow(flow("-0.6", "-12", 1_300))
    rejected = engine.on_book(book(99.98, 1_320))
    states = [e.state for e in rejected]
    assert SweepState.REJECTION_CANDIDATE in states
    assert SweepState.ORDER_FLOW_CONFIRMED in states
    assert rejected[-1].outcome == SweepOutcome.BEARISH_REJECTION
    assert rejected[-1].reclaim_time_ms is not None


def test_downside_sweep_acceptance_lifecycle():
    cfg = SweepEngineConfig(tick_size=0.01, atr_value=10, min_penetration_atr=0.001, min_penetration_ticks=2, acceptance_hold_ms=100)
    engine = LiquiditySweepStateMachine(cfg)
    lv = level(LiquidityLevelType.EQUAL_LOWS, "100")
    engine.on_liquidity_level(lv)
    engine.on_book(book(100.05, 1_100))
    engine.on_order_flow(flow("-0.6", "-10", 1_150))
    engine.on_book(book(99.80, 1_200))
    engine.on_book(book(99.75, 1_250))
    accepted = engine.on_book(book(99.70, 1_400))
    states = [e.state for e in accepted]
    assert SweepState.ACCEPTANCE_CANDIDATE in states
    assert SweepState.ORDER_FLOW_CONFIRMED in states
    assert accepted[-1].outcome == SweepOutcome.BEARISH_ACCEPTANCE


def test_sequence_unhealthy_book_does_not_advance():
    engine = LiquiditySweepStateMachine(SweepEngineConfig())
    lv = level()
    engine.on_liquidity_level(lv)
    b = book(100, 1_100)
    b = BookView.from_levels(
        symbol=b.symbol,
        event_time_ms=b.event_time_ms,
        received_time_ms=b.received_time_ms,
        venue=b.venue,
        market_type=b.market_type,
        last_update_id=b.last_update_id,
        bids=b.bids,
        asks=b.asks,
        is_sequence_healthy=False,
    )
    assert engine.on_book(b) == []
    assert engine.active_contexts()[0].state == SweepState.LEVEL_ARMED


def test_expiry_fails_closed():
    engine = LiquiditySweepStateMachine(SweepEngineConfig(max_armed_lifetime_ms=10))
    lv = level()
    engine.on_liquidity_level(lv)
    out = engine.on_book(book(90, 2_000))
    assert out[-1].state == SweepState.EXPIRED
    assert out[-1].outcome == SweepOutcome.NO_TRADE
