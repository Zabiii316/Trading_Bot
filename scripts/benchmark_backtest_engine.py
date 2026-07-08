#!/usr/bin/env python3
from __future__ import annotations

from decimal import Decimal
from time import perf_counter
from uuid import uuid4

from trading_contracts.enums import EventType, MarketType, SweepOutcome, TradeSide, Venue
from trading_contracts.events import PriceLevel, ReconstructedBookEvent, SignalEvent
from trading_backtest.engine import EventDrivenBacktestEngine
from trading_backtest.models import BacktestConfig


def book(t: int, bid: str, ask: str) -> ReconstructedBookEvent:
    return ReconstructedBookEvent(
        event_type=EventType.RECONSTRUCTED_BOOK,
        source="benchmark",
        venue=Venue.BINANCE_USDM,
        market_type=MarketType.PERPETUAL_FUTURES,
        symbol="BTCUSDT",
        event_time_ms=t,
        received_time_ms=t,
        last_update_id=t,
        best_bid=PriceLevel(price=Decimal(bid), quantity=Decimal("100")),
        best_ask=PriceLevel(price=Decimal(ask), quantity=Decimal("100")),
        spread=Decimal(str(Decimal(ask) - Decimal(bid))),
        spread_bps=Decimal("1"),
        bid_depth_notional_10=Decimal("1000000"),
        ask_depth_notional_10=Decimal("1000000"),
        is_sequence_healthy=True,
    )


def signal(t: int, n: int) -> SignalEvent:
    return SignalEvent(
        event_type=EventType.SIGNAL,
        source="benchmark",
        venue=Venue.BINANCE_USDM,
        market_type=MarketType.PERPETUAL_FUTURES,
        symbol="BTCUSDT",
        event_time_ms=t,
        received_time_ms=t,
        signal_id=uuid4(),
        strategy_id="benchmark",
        side=TradeSide.LONG,
        outcome=SweepOutcome.BULLISH_REJECTION,
        entry_candidate=Decimal("100.00"),
        stop=Decimal("99.50"),
        target_1=Decimal("100.75"),
        target_2=Decimal("101.00"),
        liquidity_score=Decimal("0.8"),
        order_flow_score=Decimal("0.8"),
        avwap_score=Decimal("0.8"),
        regime_score=Decimal("0.7"),
        execution_score=Decimal("0.9"),
        final_score=Decimal("0.8"),
        expected_net_return_bps=Decimal("20"),
        expires_at_ms=t + 60_000,
        feature_snapshot_id=uuid4(),
        rationale=[f"benchmark-{n}"],
    )


def main() -> None:
    iterations = 50_000
    engine = EventDrivenBacktestEngine(BacktestConfig(latency_ms=0, fee_bps=0, slippage_bps=0))
    start = perf_counter()
    for i in range(iterations):
        t = 1_000 + i * 10
        engine.on_event(book(t, "100.00", "100.01"))
        if i % 1000 == 0:
            engine.on_event(signal(t + 1, i))
        engine.on_event(book(t + 2, "100.80", "100.81"))
    report = engine.finalize()
    elapsed = perf_counter() - start
    per_event_us = (elapsed / (iterations * 2 + iterations // 1000)) * 1_000_000
    print(f"{iterations:,} loop iterations")
    print(f"{report.summary.event_count:,} events processed")
    print(f"{report.summary.trade_count:,} trades closed")
    print(f"{per_event_us:.3f} microseconds per event")


if __name__ == "__main__":
    main()
