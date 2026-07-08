from __future__ import annotations

import sys
import time
from pathlib import Path
from decimal import Decimal
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.extend([str(ROOT / "libs/python"), str(ROOT / "services/live_execution/python")])

from trading_contracts.enums import OrderSide, OrderType, TimeInForce
from trading_live_execution.config import BinanceLiveExecutionConfig
from trading_live_execution.mapping import to_binance_order_params
from trading_live_execution.models import BinanceOrderRequest


def main() -> None:
    iterations = 50_000
    cfg = BinanceLiveExecutionConfig(api_key="k", api_secret="s")
    start = time.perf_counter()
    for i in range(iterations):
        req = BinanceOrderRequest(
            symbol="BTCUSDT",
            side=OrderSide.BUY if i % 2 == 0 else OrderSide.SELL,
            order_type=OrderType.MARKETABLE_LIMIT,
            time_in_force=TimeInForce.IOC,
            quantity=Decimal("0.01"),
            limit_price=Decimal("62000.5"),
            reduce_only=False,
            client_order_id=f"tb14-{uuid4().hex[:20]}",
        )
        to_binance_order_params(req, timestamp_ms=1_700_000_000_000 + i, config=cfg)
    elapsed = time.perf_counter() - start
    print(f"{iterations:,} order mappings")
    print(f"{elapsed / iterations * 1_000_000:.3f} microseconds per mapping")


if __name__ == "__main__":
    main()
