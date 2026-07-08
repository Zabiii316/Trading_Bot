from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.extend([str(ROOT / "libs" / "python"), str(ROOT / "services" / "liquidity" / "python")])

from trading_contracts.enums import MarketType, Venue  # noqa: E402
from trading_liquidity.engine import LiquidityLevelEngine  # noqa: E402
from trading_liquidity.models import Bar  # noqa: E402


def main() -> int:
    engine = LiquidityLevelEngine()
    base_ms = 1_783_000_000_000
    n = 50_000
    start = time.perf_counter_ns()
    events = 0
    price = 62_000.0
    for i in range(n):
        # Deterministic oscillating stream to trigger pivots and round levels.
        price += ((i % 17) - 8) * 0.7
        bar = Bar(
            symbol="BTCUSDT",
            venue=Venue.BINANCE_USDM,
            market_type=MarketType.PERPETUAL_FUTURES,
            start_time_ms=base_ms + i * 60_000,
            end_time_ms=base_ms + (i + 1) * 60_000 - 1,
            open=price - 1.2,
            high=price + (i % 5) + 2.0,
            low=price - (i % 7) - 2.0,
            close=price,
            volume=100 + (i % 100),
        )
        events += len(engine.update(bar))
    elapsed_ns = time.perf_counter_ns() - start
    us = elapsed_ns / n / 1000
    print(f"{n:,} bar iterations")
    print(f"{events:,} liquidity events emitted")
    print(f"{us:.3f} microseconds per bar update")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
