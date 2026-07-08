#!/usr/bin/env python3
from __future__ import annotations

import time
from decimal import Decimal
from uuid import uuid4

from trading_contracts.enums import EventType, LiquidityLevelType, MarketType, Venue
from trading_contracts.events import LiquidityLevelEvent, PriceLevel, ReconstructedBookEvent
from trading_features.book_view import BookView
from trading_sweep.state_machine import LiquiditySweepStateMachine, SweepEngineConfig


def level(i: int) -> LiquidityLevelEvent:
    p = Decimal(str(60_000 + i * 10))
    return LiquidityLevelEvent(
        event_type=EventType.LIQUIDITY_LEVEL,
        source="benchmark",
        venue=Venue.BINANCE_USDM,
        market_type=MarketType.PERPETUAL_FUTURES,
        symbol="BTCUSDT",
        event_time_ms=1_000,
        received_time_ms=1_000,
        level_id=uuid4(),
        level_type=LiquidityLevelType.EQUAL_HIGHS,
        price=p,
        zone_low=p - Decimal("1"),
        zone_high=p + Decimal("1"),
        quality_score=Decimal("0.80"),
        touches=3,
        first_seen_ms=1,
        last_seen_ms=1_000,
    )


def book(price: float, t: int) -> BookView:
    event = ReconstructedBookEvent(
        event_type=EventType.RECONSTRUCTED_BOOK,
        source="benchmark",
        venue=Venue.BINANCE_USDM,
        market_type=MarketType.PERPETUAL_FUTURES,
        symbol="BTCUSDT",
        event_time_ms=t,
        received_time_ms=t,
        last_update_id=t,
        best_bid=PriceLevel(price=Decimal(str(price - 0.05)), quantity=Decimal("10")),
        best_ask=PriceLevel(price=Decimal(str(price + 0.05)), quantity=Decimal("10")),
        spread=Decimal("0.10"),
        spread_bps=Decimal("0.016"),
        bid_depth_notional_10=Decimal("100000"),
        ask_depth_notional_10=Decimal("100000"),
        is_sequence_healthy=True,
    )
    return BookView.from_reconstructed(event)


def main() -> int:
    engine = LiquiditySweepStateMachine(SweepEngineConfig())
    for i in range(100):
        engine.on_liquidity_level(level(i))
    iterations = 50_000
    start = time.perf_counter_ns()
    emitted = 0
    for i in range(iterations):
        emitted += len(engine.on_book(book(60_000 + (i % 100) * 10 - 2, 2_000 + i)))
    elapsed_ns = time.perf_counter_ns() - start
    per_update_us = elapsed_ns / iterations / 1_000
    print(f"{iterations:,} sweep-engine updates")
    print(f"{emitted:,} sweep events emitted")
    print(f"{per_update_us:.3f} microseconds per update with 100 active levels")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
