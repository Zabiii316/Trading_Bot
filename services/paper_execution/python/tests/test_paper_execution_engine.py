from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

from trading_contracts.enums import MarketType, RiskDecisionStatus, SweepOutcome, TradeSide, Venue, OrderStatus
from trading_contracts.events import PriceLevel, ReconstructedBookEvent, RiskDecisionEvent, SignalEvent
from trading_paper_execution.engine import PaperExecutionEngine
from trading_paper_execution.models import CancelReason, PaperExecutionConfig


def _book(t: int = 1_000, bid: str = "100.00", ask: str = "100.10", bid_qty: str = "5", ask_qty: str = "5") -> ReconstructedBookEvent:
    return ReconstructedBookEvent(
        source="test",
        venue=Venue.BINANCE_USDM,
        market_type=MarketType.PERPETUAL_FUTURES,
        symbol="BTCUSDT",
        event_time_ms=t,
        received_time_ms=t,
        last_update_id=t,
        best_bid=PriceLevel(price=Decimal(bid), quantity=Decimal(bid_qty)),
        best_ask=PriceLevel(price=Decimal(ask), quantity=Decimal(ask_qty)),
        spread=Decimal(ask) - Decimal(bid),
        spread_bps=((Decimal(ask) - Decimal(bid)) / Decimal(ask)) * Decimal("10000"),
        bid_depth_notional_10=Decimal(bid) * Decimal(bid_qty),
        ask_depth_notional_10=Decimal(ask) * Decimal(ask_qty),
        book_checksum="x",
        is_sequence_healthy=True,
    )


def _signal(side: TradeSide = TradeSide.LONG) -> SignalEvent:
    entry = Decimal("100.10") if side == TradeSide.LONG else Decimal("100.00")
    stop = Decimal("99.00") if side == TradeSide.LONG else Decimal("101.00")
    target = Decimal("102.00") if side == TradeSide.LONG else Decimal("98.00")
    return SignalEvent(
        source="test",
        venue=Venue.BINANCE_USDM,
        market_type=MarketType.PERPETUAL_FUTURES,
        symbol="BTCUSDT",
        event_time_ms=900,
        received_time_ms=900,
        strategy_id="sweep_v1",
        side=side,
        outcome=SweepOutcome.BULLISH_REJECTION if side == TradeSide.LONG else SweepOutcome.BEARISH_REJECTION,
        entry_candidate=entry,
        stop=stop,
        target_1=target,
        target_2=None,
        liquidity_score=Decimal("0.8"),
        order_flow_score=Decimal("0.8"),
        avwap_score=Decimal("0.8"),
        regime_score=Decimal("0.8"),
        execution_score=Decimal("0.8"),
        final_score=Decimal("0.8"),
        expected_net_return_bps=Decimal("20"),
        expires_at_ms=10_000,
        feature_snapshot_id=uuid4(),
        rationale=["test"],
    )


def _risk(signal: SignalEvent, qty: str = "1") -> RiskDecisionEvent:
    return RiskDecisionEvent(
        source="risk_engine",
        venue=signal.venue,
        market_type=signal.market_type,
        symbol=signal.symbol,
        event_time_ms=950,
        received_time_ms=950,
        signal_id=signal.signal_id,
        status=RiskDecisionStatus.APPROVED,
        approved_quantity=Decimal(qty),
        max_loss_quote=Decimal("100"),
        account_equity_quote=Decimal("100000"),
        risk_fraction=Decimal("0.0025"),
    )


def test_submit_approved_risk_decision_creates_order() -> None:
    engine = PaperExecutionEngine()
    signal = _signal()
    order, reasons = engine.submit(signal=signal, risk_decision=_risk(signal), book=_book())
    assert reasons == ()
    assert order is not None
    assert order.status == "acknowledged"
    assert order.signal_id == signal.signal_id
    assert len(engine.orders) == 1


def test_rejects_unapproved_risk_decision() -> None:
    engine = PaperExecutionEngine()
    signal = _signal()
    risk = _risk(signal)
    risk.status = "rejected"  # type: ignore[misc]
    order, reasons = engine.submit(signal=signal, risk_decision=risk, book=_book())
    assert order is None
    assert "risk_not_approved" in reasons


def test_on_book_fills_marketable_long_order_and_updates_position() -> None:
    engine = PaperExecutionEngine(PaperExecutionConfig(slippage_bps=0.0, fee_bps=0.0))
    signal = _signal(TradeSide.LONG)
    order, reasons = engine.submit(signal=signal, risk_decision=_risk(signal), book=_book(t=1_000))
    assert order is not None and reasons == ()
    events = engine.on_book(_book(t=1_001, bid="100.00", ask="100.10", ask_qty="2"))
    fills = [event for event in events if event.event_type == "execution.fill"]
    assert len(fills) == 1
    assert fills[0].fill_price == Decimal("100.1")
    assert engine.reconcile(event_time_ms=1_001).is_healthy
    assert len(engine.positions) == 1


def test_partial_fill_when_top_level_size_is_lower_than_order_quantity() -> None:
    engine = PaperExecutionEngine(PaperExecutionConfig(slippage_bps=0.0, fee_bps=0.0, allow_partial_fills=True))
    signal = _signal(TradeSide.LONG)
    order_event, _ = engine.submit(signal=signal, risk_decision=_risk(signal, qty="3"), book=_book(t=1_000, ask_qty="1"))
    assert order_event is not None
    events = engine.on_book(_book(t=1_001, ask_qty="1"))
    lifecycle_updates = [event for event in events if event.event_type == "execution.order"]
    assert lifecycle_updates[-1].status == "partially_filled"
    order = next(iter(engine.orders.values()))
    assert 0 < order.remaining_quantity < 3


def test_order_expires_and_is_cancelled() -> None:
    engine = PaperExecutionEngine(PaperExecutionConfig(order_ttl_ms=10, fill_latency_ms=0))
    signal = _signal(TradeSide.LONG)
    order_event, _ = engine.submit(signal=signal, risk_decision=_risk(signal), book=_book(t=1_000))
    assert order_event is not None
    # move market away so not fill, then pass TTL
    events = engine.on_book(_book(t=1_020, bid="99.00", ask="101.00"))
    cancels = [event for event in events if event.event_type == "execution.order"]
    assert cancels[-1].status == "cancelled"


def test_cancel_all_cancels_open_orders() -> None:
    engine = PaperExecutionEngine(PaperExecutionConfig(fill_latency_ms=10_000))
    signal = _signal()
    engine.submit(signal=signal, risk_decision=_risk(signal), book=_book())
    events = engine.cancel_all(reason=CancelReason.KILL_SWITCH, event_time_ms=2_000)
    assert len(events) == 1
    assert events[0].status == "cancelled"


def test_rejects_duplicate_signal() -> None:
    engine = PaperExecutionEngine()
    signal = _signal()
    risk = _risk(signal)
    engine.submit(signal=signal, risk_decision=risk, book=_book())
    order, reasons = engine.submit(signal=signal, risk_decision=risk, book=_book(t=1_100))
    assert order is None
    assert "duplicate_signal" in reasons
