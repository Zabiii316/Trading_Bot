from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path

OUTPUT_PATH = Path("data/processed/phase16_micro_live_manual_approval_record.json")

INPUTS = {
    "final_go_no_go_gate": Path("data/processed/phase16_final_micro_live_go_no_go_gate_spec.json"),
    "post_soak_review": Path("data/processed/phase16_post_soak_review_micro_live_gap.json"),
    "soak_execution": Path("data/processed/phase16_testnet_soak_execution_report.json"),
    "alerting_controls": Path("data/processed/phase16_alerting_incident_response_controls.json"),
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
    gate = load_json(INPUTS["final_go_no_go_gate"])
    soak = load_json(INPUTS["soak_execution"])

    manual_approval_record = {
        "approval_scope": "micro_live_review_only_not_execution",
        "approval_status": "not_approved",
        "approver_name": os.getenv("MICRO_LIVE_APPROVER_NAME", ""),
        "approval_ticket_id": os.getenv("MICRO_LIVE_APPROVAL_TICKET_ID", ""),
        "approved_capital_usd": os.getenv("MICRO_LIVE_APPROVED_CAPITAL_USD", ""),
        "max_single_order_notional_usd": os.getenv("MICRO_LIVE_MAX_ORDER_NOTIONAL_USD", ""),
        "daily_loss_limit_usd": os.getenv("MICRO_LIVE_DAILY_LOSS_LIMIT_USD", ""),
        "weekly_loss_limit_usd": os.getenv("MICRO_LIVE_WEEKLY_LOSS_LIMIT_USD", ""),
        "maximum_drawdown_limit_usd": os.getenv("MICRO_LIVE_MAX_DRAWDOWN_LIMIT_USD", ""),
        "incident_response_owner": os.getenv("MICRO_LIVE_INCIDENT_OWNER", ""),
        "human_acknowledgements": {
            "understands_real_financial_risk": False,
            "confirms_no_production_execution_now": True,
            "confirms_live_flags_must_remain_disabled": True,
            "confirms_separate_execution_gate_required": True
        }
    }

    required_manual_fields_present = all(
        bool(manual_approval_record[key])
        for key in [
            "approver_name",
            "approval_ticket_id",
            "approved_capital_usd",
            "max_single_order_notional_usd",
            "daily_loss_limit_usd",
            "weekly_loss_limit_usd",
            "maximum_drawdown_limit_usd",
            "incident_response_owner",
        ]
    )

    report = {
        "phase": "phase_16_17_micro_live_manual_approval_record",
        "generated_at_unix": int(time.time()),
        "scope": "manual_approval_record_template_only",
        "not_approved_for": [
            "real_live_trading",
            "micro_live_execution",
            "production_binance_order_submission"
        ],
        "safety_flags": flags,
        "safe_mode_active": safe_mode_active,
        "inputs_present": input_status,
        "all_inputs_present": all(input_status.values()),
        "git_working_tree_clean": git_clean(),
        "prior_gate_decision": gate.get("decision"),
        "soak_passed": bool(soak.get("passed")),
        "manual_approval_record": manual_approval_record,
        "required_manual_fields_present": required_manual_fields_present,
        "approved_for_micro_live_execution": False,
        "decision": "MICRO_LIVE_MANUAL_APPROVAL_RECORD_CREATED_NOT_APPROVED_FOR_EXECUTION",
        "next_phase": "Phase 16.18 — Production API Key and Exchange Permission Audit",
        "safety_notes": [
            "This record does not enable live trading.",
            "Manual approval fields are recorded only as evidence.",
            "A separate execution gate is still required.",
            "Live trading flags must remain disabled."
        ]
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(report, indent=2))

    print(f"Report written to: {OUTPUT_PATH}")
    print(f"safe_mode_active={safe_mode_active}")
    print(f"all_inputs_present={report['all_inputs_present']}")
    print(f"required_manual_fields_present={required_manual_fields_present}")
    print(f"approved_for_micro_live_execution={report['approved_for_micro_live_execution']}")
    print(f"decision={report['decision']}")


if __name__ == "__main__":
    main()
