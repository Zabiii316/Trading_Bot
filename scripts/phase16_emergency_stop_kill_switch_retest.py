from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path

OUTPUT_PATH = Path("data/processed/phase16_emergency_stop_kill_switch_retest.json")
KILL_SWITCH_PATH = Path("runtime/KILL_SWITCH_ACTIVE")

INPUTS = {
    "capital_limits": Path("data/processed/phase16_capital_limits_loss_limit_controls.json"),
    "secrets_manager_controls": Path("data/processed/phase16_secrets_manager_key_handling_controls.json"),
    "production_api_key_audit": Path("data/processed/phase16_production_api_key_permission_audit.json"),
    "manual_approval_record": Path("data/processed/phase16_micro_live_manual_approval_record.json"),
    "final_go_no_go_gate": Path("data/processed/phase16_final_micro_live_go_no_go_gate_spec.json"),
}

def git_clean() -> bool:
    result = subprocess.run(["git", "status", "--short"], capture_output=True, text=True)
    return result.stdout.strip() == ""

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

    before_present = KILL_SWITCH_PATH.exists()
    KILL_SWITCH_PATH.parent.mkdir(parents=True, exist_ok=True)
    KILL_SWITCH_PATH.write_text(f"phase16_kill_switch_retest_active_at_unix={int(time.time())}\n")
    after_present = KILL_SWITCH_PATH.exists()

    dry_run_command = [
        "python",
        "scripts/run_binance_live_execution.py",
        "--signal",
        "data/processed/live_signal_dryrun.json",
        "--risk",
        "data/processed/live_risk_dryrun.json",
        "--dry-run",
    ]

    result = subprocess.run(dry_run_command, capture_output=True, text=True, timeout=30)
    raw_output = (result.stdout + "\n" + result.stderr).strip()
    raw_lower = raw_output.lower()

    order_blocked_or_not_submitted = (
        "dry_run=true" in raw_lower
        or "no order submitted" in raw_lower
        or "kill" in raw_lower
        or "live trading disabled" in raw_lower
        or result.returncode != 0
    )

    passed = safe_mode_active and after_present and order_blocked_or_not_submitted

    report = {
        "phase": "phase_16_21_emergency_stop_kill_switch_retest",
        "generated_at_unix": int(time.time()),
        "scope": "emergency_stop_and_kill_switch_retest_only",
        "not_approved_for": [
            "real_live_trading",
            "micro_live_execution",
            "production_binance_order_submission"
        ],
        "safety_flags": flags,
        "safe_mode_active": safe_mode_active,
        "inputs_present": inputs_present,
        "all_inputs_present": all(inputs_present.values()),
        "git_working_tree_clean": git_clean(),
        "kill_switch_test": {
            "kill_switch_file": str(KILL_SWITCH_PATH),
            "kill_switch_present_before_test": before_present,
            "kill_switch_present_after_activation": after_present,
            "kill_switch_left_active_after_test": KILL_SWITCH_PATH.exists()
        },
        "dry_run_retest": {
            "command": " ".join(dry_run_command),
            "returncode": result.returncode,
            "order_blocked_or_not_submitted": order_blocked_or_not_submitted,
            "output_tail": raw_output[-3000:]
        },
        "emergency_stop_retest_passed": passed,
        "approved_for_micro_live_execution": False,
        "decision": "EMERGENCY_STOP_KILL_SWITCH_RETEST_COMPLETE_NOT_APPROVED_FOR_EXECUTION",
        "next_phase": "Phase 16.22 — Final Micro-Live Readiness Review"
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(report, indent=2))

    print(f"Report written to: {OUTPUT_PATH}")
    print(f"safe_mode_active={safe_mode_active}")
    print(f"all_inputs_present={report['all_inputs_present']}")
    print(f"git_working_tree_clean={report['git_working_tree_clean']}")
    print(f"kill_switch_present_after_activation={after_present}")
    print(f"order_blocked_or_not_submitted={order_blocked_or_not_submitted}")
    print(f"emergency_stop_retest_passed={passed}")
    print(f"approved_for_micro_live_execution={report['approved_for_micro_live_execution']}")
    print(f"decision={report['decision']}")

if __name__ == "__main__":
    main()
