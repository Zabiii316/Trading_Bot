from __future__ import annotations

from decimal import Decimal
import time
from uuid import uuid4
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
for rel in ["libs/python", "services/signals/python"]:
    p = str(ROOT / rel)
    if p not in sys.path:
        sys.path.insert(0, p)

from trading_contracts.enums import AvwapConfirmation, EventType, MarketType, SweepOutcome, SweepState, Venue
from trading_contracts.events import AnchoredVwapEvent, LiquiditySweepEvent, PriceLevel, ReconstructedBookEvent
from trading_signals.engine import SignalScorerEngine, SignalEngineConfig
from trading_signals.scoring import SignalScoringConfig


def main() -> None:
    engine = SignalScorerEngine(SignalEngineConfig(stale_book_ms=1_000_000_000, stale_avwap_ms=1_000_000_000, stale_flow_ms=1_000_000_000, scoring=SignalScoringConfig(signal_ttl_ms=60_000)))
    symbol = "BTCUSDT"
    book = ReconstructedBookEvent(
        event_type=EventType.RECONSTRUCTED_BOOK,
        source="bench",
        venue=Venue.BINANCE_USDM,
        market_type=MarketType.PERPETUAL_FUTURES,
        symbol=symbol,
        event_time_ms=1_000,
        received_time_ms=1_000,
        last_update_id=1,
        best_bid=PriceLevel(price=Decimal("100.00"), quantity=Decimal("100")),
        best_ask=PriceLevel(price=Decimal("100.01"), quantity=Decimal("100")),
        spread=Decimal("0.01"),
        spread_bps=Decimal("1"),
        bid_depth_notional_10=Decimal("100000"),
        ask_depth_notional_10=Decimal("100000"),
        is_sequence_healthy=True,
    )
    engine.on_book(book)
    iterations = 50_000
    t0 = time.perf_counter_ns()
    emitted = 0
    for i in range(iterations):
        sid = uuid4()
        sweep = LiquiditySweepEvent(
            event_type=EventType.LIQUIDITY_SWEEP,
            source="bench",
            venue=Venue.BINANCE_USDM,
            market_type=MarketType.PERPETUAL_FUTURES,
            symbol=symbol,
            event_time_ms=1_001 + i,
            received_time_ms=1_001 + i,
            sweep_id=sid,
            level_id=uuid4(),
            state=SweepState.ORDER_FLOW_CONFIRMED,
            outcome=SweepOutcome.BULLISH_REJECTION,
            level_price=Decimal("100"),
            sweep_extreme_price=Decimal("99.5"),
            liquidity_score=Decimal("0.85"),
            order_flow_score=Decimal("0.8"),
        )
        avwap = AnchoredVwapEvent(
            event_type=EventType.ANCHORED_VWAP,
            source="bench",
            venue=Venue.BINANCE_USDM,
            market_type=MarketType.PERPETUAL_FUTURES,
            symbol=symbol,
            event_time_ms=1_002 + i,
            received_time_ms=1_002 + i,
            anchor_name="sweep",
            anchor_type="sweep_event",
            anchor_time_ms=1_000,
            anchor_price=Decimal("99.5"),
            avwap=Decimal("99.9"),
            slope=Decimal("0.1"),
            distance_from_price_bps=Decimal("5"),
            confirmation=AvwapConfirmation.STRONG_BULLISH,
            confirmation_score=Decimal("0.82"),
            is_reclaim=True,
            sweep_id=sid,
        )
        engine.on_sweep(sweep)
        emitted += len(engine.on_avwap(avwap))
    dt = time.perf_counter_ns() - t0
    print(f"iterations={iterations}")
    print(f"emitted={emitted}")
    print(f"microseconds_per_candidate={dt / iterations / 1000:.3f}")


if __name__ == "__main__":
    main()
