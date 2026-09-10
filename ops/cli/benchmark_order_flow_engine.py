#!/usr/bin/env python
from __future__ import annotations

import time

from trading_features.book_view import BookView
from trading_features.engine import OrderFlowEngine


def main() -> None:
    engine = OrderFlowEngine()
    iterations = 50_000
    start = time.perf_counter_ns()
    for i in range(iterations):
        base = 62_000.0 + (i % 10) * 0.1
        book = BookView.from_levels(
            symbol="BTCUSDT",
            venue="binance_usdm",
            market_type="perpetual_futures",
            event_time_ms=1_000_000 + i,
            received_time_ms=1_000_000 + i,
            last_update_id=i,
            bids=[(base - j * 0.1, 10.0 + j) for j in range(20)],
            asks=[(base + 0.1 + j * 0.1, 8.0 + j) for j in range(20)],
        )
        engine.on_book(book)
        engine.snapshot_features()
    elapsed_ns = time.perf_counter_ns() - start
    per_event_us = elapsed_ns / iterations / 1_000
    print(f"iterations={iterations} elapsed_ms={elapsed_ns/1_000_000:.2f} per_book_feature_us={per_event_us:.3f}")


if __name__ == "__main__":
    main()
