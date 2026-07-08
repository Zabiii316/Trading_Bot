from __future__ import annotations

from deployment import CapitalControls, DeploymentStage, OperationalSnapshot, ProductionReadinessValidator


def _snapshot(**overrides):
    payload = {
        "stage": DeploymentStage.MICRO_LIVE,
        "commit_sha": "abcdef123",
        "image_tag": "trading-bot:0.15.0",
        "tests_passed": True,
        "test_count": 127,
        "paper_trades": 250,
        "testnet_orders": 125,
        "paper_profit_factor": 1.2,
        "risk_engine_healthy": True,
        "monitoring_healthy": True,
        "reconciliation_healthy": True,
        "order_book_sequence_healthy": True,
        "kill_switch_tested": True,
        "emergency_drills": [
            {"name": "cancel_all", "completed": True, "latency_ms": 800},
            {"name": "emergency_flatten", "completed": True, "latency_ms": 1200},
            {"name": "reconciliation_rebuild", "completed": True, "latency_ms": 1500},
            {"name": "service_restart", "completed": True, "latency_ms": 1700},
        ],
        "live_trading_enabled": True,
        "withdrawal_permissions_disabled": True,
        "secrets_loaded_from_manager": True,
        "manual_approval": True,
        "open_critical_alerts": 0,
        "stale_component_count": 0,
        "current_daily_loss_pct": 0.0,
        "current_weekly_loss_pct": 0.0,
        "current_drawdown_pct": 0.0,
    }
    payload.update(overrides)
    return OperationalSnapshot.model_validate(payload)


def _capital(**overrides):
    payload = {
        "account_equity_usd": 100_000,
        "requested_allocation_usd": 750,
        "max_allocation_pct": 0.10,
        "max_daily_loss_pct": 0.015,
        "max_weekly_loss_pct": 0.04,
        "max_portfolio_drawdown_pct": 0.08,
        "max_effective_leverage": 1.0,
        "max_symbol_exposure_pct": 0.30,
        "max_strategy_exposure_pct": 0.40,
        "max_correlated_cluster_pct": 0.35,
        "per_trade_risk_pct": 0.0025,
    }
    payload.update(overrides)
    return CapitalControls.model_validate(payload)


def test_readiness_passes_micro_live():
    report = ProductionReadinessValidator().evaluate(_snapshot(), _capital())
    assert report.decision in {"approve", "approve_with_limits"}
    assert report.blocking_failures == []
    assert report.approved_allocation_usd == 750


def test_critical_alert_blocks_deployment():
    report = ProductionReadinessValidator().evaluate(_snapshot(open_critical_alerts=1), _capital())
    assert report.decision == "hold"
    assert any(g.name == "critical_alerts" for g in report.blocking_failures)


def test_non_live_stage_requires_live_flag_disabled():
    report = ProductionReadinessValidator().evaluate(
        _snapshot(stage=DeploymentStage.TESTNET_PAPER, live_trading_enabled=True), _capital()
    )
    assert report.decision == "hold"
    assert any(g.name == "live_trading_flag" for g in report.blocking_failures)


def test_live_stage_requires_manual_approval():
    report = ProductionReadinessValidator().evaluate(_snapshot(manual_approval=False), _capital())
    assert report.decision == "hold"
    assert any(g.name == "manual_approval" for g in report.blocking_failures)


def test_missing_emergency_drill_blocks_deployment():
    drills = [{"name": "cancel_all", "completed": True, "latency_ms": 800}]
    report = ProductionReadinessValidator().evaluate(_snapshot(emergency_drills=drills), _capital())
    assert report.decision == "hold"
    assert any(g.name == "emergency_drills" for g in report.blocking_failures)


def test_capital_allocation_is_reduced_to_stage_cap():
    report = ProductionReadinessValidator().evaluate(
        _snapshot(), _capital(requested_allocation_usd=5000)
    )
    assert report.decision == "approve_with_limits"
    assert report.approved_allocation_usd == 1000
    assert any(g.name == "capital_allocation_cap" and g.status == "warn" for g in report.gates)


def test_daily_loss_limit_blocks_deployment():
    report = ProductionReadinessValidator().evaluate(
        _snapshot(current_daily_loss_pct=0.02), _capital()
    )
    assert report.decision == "hold"
    assert any(g.name == "daily_loss_limit" for g in report.blocking_failures)


def test_leverage_above_stage_cap_blocks():
    report = ProductionReadinessValidator().evaluate(_snapshot(), _capital(max_effective_leverage=2.0))
    assert report.decision == "hold"
    assert any(g.name == "stage_leverage_cap" for g in report.blocking_failures)
