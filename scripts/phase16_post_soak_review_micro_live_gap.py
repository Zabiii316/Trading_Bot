from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path

OUTPUT_PATH = Path("data/processed/phase16_post_soak_review_micro_live_gap.json")

INPUTS = {
    "soak_execution": Path("data/processed/phase16_testnet_soak_execution_report.json"),
    "soak_plan": Path("data/processed/phase16_testnet_soak_plan.json"),
    "alerting_controls": Path("data/processed/phase16_alerting_incident_response_controls.json"),
    "micro_live_controls": Path("data/processed/phase16_micro_live_controls_spec.json"),
    "manual_approval": Path("data/processed/phase16_manual_approval_checklist.json"),
}


def git_clean() -> bool:
    result = subprocess.run(["git", "status", "--short"], capture_output=True, text=True)
    return result.stdout.strip() == ""


def load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text())


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

    input_status = {name: path.exists() for name, path in INPUTS.items()}
    soak = load_json(INPUTS["soak_execution"])

    completed_checks = {
        "soak_report_present": input_status["soak_execution"],
        "soak_duration_passed": bool(soak.get("duration_passed")),
        "soak_passed": bool(soak.get("passed")),
        "safe_mode_active": safe_mode_active,
        "live_trading_disabled": flags.get("BINANCE_ENABLE_LIVE_TRADING") == "false",
        "manual_live_permission_disabled": flags.get("LIVE_TRADING_ALLOWED") == "false",
        "git_working_tree_clean": git_clean(),
    }

    remaining_gaps = [
        "separate_micro_live_manual_approval_not_recorded",
        "real_exchange_key_management_not_finalized",
        "production_binance_api_key_not_ip_whitelisted",
        "withdrawal_permissions_not_independently_verified_disabled",
        "micro_live_capital_amount_not_formally_approved",
        "max_single_order_notional_not_formally_approved",
        "daily_loss_limit_not_formally_approved",
        "weekly_loss_limit_not_formally_approved",
        "maximum_drawdown_stop_not_formally_approved",
        "incident_response_owner_not_formally_assigned",
        "independent_code_review_not_recorded",
        "production_secrets_manager_not_confirmed",
        "exchange_permissions_audit_not_attached",
        "final_micro_live_go_no_go_report_not_created",
    ]

    report = {
        "phase": "phase_16_15_post_soak_review_micro_live_approval_gap",
        "generated_at_unix": int(time.time()),
        "scope": "post_soak_review_and_micro_live_gap_analysis_only",
        "not_approved_for": [
            "real_live_trading",
            "micro_live_execution",
            "production_binance_order_submission",
        ],
        "safety_flags": flags,
        "inputs_present": input_status,
        "all_inputs_present": all(input_status.values()),
        "completed_checks": completed_checks,
        "soak_summary": {
            "elapsed_hours": soak.get("elapsed_hours"),
            "duration_passed": soak.get("duration_passed"),
            "passed": soak.get("passed"),
            "decision": soak.get("decision"),
        },
        "remaining_micro_live_gaps": remaining_gaps,
        "approved_for_micro_live_execution": False,
        "decision": "POST_SOAK_REVIEW_COMPLETE_MICRO_LIVE_NOT_APPROVED_GAPS_REMAIN",
        "next_phase": "Phase 16.16 — Final Micro-Live Go/No-Go Gate Specification",
        "safety_notes": [
            "The 24h testnet soak passing does not approve real live trading.",
            "Micro-live requires a separate final go/no-go gate.",
            "Production Binance order submission remains disabled.",
            "Live trading flags must remain disabled until separate manual approval.",
        ],
    }

    OUTPUT_PATH.write_text(json.dumps(report, indent=2))

    print(f"Report written to: {OUTPUT_PATH}")
    print(f"all_inputs_present={report['all_inputs_present']}")
    print(f"soak_passed={completed_checks['soak_passed']}")
    print(f"safe_mode_active={safe_mode_active}")
    print(f"approved_for_micro_live_execution={report['approved_for_micro_live_execution']}")
    print(f"decision={report['decision']}")


if __name__ == "__main__":
    main()
