from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path


OUTPUT_PATH = Path("data/processed/phase16_micro_live_controls_spec.json")
GAP_REPORT_PATH = Path("data/processed/phase16_micro_live_gap_analysis.json")


def git_clean() -> bool:
    result = subprocess.run(
        ["git", "status", "--short"],
        capture_output=True,
        text=True,
    )
    return result.stdout.strip() == ""


def load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text())


def main() -> None:
    gap_report = load_json(GAP_REPORT_PATH)

    safety_flags = {
        "BINANCE_TESTNET": os.getenv("BINANCE_TESTNET"),
        "BINANCE_USE_TESTNET": os.getenv("BINANCE_USE_TESTNET"),
        "BINANCE_ENABLE_LIVE_TRADING": os.getenv("BINANCE_ENABLE_LIVE_TRADING"),
        "LIVE_TRADING_ALLOWED": os.getenv("LIVE_TRADING_ALLOWED"),
    }

    safe_mode_active = (
        safety_flags.get("BINANCE_ENABLE_LIVE_TRADING") == "false"
        and safety_flags.get("LIVE_TRADING_ALLOWED") == "false"
    )

    proposed_controls = {
        "execution_scope": {
            "micro_live_execution_enabled": False,
            "requires_separate_manual_approval": True,
            "allowed_symbols": ["BTCUSDT"],
            "allowed_market_type": "binance_usdm_futures",
            "allowed_order_types": ["marketable_limit"],
            "max_concurrent_positions": 1,
            "max_open_orders": 1
        },
        "capital_controls": {
            "starting_micro_live_capital_usd": None,
            "max_single_order_notional_usd": 10,
            "max_total_open_notional_usd": 10,
            "max_daily_loss_usd": 5,
            "max_weekly_loss_usd": 10,
            "max_drawdown_usd": 10,
            "risk_fraction_per_trade_max": 0.001
        },
        "frequency_controls": {
            "max_orders_per_day": 3,
            "cooldown_minutes_after_order": 30,
            "cooldown_minutes_after_rejection": 60,
            "cooldown_minutes_after_loss": 120
        },
        "exchange_safety_controls": {
            "production_keys_required": False,
            "ip_whitelisting_required": True,
            "withdrawals_must_be_disabled": True,
            "key_permissions": [
                "futures_trading_only",
                "no_withdrawals",
                "no_unrestricted_account_permissions"
            ]
        },
        "kill_switch_controls": {
            "kill_switch_file": "runtime/KILL_SWITCH_ACTIVE",
            "safe_flags_file": "runtime/safe_trading_flags.env",
            "emergency_stop_script": "scripts/phase16_emergency_stop.sh",
            "cancel_all_required_before_micro_live": True,
            "position_flatten_required_before_micro_live": True
        },
        "monitoring_controls": {
            "prometheus_required": True,
            "grafana_required": True,
            "dashboard_review_required": True,
            "alerting_required": True,
            "required_alerts": [
                "order_submitted",
                "order_rejected",
                "position_opened",
                "daily_loss_limit_hit",
                "kill_switch_active",
                "monitoring_api_down"
            ]
        },
        "approval_controls": {
            "manual_micro_live_approval_required": True,
            "independent_code_review_required": True,
            "minimum_24h_testnet_soak_required": True,
            "incident_response_owner_required": True
        }
    }

    blocking_gaps = [
        "starting_micro_live_capital_usd_not_defined",
        "production_key_management_not_documented",
        "ip_whitelisting_not_confirmed",
        "withdrawal_permissions_not_confirmed_disabled",
        "cancel_all_not_retested_after_testnet_execution",
        "position_flatten_not_tested",
        "alerts_not_tested",
        "24h_testnet_soak_not_completed",
        "manual_micro_live_approval_not_recorded",
        "independent_code_review_not_completed"
    ]

    report = {
        "phase": "phase_16_11_micro_live_controls_specification",
        "generated_at_unix": int(time.time()),
        "scope": "controls_specification_only",
        "not_approved_for": [
            "real_live_trading",
            "micro_live_execution",
            "production_binance_order_submission"
        ],
        "safety_flags": safety_flags,
        "safe_mode_active": safe_mode_active,
        "git_working_tree_clean": git_clean(),
        "gap_report_present": GAP_REPORT_PATH.exists(),
        "gap_report_decision": gap_report.get("decision"),
        "proposed_controls": proposed_controls,
        "blocking_gaps_before_micro_live": blocking_gaps,
        "controls_specified": True,
        "approved_for_micro_live_execution": False,
        "decision": "MICRO_LIVE_CONTROLS_SPEC_READY_FOR_REVIEW_NOT_EXECUTION",
        "next_phase": "Phase 16.12 — Alerting and Incident Response Controls",
        "safety_notes": [
            "This phase only defines controls.",
            "Micro-live execution remains disabled.",
            "Production live trading remains disabled.",
            "A separate manual approval gate is required before any real exchange execution."
        ]
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(report, indent=2))

    print(f"Report written to: {OUTPUT_PATH}")
    print(f"safe_mode_active={safe_mode_active}")
    print(f"approved_for_micro_live_execution={report['approved_for_micro_live_execution']}")
    print(f"decision={report['decision']}")


if __name__ == "__main__":
    main()
