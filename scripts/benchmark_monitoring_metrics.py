#!/usr/bin/env python3
from __future__ import annotations

from decimal import Decimal
from time import perf_counter

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for rel in [
    "libs/python",
    "services/monitoring/python",
]:
    sys.path.insert(0, str(ROOT / rel))

from trading_contracts.enums import MarketType, Venue
from trading_contracts.events import OrderFlowFeatureEvent
from trading_monitoring.metrics import TradingMetrics


def main() -> None:
    metrics = TradingMetrics()
    iterations = 50_000
    event = OrderFlowFeatureEvent(
        source="benchmark",
        venue=Venue.BINANCE_USDM,
        market_type=MarketType.PERPETUAL_FUTURES,
        symbol="BTCUSDT",
        event_time_ms=1_000,
        received_time_ms=1_001,
        window_ms=1_000,
        trade_count=8,
        buy_volume=Decimal("4"),
        sell_volume=Decimal("2"),
        delta=Decimal("2"),
        normalized_delta=Decimal("0.33333333"),
        cumulative_volume_delta=Decimal("42"),
        queue_imbalance_l1=Decimal("0.21"),
        absorption_ratio=Decimal("3.2"),
    )
    started = perf_counter()
    for _ in range(iterations):
        metrics.observe_event(event)
    elapsed = perf_counter() - started
    us = elapsed / iterations * 1_000_000
    print(f"{iterations:,} metric observations")
    print(f"{us:.3f} microseconds per observation")


if __name__ == "__main__":
    main()
