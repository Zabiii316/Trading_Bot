from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

from trading_contracts.enums import MarketType, RiskDecisionStatus, SweepOutcome, TradeSide, Venue
from trading_contracts.events import PriceLevel, ReconstructedBookEvent, RiskDecisionEvent, SignalEvent
from trading_paper_execution.engine import PaperExecutionEngine
from trading_paper_execution.models import PaperExecutionConfig


def test_hot_path_processes_many_book_updates() -> None:
    engine = PaperExecutionEngine(PaperExecutionConfig(slippage_bps=0.0, fee_bps=0.0))
    now = 1_000
    signal = SignalEvent(
        source="test", venue=Venue.BINANCE_USDM, market_type=MarketType.PERPETUAL_FUTURES, symbol="BTCUSDT",
        event_time_ms=now, received_time_ms=now, strategy_id="bench", side=TradeSide.LONG,
        outcome=SweepOutcome.BULLISH_REJECTION, entry_candidate=Decimal("100.1"), stop=Decimal("99"),
        target_1=Decimal("102"), liquidity_score=Decimal("0.8"), order_flow_score=Decimal("0.8"),
        avwap_score=Decimal("0.8"), regime_score=Decimal("0.8"), execution_score=Decimal("0.8"), final_score=Decimal("0.8"),
        expected_net_return_bps=Decimal("20"), expires_at_ms=100_000, feature_snapshot_id=uuid4(),
    )
    risk = RiskDecisionEvent(
        source="risk", venue=signal.venue, market_type=signal.market_type, symbol=signal.symbol, event_time_ms=now,
        received_time_ms=now, signal_id=signal.signal_id, status=RiskDecisionStatus.APPROVED, approved_quantity=Decimal("1"),
        max_loss_quote=Decimal("1"), account_equity_quote=Decimal("100000"), risk_fraction=Decimal("0.001"),
    )
    book = ReconstructedBookEvent(
        source="test", venue=Venue.BINANCE_USDM, market_type=MarketType.PERPETUAL_FUTURES, symbol="BTCUSDT",
        event_time_ms=now, received_time_ms=now, last_update_id=now,
        best_bid=PriceLevel(price=Decimal("100"), quantity=Decimal("1")),
        best_ask=PriceLevel(price=Decimal("100.1"), quantity=Decimal("1")),
        spread=Decimal("0.1"), spread_bps=Decimal("9.99"), bid_depth_notional_10=Decimal("100"),
        ask_depth_notional_10=Decimal("100.1"), is_sequence_healthy=True,
    )
    engine.submit(signal=signal, risk_decision=risk, book=book)
    emitted = 0
    for i in range(1000):
        book.event_time_ms = now + i + 1  # type: ignore[misc]
        book.received_time_ms = now + i + 1  # type: ignore[misc]
        book.last_update_id = now + i + 1  # type: ignore[misc]
        emitted += len(engine.on_book(book))
    assert emitted >= 1
