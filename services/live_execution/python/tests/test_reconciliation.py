from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

import pytest

from trading_contracts.enums import MarketType, OrderStatus, RiskDecisionStatus, SweepOutcome, TradeSide, Venue
from trading_contracts.events import RiskDecisionEvent, SignalEvent
from trading_live_execution.config import BinanceLiveExecutionConfig
from trading_live_execution.engine import BinanceLiveExecutionAdapter
from trading_live_execution.models import BinanceOrderAck, BinanceOrderStatus, ExchangeOrderSnapshot, ExchangePositionSnapshot
from trading_live_execution.reconciliation import BinanceReconciler


class ReconcileClient:
    def __init__(self, *, include_local_on_exchange: bool) -> None:
        self.config = BinanceLiveExecutionConfig(api_key="key", api_secret="secret", testnet=True, enable_live_trading=True)
        self.include_local_on_exchange = include_local_on_exchange
        self.client_id = ""

    def timestamp_ms(self) -> int:
        return 1_700_000_000_000

    async def place_order(self, params):
        self.client_id = dict(params)["newClientOrderId"]
        return BinanceOrderAck("BTCUSDT", "1", self.client_id, BinanceOrderStatus.NEW, {"status": "NEW", "clientOrderId": self.client_id, "orderId": 1})

    async def open_orders(self, *, symbol=None):
        if not self.include_local_on_exchange:
            return []
        return [
            ExchangeOrderSnapshot(
                symbol="BTCUSDT",
                venue_order_id="1",
                client_order_id=self.client_id,
                status=BinanceOrderStatus.NEW,
                side="BUY",
                order_type="LIMIT",
                original_quantity=Decimal("0.01"),
                executed_quantity=Decimal("0"),
                average_price=Decimal("0"),
                reduce_only=False,
                update_time_ms=1,
                raw={},
            )
        ]

    async def position_risk(self, *, symbol=None):
        return [
            ExchangePositionSnapshot(
                symbol="BTCUSDT",
                position_amount=Decimal("0"),
                entry_price=Decimal("0"),
                mark_price=Decimal("62000"),
                unrealized_pnl=Decimal("0"),
            )
        ]


def make_signal() -> SignalEvent:
    now = 1_700_000_000_000
    return SignalEvent(
        source="signals",
        venue=Venue.BINANCE_USDM,
        market_type=MarketType.PERPETUAL_FUTURES,
        symbol="BTCUSDT",
        event_time_ms=now,
        received_time_ms=now,
        strategy_id="sweep_avwap_v1",
        side=TradeSide.LONG,
        outcome=SweepOutcome.BULLISH_REJECTION,
        entry_candidate=Decimal("62000"),
        stop=Decimal("61900"),
        target_1=Decimal("62200"),
        liquidity_score=Decimal("0.8"),
        order_flow_score=Decimal("0.8"),
        avwap_score=Decimal("0.8"),
        regime_score=Decimal("0.7"),
        execution_score=Decimal("0.9"),
        final_score=Decimal("0.8"),
        expected_net_return_bps=Decimal("15"),
        expires_at_ms=now + 60_000,
        feature_snapshot_id=uuid4(),
    )


def make_risk(signal: SignalEvent) -> RiskDecisionEvent:
    return RiskDecisionEvent(
        source="risk",
        venue=Venue.BINANCE_USDM,
        market_type=MarketType.PERPETUAL_FUTURES,
        symbol=signal.symbol,
        event_time_ms=signal.event_time_ms,
        received_time_ms=signal.event_time_ms,
        signal_id=signal.signal_id,
        status=RiskDecisionStatus.APPROVED,
        approved_quantity=Decimal("0.01"),
        max_loss_quote=Decimal("1"),
        account_equity_quote=Decimal("1000"),
        risk_fraction=Decimal("0.001"),
    )


@pytest.mark.asyncio
async def test_reconciliation_healthy_when_exchange_matches_local_open_order() -> None:
    client = ReconcileClient(include_local_on_exchange=True)
    adapter = BinanceLiveExecutionAdapter(client.config, client)  # type: ignore[arg-type]
    signal = make_signal()
    await adapter.submit_entry(signal=signal, risk_decision=make_risk(signal), event_time_ms=signal.event_time_ms)
    report = await BinanceReconciler(adapter, client).reconcile(event_time_ms=signal.event_time_ms, symbol="BTCUSDT")  # type: ignore[arg-type]
    assert report.is_healthy
    assert report.local_open_order_count == 1
    assert report.exchange_open_order_count == 1


@pytest.mark.asyncio
async def test_reconciliation_reports_missing_exchange_order() -> None:
    client = ReconcileClient(include_local_on_exchange=False)
    adapter = BinanceLiveExecutionAdapter(client.config, client)  # type: ignore[arg-type]
    signal = make_signal()
    order, _ = await adapter.submit_entry(signal=signal, risk_decision=make_risk(signal), event_time_ms=signal.event_time_ms)
    assert order is not None
    report = await BinanceReconciler(adapter, client).reconcile(event_time_ms=signal.event_time_ms, symbol="BTCUSDT")  # type: ignore[arg-type]
    assert not report.is_healthy
    assert any("local_open_missing_on_exchange" in d for d in report.discrepancies)
