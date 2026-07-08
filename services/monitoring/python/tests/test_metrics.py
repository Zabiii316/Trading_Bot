from decimal import Decimal
from uuid import uuid4

from trading_contracts.enums import (
    KillSwitchLevel,
    MarketType,
    RiskDecisionStatus,
    Venue,
)
from trading_contracts.events import (
    KillSwitchEvent,
    OrderFlowFeatureEvent,
    PriceLevel,
    ReconstructedBookEvent,
    RiskDecisionEvent,
)
from trading_monitoring.metrics import TradingMetrics


def _base():
    return dict(
        source="test",
        venue=Venue.BINANCE_USDM,
        market_type=MarketType.PERPETUAL_FUTURES,
        symbol="btcusdt",
        event_time_ms=1_000,
        received_time_ms=1_010,
    )


def test_metrics_observe_reconstructed_book_and_export():
    metrics = TradingMetrics()
    event = ReconstructedBookEvent(
        **_base(),
        last_update_id=123,
        best_bid=PriceLevel(price=Decimal("100"), quantity=Decimal("2")),
        best_ask=PriceLevel(price=Decimal("101"), quantity=Decimal("3")),
        spread=Decimal("1"),
        spread_bps=Decimal("100"),
        bid_depth_notional_10=Decimal("200"),
        ask_depth_notional_10=Decimal("303"),
        is_sequence_healthy=True,
    )

    metrics.observe_event(event)
    exported = metrics.export_text().decode()

    assert 'trading_events_total{event_type="book.reconstructed"' in exported
    assert 'trading_orderbook_sequence_healthy{symbol="BTCUSDT",venue="binance_usdm"} 1.0' in exported
    assert 'trading_orderbook_spread_bps{symbol="BTCUSDT",venue="binance_usdm"} 100.0' in exported


def test_metrics_observe_order_flow_risk_and_kill_switch():
    metrics = TradingMetrics()
    flow = OrderFlowFeatureEvent(
        **_base(),
        window_ms=1_000,
        trade_count=4,
        buy_volume=Decimal("3"),
        sell_volume=Decimal("1"),
        delta=Decimal("2"),
        normalized_delta=Decimal("0.5"),
        cumulative_volume_delta=Decimal("10"),
        queue_imbalance_l1=Decimal("0.25"),
        absorption_ratio=Decimal("5"),
    )
    risk = RiskDecisionEvent(
        **_base(),
        signal_id=uuid4(),
        status=RiskDecisionStatus.REJECTED,
        account_equity_quote=Decimal("100000"),
        risk_fraction=Decimal("0.005"),
        rejection_reasons=["daily_loss_limit"],
    )
    kill = KillSwitchEvent(
        **_base(),
        level=KillSwitchLevel.HARD_TRADING_HALT,
        is_active=True,
        reason="order_book_gap",
        triggered_by="risk_engine",
    )

    for event in (flow, risk, kill):
        metrics.observe_event(event)
    exported = metrics.export_text().decode()

    assert 'trading_orderflow_delta{symbol="BTCUSDT",venue="binance_usdm",window_ms="1000"} 2.0' in exported
    assert 'trading_risk_rejections_total{reason="daily_loss_limit",symbol="BTCUSDT",venue="binance_usdm"} 1.0' in exported
    assert 'trading_kill_switch_active{level="hard_trading_halt",strategy_id="all",symbol="BTCUSDT"} 1.0' in exported
