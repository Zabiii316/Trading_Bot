from decimal import Decimal
from uuid import uuid4

from trading_contracts.enums import EventType, KillSwitchLevel, MarketType, RiskDecisionStatus, TradeSide, Venue
from trading_contracts.events import KillSwitchEvent, RiskDecisionEvent
from trading_risk.sizing import round_down_to_step
from trading_storage.table_map import group_events_for_clickhouse, row_for_event


def test_quantity_rounding_down_to_step():
    assert round_down_to_step(1.23456, 0.01) == 1.23
    assert round_down_to_step(1.23456, 0.0) == 1.23456


def test_risk_decision_storage_mapping():
    event = RiskDecisionEvent(
        source="risk_engine",
        venue=Venue.BINANCE_USDM,
        market_type=MarketType.PERPETUAL_FUTURES,
        symbol="BTCUSDT",
        event_time_ms=1_000,
        received_time_ms=1_000,
        signal_id=uuid4(),
        status=RiskDecisionStatus.APPROVED,
        approved_quantity=Decimal("1.25"),
        max_loss_quote=Decimal("50"),
        account_equity_quote=Decimal("100000"),
        risk_fraction=Decimal("0.0025"),
    )
    row = row_for_event(event)
    assert row["approved_quantity"] == "1.25"
    assert row["status"] == RiskDecisionStatus.APPROVED
    grouped = group_events_for_clickhouse([event])
    assert grouped[0].table_name == "risk_decisions"


def test_kill_switch_storage_mapping():
    event = KillSwitchEvent(
        source="risk_engine",
        venue=Venue.INTERNAL,
        market_type=MarketType.PAPER,
        symbol="GLOBAL",
        event_time_ms=1_000,
        received_time_ms=1_000,
        level=KillSwitchLevel.EMERGENCY_FLATTEN,
        is_active=True,
        reason="unknown exposure",
        triggered_by="unit",
    )
    row = row_for_event(event)
    assert row["level"] == KillSwitchLevel.EMERGENCY_FLATTEN
    assert row["is_active"] == 1
    assert group_events_for_clickhouse([event])[0].table_name == "kill_switch_events"
