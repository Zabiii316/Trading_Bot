from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path

OUTPUT_PATH = Path("data/processed/phase16_final_micro_live_go_no_go_gate_spec.json")

INPUTS = {
    "post_soak_review": Path("data/processed/phase16_post_soak_review_micro_live_gap.json"),
    "soak_execution": Path("data/processed/phase16_testnet_soak_execution_report.json"),
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

    inputs_present = {name: path.exists() for name, path in INPUTS.items()}
    soak = load_json(INPUTS["soak_execution"])
    post_soak = load_json(INPUTS["post_soak_review"])

    report = {
        "phase": "phase_16_16_final_micro_live_go_no_go_gate_specification",
        "generated_at_unix": int(time.time()),
        "scope": "final_micro_live_go_no_go_gate_specification_only",
        "not_approved_for": [
            "real_live_trading",
            "micro_live_execution",
            "production_binance_order_submission"
        ],
        "safety_flags": flags,
        "safe_mode_active": safe_mode_active,
        "inputs_present": inputs_present,
        "all_inputs_present": all(inputs_present.values()),
        "post_soak_review_completed": post_soak.get("decision") == "POST_SOAK_REVIEW_COMPLETE_MICRO_LIVE_NOT_APPROVED_GAPS_REMAIN",
        "testnet_soak_passed": bool(soak.get("passed")),
        "testnet_soak_duration_passed": bool(soak.get("duration_passed")),
        "git_working_tree_clean": git_clean(),
        "current_gate": {
            "decision": "NO_GO_SAFE_MODE_REMAINS_ACTIVE",
            "micro_live_execution_allowed_now": False,
            "production_live_execution_allowed_now": False,
            "requires_separate_manual_approval": True,
            "requires_exchange_permission_audit": True,
            "requires_capital_limit_signoff": True,
            "requires_incident_response_signoff": True
        },
        "approved_for_micro_live_execution": False,
        "decision": "FINAL_MICRO_LIVE_GO_NO_GO_GATE_SPEC_READY_FOR_REVIEW_NOT_EXECUTION",
        "next_phase": "Phase 16.17 — Micro-Live Manual Approval Record"
    }

    OUTPUT_PATH.write_text(json.dumps(report, indent=2))

    print(f"Report written to: {OUTPUT_PATH}")
    print(f"all_inputs_present={report['all_inputs_present']}")
    print(f"testnet_soak_passed={report['testnet_soak_passed']}")
    print(f"safe_mode_active={safe_mode_active}")
    print(f"approved_for_micro_live_execution={report['approved_for_micro_live_execution']}")
    print(f"decision={report['decision']}")

if __name__ == "__main__":
    main()
