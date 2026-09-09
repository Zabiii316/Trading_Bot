#!/usr/bin/env python3
from __future__ import annotations

import time
from decimal import Decimal
from uuid import uuid4

from trading_contracts.enums import MarketType, TradeSide, Venue
from trading_contracts.events import SignalEvent
from trading_risk.engine import RiskEngine
from trading_risk.models import AccountState, RiskLimits, RiskRequest


def make_signal(i: int) -> SignalEvent:
    return SignalEvent(
        source="benchmark",
        venue=Venue.BINANCE_USDM,
        market_type=MarketType.PERPETUAL_FUTURES,
        symbol="BTCUSDT",
        event_time_ms=1_000 + i,
        received_time_ms=1_000 + i,
        strategy_id="sweep_orderflow_avwap_v1",
        side=TradeSide.LONG,
        outcome="bullish_rejection",
        entry_candidate=Decimal("100"),
        stop=Decimal("99"),
        target_1=Decimal("102"),
        liquidity_score=Decimal("0.8"),
        order_flow_score=Decimal("0.8"),
        avwap_score=Decimal("0.8"),
        regime_score=Decimal("0.7"),
        execution_score=Decimal("0.8"),
        final_score=Decimal("0.78"),
        expected_net_return_bps=Decimal("20"),
        expires_at_ms=120_000 + i,
        feature_snapshot_id=uuid4(),
    )


def main() -> None:
    iterations = 50_000
    engine = RiskEngine(RiskLimits(quantity_step=0.001))
    account = AccountState(equity_quote=100_000.0, available_margin_quote=90_000.0, peak_equity_quote=100_000.0)
    signals = [make_signal(i) for i in range(iterations)]
    start = time.perf_counter()
    approved = 0
    for i, signal in enumerate(signals):
        detail, _ = engine.evaluate(RiskRequest(signal=signal, account=account, event_time_ms=2_000 + i, mark_price=100.0))
        if detail.approved:
            approved += 1
    elapsed = time.perf_counter() - start
    print(f"{iterations:,} risk checks")
    print(f"{approved:,} approved")
    print(f"{elapsed / iterations * 1_000_000:.3f} microseconds per risk check")


if __name__ == "__main__":
    main()
