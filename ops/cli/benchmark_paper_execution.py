from __future__ import annotations

from decimal import Decimal
from time import perf_counter
from uuid import uuid4

from trading_contracts.enums import MarketType, RiskDecisionStatus, SweepOutcome, TradeSide, Venue
from trading_contracts.events import PriceLevel, ReconstructedBookEvent, RiskDecisionEvent, SignalEvent
from trading_paper_execution.engine import PaperExecutionEngine
from trading_paper_execution.models import PaperExecutionConfig


def main() -> None:
    engine = PaperExecutionEngine(PaperExecutionConfig(slippage_bps=0.0, fee_bps=0.0))
    now = 1_000
    book = ReconstructedBookEvent(
        source="bench", venue=Venue.BINANCE_USDM, market_type=MarketType.PERPETUAL_FUTURES, symbol="BTCUSDT",
        event_time_ms=now, received_time_ms=now, last_update_id=now,
        best_bid=PriceLevel(price=Decimal("100"), quantity=Decimal("100000")),
        best_ask=PriceLevel(price=Decimal("100.1"), quantity=Decimal("100000")),
        spread=Decimal("0.1"), spread_bps=Decimal("9.99"), bid_depth_notional_10=Decimal("10000000"),
        ask_depth_notional_10=Decimal("10010000"), is_sequence_healthy=True,
    )
    signals = []
    risks = []
    n = 5_000
    for i in range(n):
        s = SignalEvent(
            source="bench", venue=Venue.BINANCE_USDM, market_type=MarketType.PERPETUAL_FUTURES, symbol="BTCUSDT",
            event_time_ms=now+i, received_time_ms=now+i, strategy_id="bench", side=TradeSide.LONG,
            outcome=SweepOutcome.BULLISH_REJECTION, entry_candidate=Decimal("100.1"), stop=Decimal("99"),
            target_1=Decimal("102"), liquidity_score=Decimal("0.8"), order_flow_score=Decimal("0.8"), avwap_score=Decimal("0.8"),
            regime_score=Decimal("0.8"), execution_score=Decimal("0.8"), final_score=Decimal("0.8"), expected_net_return_bps=Decimal("20"),
            expires_at_ms=now+i+100_000, feature_snapshot_id=uuid4(),
        )
        r = RiskDecisionEvent(
            source="risk", venue=s.venue, market_type=s.market_type, symbol=s.symbol, event_time_ms=now+i, received_time_ms=now+i,
            signal_id=s.signal_id, status=RiskDecisionStatus.APPROVED, approved_quantity=Decimal("0.001"), max_loss_quote=Decimal("1"),
            account_equity_quote=Decimal("100000"), risk_fraction=Decimal("0.001"),
        )
        signals.append(s); risks.append(r)
    t0 = perf_counter()
    emitted = 0
    for i, (s, r) in enumerate(zip(signals, risks, strict=True)):
        book.event_time_ms = now + i  # type: ignore[misc]
        book.received_time_ms = now + i  # type: ignore[misc]
        book.last_update_id = now + i  # type: ignore[misc]
        order, reasons = engine.submit(signal=s, risk_decision=r, book=book, event_time_ms=now+i)
        if order is not None:
            emitted += 1
            emitted += len(engine.on_book(book))
    elapsed = perf_counter() - t0
    print(f"{n:,} approved paper orders submitted")
    print(f"{emitted:,} order/fill lifecycle events emitted")
    print(f"{(elapsed / n) * 1_000_000:.3f} microseconds per submit+book cycle")


if __name__ == "__main__":
    main()
