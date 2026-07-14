from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path

OUTPUT_PATH = Path("data/processed/phase16_capital_limits_loss_limit_controls.json")

INPUTS = {
    "secrets_manager_controls": Path("data/processed/phase16_secrets_manager_key_handling_controls.json"),
    "production_api_key_audit": Path("data/processed/phase16_production_api_key_permission_audit.json"),
    "manual_approval_record": Path("data/processed/phase16_micro_live_manual_approval_record.json"),
    "final_go_no_go_gate": Path("data/processed/phase16_final_micro_live_go_no_go_gate_spec.json"),
    "post_soak_review": Path("data/processed/phase16_post_soak_review_micro_live_gap.json"),
}


def git_clean() -> bool:
    result = subprocess.run(["git", "status", "--short"], capture_output=True, text=True)
    return result.stdout.strip() == ""


def parse_positive_float(value: str | None) -> bool:
    try:
        if value is None or value.strip() == "":
            return False
        return float(value) > 0
    except Exception:
        return False


def main() -> None:
    flags = {
        "BINANCE_TESTNET": os.getenv("BINANCE_TESTNET"),
        "BINANCE_USE_TESTNET": os.getenv("BINANCE_USE_TESTNET"),
        "BINANCE_ENABLE_LIVE_TRADING": os.getenv("BINANCE_ENABLE_LIVE_TRADING"),
        "LIVE_TRADING_ALLOWED": os.getenv("LIVE_TRADING_ALLOWED"),
    }

    safe_mode_active = (
        flags.get("BINANCE_ENABLE_LIVE_TRADING") == "false"
        and flags.get("LIVE_TRADING_ALLOWED") == "false"
    )

    inputs_present = {name: path.exists() for name, path in INPUTS.items()}

    capital_limits = {
        "approved_capital_usd": os.getenv("MICRO_LIVE_APPROVED_CAPITAL_USD", ""),
        "max_single_order_notional_usd": os.getenv("MICRO_LIVE_MAX_SINGLE_ORDER_NOTIONAL_USD", ""),
        "daily_loss_limit_usd": os.getenv("MICRO_LIVE_DAILY_LOSS_LIMIT_USD", ""),
        "weekly_loss_limit_usd": os.getenv("MICRO_LIVE_WEEKLY_LOSS_LIMIT_USD", ""),
        "maximum_drawdown_limit_usd": os.getenv("MICRO_LIVE_MAX_DRAWDOWN_LIMIT_USD", ""),
        "max_consecutive_losses": os.getenv("MICRO_LIVE_MAX_CONSECUTIVE_LOSSES", ""),
        "capital_limits_formally_approved": os.getenv("MICRO_LIVE_CAPITAL_LIMITS_FORMALLY_APPROVED", "false") == "true",
        "loss_limits_formally_approved": os.getenv("MICRO_LIVE_LOSS_LIMITS_FORMALLY_APPROVED", "false") == "true",
        "operator_understands_loss_limits": os.getenv("MICRO_LIVE_OPERATOR_UNDERSTANDS_LOSS_LIMITS", "false") == "true",
    }

    numeric_checks = {
        "approved_capital_valid": parse_positive_float(capital_limits["approved_capital_usd"]),
        "max_single_order_notional_valid": parse_positive_float(capital_limits["max_single_order_notional_usd"]),
        "daily_loss_limit_valid": parse_positive_float(capital_limits["daily_loss_limit_usd"]),
        "weekly_loss_limit_valid": parse_positive_float(capital_limits["weekly_loss_limit_usd"]),
        "maximum_drawdown_limit_valid": parse_positive_float(capital_limits["maximum_drawdown_limit_usd"]),
        "max_consecutive_losses_valid": parse_positive_float(capital_limits["max_consecutive_losses"]),
    }

    all_numeric_limits_defined = all(numeric_checks.values())

    report = {
        "phase": "phase_16_20_capital_limits_loss_limit_controls",
        "generated_at_unix": int(time.time()),
        "scope": "capital_limits_and_loss_limit_controls_only",
        "not_approved_for": [
            "real_live_trading",
            "micro_live_execution",
            "production_binance_order_submission",
        ],
        "safety_flags": flags,
        "safe_mode_active": safe_mode_active,
        "inputs_present": inputs_present,
        "all_inputs_present": all(inputs_present.values()),
        "git_working_tree_clean": git_clean(),
        "capital_limits": capital_limits,
        "numeric_limit_checks": numeric_checks,
        "all_numeric_limits_defined": all_numeric_limits_defined,
        "approved_for_micro_live_execution": False,
        "decision": "CAPITAL_LIMITS_LOSS_LIMIT_CONTROLS_CREATED_NOT_APPROVED_FOR_EXECUTION",
        "next_phase": "Phase 16.21 — Emergency Stop and Kill Switch Retest",
        "safety_notes": [
            "This phase defines capital and loss-limit controls only.",
            "No live trading is enabled.",
            "Micro-live execution still requires separate manual approval.",
            "Loss limits must be formally approved before any future micro-live gate.",
            "Live trading flags must remain disabled.",
        ],
    }

    OUTPUT_PATH.write_text(json.dumps(report, indent=2))

    print(f"Report written to: {OUTPUT_PATH}")
    print(f"safe_mode_active={safe_mode_active}")
    print(f"all_inputs_present={report['all_inputs_present']}")
    print(f"git_working_tree_clean={report['git_working_tree_clean']}")
    print(f"all_numeric_limits_defined={all_numeric_limits_defined}")
    print(f"approved_for_micro_live_execution={report['approved_for_micro_live_execution']}")
    print(f"decision={report['decision']}")


if __name__ == "__main__":
    main()
