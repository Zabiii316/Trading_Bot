from decimal import Decimal
from uuid import uuid4

from trading_contracts.enums import KillSwitchLevel, MarketType, RiskDecisionStatus, TradeSide, Venue
from trading_contracts.events import SignalEvent
from trading_risk.engine import RiskEngine
from trading_risk.models import AccountState, KillSwitchState, PositionSnapshot, RiskLimits, RiskRejectReason, RiskRequest


def signal(**overrides):
    payload = dict(
        source="test",
        venue=Venue.BINANCE_USDM,
        market_type=MarketType.PERPETUAL_FUTURES,
        symbol="BTCUSDT",
        event_time_ms=1_000,
        received_time_ms=1_000,
        strategy_id="sweep_orderflow_avwap_v1",
        side=TradeSide.LONG,
        outcome="bullish_rejection",
        entry_candidate=Decimal("100"),
        stop=Decimal("99"),
        target_1=Decimal("102"),
        target_2=Decimal("103"),
        liquidity_score=Decimal("0.8"),
        order_flow_score=Decimal("0.8"),
        avwap_score=Decimal("0.8"),
        regime_score=Decimal("0.7"),
        execution_score=Decimal("0.8"),
        final_score=Decimal("0.78"),
        expected_net_return_bps=Decimal("20"),
        expires_at_ms=60_000,
        feature_snapshot_id=uuid4(),
    )
    payload.update(overrides)
    return SignalEvent(**payload)


def account(**overrides):
    payload = dict(equity_quote=100_000.0, available_margin_quote=80_000.0, peak_equity_quote=100_000.0)
    payload.update(overrides)
    return AccountState(**payload)


def test_approves_valid_signal_and_sizes_by_risk_distance():
    engine = RiskEngine(RiskLimits(risk_fraction_per_trade=0.0025, quantity_step=0.001))
    detail, event = engine.evaluate(RiskRequest(signal=signal(), account=account(), event_time_ms=2_000))
    assert event.status == RiskDecisionStatus.APPROVED
    assert detail.approved
    assert event.approved_quantity == Decimal("250.0")
    assert event.max_loss_quote == Decimal("250.0")
    assert event.risk_fraction == Decimal("0.0025")


def test_rejects_expired_signal():
    engine = RiskEngine()
    _, event = engine.evaluate(RiskRequest(signal=signal(expires_at_ms=1_500), account=account(), event_time_ms=2_000))
    assert event.status == RiskDecisionStatus.REJECTED
    assert RiskRejectReason.SIGNAL_EXPIRED.value in event.rejection_reasons


def test_hard_kill_switch_halts_trade():
    engine = RiskEngine()
    kill = KillSwitchState(level=KillSwitchLevel.HARD_TRADING_HALT, is_active=True, reason="manual")
    _, event = engine.evaluate(RiskRequest(signal=signal(), account=account(), event_time_ms=2_000, kill_switch=kill))
    assert event.status == RiskDecisionStatus.HALTED
    assert RiskRejectReason.KILL_SWITCH_ACTIVE.value in event.rejection_reasons


def test_daily_loss_limit_rejects():
    engine = RiskEngine(RiskLimits(daily_loss_limit_fraction=0.01))
    _, event = engine.evaluate(
        RiskRequest(signal=signal(), account=account(realized_pnl_today_quote=-1_500.0), event_time_ms=2_000)
    )
    assert event.status == RiskDecisionStatus.REJECTED
    assert RiskRejectReason.DAILY_LOSS_LIMIT.value in event.rejection_reasons


def test_existing_exposure_can_reduce_size():
    pos = PositionSnapshot(
        symbol="BTCUSDT",
        side=TradeSide.LONG,
        quantity=400.0,
        entry_price=100.0,
        mark_price=100.0,
        strategy_id="other",
        correlated_cluster="btc",
    )
    engine = RiskEngine(
        RiskLimits(
            risk_fraction_per_trade=0.01,
            max_risk_fraction_per_trade=0.02,
            max_symbol_exposure_fraction=0.5,
            max_order_notional_fraction=1.0,
            quantity_step=0.001,
        )
    )
    detail, event = engine.evaluate(
        RiskRequest(
            signal=signal(),
            account=account(open_positions=(pos,)),
            event_time_ms=2_000,
            correlated_cluster="btc",
        )
    )
    assert event.status == RiskDecisionStatus.REDUCED_SIZE
    assert detail.approved_quantity > 0
    assert detail.notional_quote <= 10_000.0 + 1e-9
    assert RiskRejectReason.MAX_SYMBOL_EXPOSURE.value in detail.reduction_reasons


def test_rejects_duplicate_signal():
    sig = signal()
    engine = RiskEngine()
    _, event = engine.evaluate(
        RiskRequest(signal=sig, account=account(seen_signal_ids=frozenset({sig.signal_id})), event_time_ms=2_000)
    )
    assert event.status == RiskDecisionStatus.REJECTED
    assert RiskRejectReason.DUPLICATE_SIGNAL.value in event.rejection_reasons
