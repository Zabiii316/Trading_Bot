from decimal import Decimal
from uuid import uuid4

from trading_contracts.enums import AvwapConfirmation, EventType, MarketType, SweepOutcome, SweepState, Venue
from trading_contracts.events import AnchoredVwapEvent, LiquiditySweepEvent, PriceLevel, ReconstructedBookEvent
from trading_signals.engine import SignalScorerEngine


def book(t=1_000):
    return ReconstructedBookEvent(
        event_type=EventType.RECONSTRUCTED_BOOK,
        source="test",
        venue=Venue.BINANCE_USDM,
        market_type=MarketType.PERPETUAL_FUTURES,
        symbol="BTCUSDT",
        event_time_ms=t,
        received_time_ms=t,
        last_update_id=t,
        best_bid=PriceLevel(price=Decimal("100.00"), quantity=Decimal("100")),
        best_ask=PriceLevel(price=Decimal("100.01"), quantity=Decimal("100")),
        spread=Decimal("0.01"),
        spread_bps=Decimal("1"),
        bid_depth_notional_10=Decimal("100000"),
        ask_depth_notional_10=Decimal("100000"),
        is_sequence_healthy=True,
    )


def sweep(outcome=SweepOutcome.BULLISH_REJECTION, t=1_001, sid=None, of="0.82"):
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
        state=SweepState.ORDER_FLOW_CONFIRMED,
        outcome=outcome,
        level_price=Decimal("100"),
        sweep_extreme_price=Decimal("99.5") if outcome == SweepOutcome.BULLISH_REJECTION else Decimal("100.5"),
        liquidity_score=Decimal("0.85"),
        order_flow_score=Decimal(of),
    )


def avwap(sid, confirmation=AvwapConfirmation.STRONG_BULLISH, t=1_002, score="0.84", failure=False):
    return AnchoredVwapEvent(
        event_type=EventType.ANCHORED_VWAP,
        source="test",
        venue=Venue.BINANCE_USDM,
        market_type=MarketType.PERPETUAL_FUTURES,
        symbol="BTCUSDT",
        event_time_ms=t,
        received_time_ms=t,
        anchor_name="sweep",
        anchor_type="sweep_event",
        anchor_time_ms=1_000,
        anchor_price=Decimal("99.5"),
        avwap=Decimal("99.9"),
        slope=Decimal("0.1"),
        distance_from_price_bps=Decimal("5"),
        confirmation=confirmation,
        confirmation_score=Decimal(score),
        is_reclaim=not failure,
        is_failure=failure,
        sweep_id=sid,
    )


def test_engine_emits_long_signal_after_avwap_confirmation():
    engine = SignalScorerEngine()
    engine.on_book(book())
    sw = sweep()
    assert engine.on_sweep(sw) == []
    out = engine.on_avwap(avwap(sw.sweep_id))
    assert len(out) == 1
    signal = out[0]
    assert signal.side == "long"
    assert signal.stop < signal.entry_candidate
    assert signal.final_score >= Decimal("0.72")
    assert signal.expected_net_return_bps > 0


def test_engine_rejects_mismatched_avwap_direction():
    engine = SignalScorerEngine()
    engine.on_book(book())
    sw = sweep()
    engine.on_sweep(sw)
    assert engine.on_avwap(avwap(sw.sweep_id, confirmation=AvwapConfirmation.STRONG_BEARISH)) == []
    assert "direction" in engine.last_rejections[sw.sweep_id][0]


def test_engine_suppresses_duplicate_signal():
    engine = SignalScorerEngine()
    engine.on_book(book())
    sw = sweep()
    engine.on_sweep(sw)
    assert len(engine.on_avwap(avwap(sw.sweep_id))) == 1
    assert engine.on_avwap(avwap(sw.sweep_id, t=1_003)) == []


def test_low_score_is_rejected():
    engine = SignalScorerEngine()
    engine.on_book(book())
    sw = sweep(of="0.2")
    engine.on_sweep(sw)
    assert engine.on_avwap(avwap(sw.sweep_id)) == []
    assert any("order-flow" in reason for reason in engine.last_rejections[sw.sweep_id])


def test_avwap_failure_is_rejected():
    engine = SignalScorerEngine()
    engine.on_book(book())
    sw = sweep()
    engine.on_sweep(sw)
    assert engine.on_avwap(avwap(sw.sweep_id, failure=True)) == []
    assert "failure" in engine.last_rejections[sw.sweep_id][0]
