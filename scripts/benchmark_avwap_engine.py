from __future__ import annotations

from decimal import Decimal
from time import perf_counter
from uuid import uuid4
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for rel in ["libs/python", "services/avwap/python"]:
    path = str(ROOT / rel)
    if path not in sys.path:
        sys.path.insert(0, path)

from trading_contracts.enums import EventType, MarketType, Venue
from trading_contracts.events import LiquidityLevelEvent, RawAggTradeEvent
from trading_avwap.engine import AnchoredVwapEngine, AvwapEngineConfig


def main() -> None:
    engine = AnchoredVwapEngine(AvwapEngineConfig(max_active_anchors_per_symbol=32, emit_every_trade=False))
    base_t = 1_783_000_000_000
    for i in range(16):
        price = Decimal(str(60_000 + i * 50))
        engine.on_liquidity_level(
            LiquidityLevelEvent(
                event_type=EventType.LIQUIDITY_LEVEL,
                source="bench",
                venue=Venue.BINANCE_USDM,
                market_type=MarketType.PERPETUAL_FUTURES,
                symbol="BTCUSDT",
                event_time_ms=base_t,
                received_time_ms=base_t,
                level_id=uuid4(),
                level_type="swing_high",
                price=price,
                zone_low=price - Decimal("1"),
                zone_high=price + Decimal("1"),
                quality_score=Decimal("0.75"),
                touches=3,
                first_seen_ms=base_t,
                last_seen_ms=base_t,
            )
        )
    n = 50_000
    start = perf_counter()
    emitted = 0
    for i in range(n):
        t = base_t + i
        price = Decimal(str(60_000 + (i % 100) * 0.1))
        event = RawAggTradeEvent(
            event_type=EventType.RAW_AGG_TRADE,
            source="bench",
            venue=Venue.BINANCE_USDM,
            market_type=MarketType.PERPETUAL_FUTURES,
            symbol="BTCUSDT",
            event_time_ms=t,
            received_time_ms=t,
            agg_trade_id=i,
            price=price,
            quantity=Decimal("0.01"),
            first_trade_id=i,
            last_trade_id=i,
            trade_time_ms=t,
            is_buyer_maker=False,
            aggressor_side="buy",
        )
        emitted += len(engine.on_trade(event))
    elapsed = perf_counter() - start
    print(f"iterations={n} emitted={emitted} us_per_trade={(elapsed/n)*1_000_000:.3f}")


if __name__ == "__main__":
    main()
