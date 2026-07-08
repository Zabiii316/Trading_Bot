from decimal import Decimal
from uuid import uuid4

from trading_contracts.enums import KillSwitchLevel, MarketType, TradeSide, Venue
from trading_contracts.events import SignalEvent
from trading_risk.kill_switch import KillSwitchRegistry, make_kill_switch_event
from trading_risk.models import AccountState, RiskLimits
from trading_risk.replay import run_risk_replay


def signal(t=1_000):
    return SignalEvent(
        source="test",
        venue=Venue.BINANCE_USDM,
        market_type=MarketType.PERPETUAL_FUTURES,
        symbol="BTCUSDT",
        event_time_ms=t,
        received_time_ms=t,
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
        expires_at_ms=t + 60_000,
        feature_snapshot_id=uuid4(),
    )


def test_kill_switch_registry_symbol_scope():
    reg = KillSwitchRegistry()
    ev = make_kill_switch_event(
        level=KillSwitchLevel.SOFT_STRATEGY_SUSPENSION,
        active=True,
        reason="slippage spike",
        triggered_by="test",
        symbol="BTCUSDT",
        event_time_ms=1_000,
    )
    reg.update_from_event(ev)
    assert reg.resolve(strategy_id="x", symbol="BTCUSDT").is_active
    assert not reg.resolve(strategy_id="x", symbol="ETHUSDT").is_active


def test_risk_replay_outputs_kill_switch_and_decision():
    sig = signal()
    kill = make_kill_switch_event(
        level=KillSwitchLevel.HARD_TRADING_HALT,
        active=True,
        reason="manual",
        triggered_by="unit",
        event_time_ms=900,
    )
    decisions = run_risk_replay([kill, sig], account=AccountState(equity_quote=100_000), limits=RiskLimits())
    assert len(decisions) == 2
    assert decisions[0].event_type == "risk.kill_switch"
    assert decisions[1].event_type == "risk.decision"
    assert decisions[1].status == "halted"
