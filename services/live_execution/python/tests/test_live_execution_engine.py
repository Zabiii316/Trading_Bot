from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

import pytest

from trading_contracts.enums import (
    EventType,
    KillSwitchLevel,
    MarketType,
    OrderSide,
    OrderStatus,
    RiskDecisionStatus,
    SweepOutcome,
    TradeSide,
    Venue,
)
from trading_contracts.events import KillSwitchEvent, RiskDecisionEvent, SignalEvent
from trading_live_execution.config import BinanceLiveExecutionConfig
from trading_live_execution.engine import BinanceLiveExecutionAdapter
from trading_live_execution.models import BinanceOrderAck, BinanceOrderStatus, ExchangeOrderSnapshot


class FakeClient:
    def __init__(self) -> None:
        self.config = BinanceLiveExecutionConfig(api_key="key", api_secret="secret", testnet=True, enable_live_trading=True)
        self.placed_params = []
        self.cancelled = []
        self.now = 1_700_000_000_000

    def timestamp_ms(self) -> int:
        return self.now

    async def place_order(self, params):
        self.placed_params.append(dict(params))
        return BinanceOrderAck(
            symbol=dict(params)["symbol"],
            venue_order_id="12345",
            client_order_id=dict(params)["newClientOrderId"],
            status=BinanceOrderStatus.NEW,
            raw={"symbol": dict(params)["symbol"], "orderId": 12345, "clientOrderId": dict(params)["newClientOrderId"], "status": "NEW"},
        )

    async def cancel_order(self, *, symbol, orig_client_order_id=None, order_id=None):
        self.cancelled.append((symbol, orig_client_order_id, order_id))
        return ExchangeOrderSnapshot(
            symbol=symbol,
            venue_order_id="12345",
            client_order_id=orig_client_order_id or "",
            status=BinanceOrderStatus.CANCELED,
            side="BUY",
            order_type="LIMIT",
            original_quantity=Decimal("0.01"),
            executed_quantity=Decimal("0"),
            average_price=Decimal("0"),
            reduce_only=False,
            update_time_ms=self.now,
            raw={"symbol": symbol, "orderId": 12345, "clientOrderId": orig_client_order_id, "status": "CANCELED"},
        )

    async def query_order(self, *, symbol, orig_client_order_id=None, order_id=None):
        return ExchangeOrderSnapshot(
            symbol=symbol,
            venue_order_id="12345",
            client_order_id=orig_client_order_id or "",
            status=BinanceOrderStatus.FILLED,
            side="BUY",
            order_type="LIMIT",
            original_quantity=Decimal("0.01"),
            executed_quantity=Decimal("0.01"),
            average_price=Decimal("62000"),
            reduce_only=False,
            update_time_ms=self.now,
            raw={"symbol": symbol, "status": "FILLED"},
        )


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
        target_2=Decimal("62400"),
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


def make_risk(signal: SignalEvent, status: RiskDecisionStatus = RiskDecisionStatus.APPROVED) -> RiskDecisionEvent:
    now = signal.event_time_ms
    return RiskDecisionEvent(
        source="risk",
        venue=Venue.BINANCE_USDM,
        market_type=MarketType.PERPETUAL_FUTURES,
        symbol=signal.symbol,
        event_time_ms=now,
        received_time_ms=now,
        signal_id=signal.signal_id,
        status=status,
        approved_quantity=Decimal("0.01") if status == RiskDecisionStatus.APPROVED else Decimal("0"),
        max_loss_quote=Decimal("1"),
        account_equity_quote=Decimal("1000"),
        risk_fraction=Decimal("0.001"),
        rejection_reasons=["test"] if status == RiskDecisionStatus.REJECTED else [],
    )


@pytest.mark.asyncio
async def test_submit_entry_places_acknowledged_order() -> None:
    client = FakeClient()
    adapter = BinanceLiveExecutionAdapter(client.config, client)  # type: ignore[arg-type]
    signal = make_signal()
    risk = make_risk(signal)
    order, reasons = await adapter.submit_entry(signal=signal, risk_decision=risk, event_time_ms=signal.event_time_ms)
    assert reasons == ()
    assert order is not None
    assert order.status == OrderStatus.ACKNOWLEDGED
    assert order.venue_order_id == "12345"
    assert client.placed_params[0]["type"] == "LIMIT"
    assert client.placed_params[0]["timeInForce"] == "IOC"


@pytest.mark.asyncio
async def test_submit_entry_rejects_non_approved_risk() -> None:
    client = FakeClient()
    adapter = BinanceLiveExecutionAdapter(client.config, client)  # type: ignore[arg-type]
    signal = make_signal()
    risk = make_risk(signal, RiskDecisionStatus.REJECTED)
    order, reasons = await adapter.submit_entry(signal=signal, risk_decision=risk, event_time_ms=signal.event_time_ms)
    assert order is None
    assert "risk_not_approved" in reasons
    assert not client.placed_params


@pytest.mark.asyncio
async def test_live_trading_disabled_blocks_mainnet_submissions() -> None:
    client = FakeClient()
    cfg = BinanceLiveExecutionConfig(api_key="key", api_secret="secret", testnet=False, enable_live_trading=False)
    adapter = BinanceLiveExecutionAdapter(cfg, client)  # type: ignore[arg-type]
    signal = make_signal()
    risk = make_risk(signal)
    order, reasons = await adapter.submit_entry(signal=signal, risk_decision=risk, event_time_ms=signal.event_time_ms)
    assert order is None
    assert "live_trading_disabled" in reasons


@pytest.mark.asyncio
async def test_kill_switch_blocks_new_entries() -> None:
    client = FakeClient()
    adapter = BinanceLiveExecutionAdapter(client.config, client)  # type: ignore[arg-type]
    signal = make_signal()
    adapter.set_kill_switch(
        KillSwitchEvent(
            source="risk",
            venue=Venue.BINANCE_USDM,
            market_type=MarketType.PERPETUAL_FUTURES,
            symbol=signal.symbol,
            event_time_ms=signal.event_time_ms,
            received_time_ms=signal.event_time_ms,
            level=KillSwitchLevel.HARD_TRADING_HALT,
            is_active=True,
            reason="test",
            triggered_by="unit_test",
        )
    )
    order, reasons = await adapter.submit_entry(signal=signal, risk_decision=make_risk(signal), event_time_ms=signal.event_time_ms)
    assert order is None
    assert any(reason.startswith("kill_switch_active") for reason in reasons)


@pytest.mark.asyncio
async def test_cancel_and_sync_order_status() -> None:
    client = FakeClient()
    adapter = BinanceLiveExecutionAdapter(client.config, client)  # type: ignore[arg-type]
    signal = make_signal()
    order, _ = await adapter.submit_entry(signal=signal, risk_decision=make_risk(signal), event_time_ms=signal.event_time_ms)
    assert order is not None
    cancelled = await adapter.cancel_order(order_id=order.order_id, event_time_ms=signal.event_time_ms + 1)
    assert cancelled is not None
    assert cancelled.status == OrderStatus.CANCELLED
    # Reopen status sync can still map exchange snapshot deterministically.
    synced = await adapter.sync_order_status(order_id=order.order_id, event_time_ms=signal.event_time_ms + 2)
    assert synced is not None
    assert synced.status == OrderStatus.FILLED


@pytest.mark.asyncio
async def test_reduce_only_close_sends_reduce_only_true() -> None:
    client = FakeClient()
    adapter = BinanceLiveExecutionAdapter(client.config, client)  # type: ignore[arg-type]
    signal_id = uuid4()
    risk_snapshot_id = uuid4()
    order = await adapter.submit_reduce_only_close(
        symbol="BTCUSDT",
        position_amount=Decimal("0.02"),
        signal_id=signal_id,
        risk_snapshot_id=risk_snapshot_id,
        event_time_ms=1_700_000_000_000,
        limit_price=Decimal("62000"),
    )
    assert order.reduce_only is True
    assert order.side == OrderSide.SELL
    assert client.placed_params[0]["reduceOnly"] is True


def test_order_trade_update_emits_fill() -> None:
    client = FakeClient()
    adapter = BinanceLiveExecutionAdapter(client.config, client)  # type: ignore[arg-type]
    signal = make_signal()
    risk = make_risk(signal)

    async def setup() -> str:
        order, _ = await adapter.submit_entry(signal=signal, risk_decision=risk, event_time_ms=signal.event_time_ms)
        assert order is not None
        return order.client_order_id

    import asyncio

    client_id = asyncio.run(setup())
    result = adapter.on_order_trade_update(
        {
            "e": "ORDER_TRADE_UPDATE",
            "E": signal.event_time_ms + 100,
            "T": signal.event_time_ms + 100,
            "o": {
                "s": "BTCUSDT",
                "c": client_id,
                "S": "BUY",
                "o": "LIMIT",
                "x": "TRADE",
                "X": "PARTIALLY_FILLED",
                "i": 12345,
                "l": "0.005",
                "z": "0.005",
                "L": "62000",
                "ap": "62000",
                "n": "0.0124",
                "N": "USDT",
                "m": False,
            },
        }
    )
    assert result.fill_event is not None
    assert result.fill_event.fill_quantity == Decimal("0.005")
    assert result.order_event is not None
    assert result.order_event.status == OrderStatus.PARTIALLY_FILLED
