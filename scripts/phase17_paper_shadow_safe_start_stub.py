import argparse
import json
import os
import subprocess
import time
from pathlib import Path

OUT = Path("data/processed/phase17_paper_shadow_safe_start_stub.json")
RUNTIME_OUT = Path("runtime/phase17_paper_shadow_safe_start_stub.json")
START_DIR = Path("data/processed/paper_shadow_safe_start")

READINESS_INPUT = Path("data/processed/phase17_paper_shadow_start_readiness_check.json")
RUNTIME_READINESS = Path("runtime/phase17_paper_shadow_start_readiness_check.json")
HARNESS_STATE = Path("runtime/phase17_paper_shadow_state.json")
MANUAL_APPROVAL = Path("runtime/phase17_paper_shadow_manual_approval_record.json")

def run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True)

def git_clean():
    return run(["git", "status", "--short"]).stdout.strip() == ""

def load_json(path):
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except Exception:
        return {}

def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2))

def safety_flags():
    return {
        "BINANCE_TESTNET": os.getenv("BINANCE_TESTNET", ""),
        "BINANCE_USE_TESTNET": os.getenv("BINANCE_USE_TESTNET", ""),
        "BINANCE_ENABLE_LIVE_TRADING": os.getenv("BINANCE_ENABLE_LIVE_TRADING", ""),
        "LIVE_TRADING_ALLOWED": os.getenv("LIVE_TRADING_ALLOWED", ""),
    }

def is_safe_mode(flags):
    return flags["BINANCE_ENABLE_LIVE_TRADING"] == "false" and flags["LIVE_TRADING_ALLOWED"] == "false"

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--action", choices=["create", "start", "status"], default="create")
    args = parser.parse_args()

    flags = safety_flags()
    safe_mode = is_safe_mode(flags)

    readiness = load_json(READINESS_INPUT)
    runtime_readiness = load_json(RUNTIME_READINESS)
    harness_state = load_json(HARNESS_STATE)
    manual_approval = load_json(MANUAL_APPROVAL)

    readiness_passed = readiness.get("readiness_passed") is True or runtime_readiness.get("readiness_passed") is True
    manual_approval_provided = manual_approval.get("manual_approval_provided") is True
    approved_for_paper_shadow_start = manual_approval.get("approved_for_paper_shadow_start") is True

    start_checks = {
        "safe_mode_active": safe_mode,
        "readiness_input_present": READINESS_INPUT.exists(),
        "runtime_readiness_present": RUNTIME_READINESS.exists(),
        "harness_state_present": HARNESS_STATE.exists(),
        "manual_approval_present": MANUAL_APPROVAL.exists(),
        "readiness_passed": readiness_passed,
        "manual_approval_provided": manual_approval_provided,
        "approved_for_paper_shadow_start": approved_for_paper_shadow_start,
        "paper_shadow_not_started": harness_state.get("paper_shadow_started") is not True,
        "exchange_order_submission_disabled": harness_state.get("exchange_order_submission") is False,
        "real_capital_disabled": harness_state.get("real_capital_allowed") is False,
        "live_trading_disabled": harness_state.get("live_trading_enabled") is False,
    }

    blockers = [k for k, v in start_checks.items() if v is not True]
    start_allowed = all(start_checks.values())

    START_DIR.mkdir(parents=True, exist_ok=True)

    if args.action == "status":
        if RUNTIME_OUT.exists():
            print(RUNTIME_OUT.read_text())
        else:
            print(json.dumps({"status": "no_runtime_start_stub_found"}, indent=2))
        return

    if args.action == "start":
        if start_allowed:
            decision = "PAPER_SHADOW_SAFE_START_STUB_READY_ACTUAL_START_NOT_IMPLEMENTED_NOT_STARTED"
            start_attempt_status = "START_STUB_READY_BUT_ACTUAL_EXECUTION_NOT_IMPLEMENTED"
        else:
            decision = "PAPER_SHADOW_SAFE_START_REJECTED_READINESS_OR_APPROVAL_FAILED_NOT_STARTED"
            start_attempt_status = "START_REJECTED"
    else:
        decision = "PAPER_SHADOW_SAFE_START_STUB_CREATED_NOT_STARTED"
        start_attempt_status = "STUB_CREATED_NOT_STARTED"

    runtime_state = {
        "phase": "phase_17_22_paper_shadow_safe_start_stub_runtime",
        "updated_at_unix": int(time.time()),
        "action_requested": args.action,
        "start_attempt_status": start_attempt_status,
        "start_allowed": False,
        "start_checks": start_checks,
        "blockers": blockers,
        "paper_shadow_started": False,
        "paper_shadow_completed": False,
        "exchange_order_submission": False,
        "real_capital_allowed": False,
        "live_trading_enabled": False,
        "approved_for_paper_shadow_start": False,
        "approved_for_micro_live_execution": False,
        "approved_for_real_live_trading": False,
        "decision": decision
    }

    write_json(RUNTIME_OUT, runtime_state)

    start_attempt_file = START_DIR / "paper_shadow_safe_start_attempt.json"
    write_json(start_attempt_file, runtime_state)

    report = {
        "phase": "phase_17_22_paper_shadow_safe_start_stub",
        "generated_at_unix": int(time.time()),
        "scope": "paper_shadow_safe_start_stub_only",
        "action_requested": args.action,
        "safety_flags": flags,
        "safe_mode_active": safe_mode,
        "git_working_tree_clean": git_clean(),
        "start_checks": start_checks,
        "blockers": blockers,
        "start_allowed": False,
        "paper_shadow_started": False,
        "paper_shadow_completed": False,
        "exchange_order_submission": False,
        "real_capital_allowed": False,
        "live_trading_enabled": False,
        "approved_for_paper_shadow_start": False,
        "approved_for_micro_live_execution": False,
        "approved_for_real_live_trading": False,
        "runtime_start_stub": str(RUNTIME_OUT),
        "start_attempt_file": str(start_attempt_file),
        "decision": decision,
        "next_phase": "Phase 17.23 — Paper Shadow Blocked Start Review",
        "safety_notes": [
            "This phase is a safe start stub only.",
            "This phase does not start paper shadow execution.",
            "This phase does not approve micro-live execution.",
            "This phase does not approve real live trading.",
            "This phase does not submit Binance orders.",
            "Start remains blocked until manual paper-shadow-only approval is provided."
        ]
    }

    write_json(OUT, report)

    print(f"Report written to: {OUT}")
    print(f"Runtime start stub written to: {RUNTIME_OUT}")
    print(f"safe_mode_active={safe_mode}")
    print(f"action_requested={args.action}")
    print(f"start_allowed=False")
    print(f"paper_shadow_started=False")
    print(f"exchange_order_submission=False")
    print(f"approved_for_paper_shadow_start=False")
    print(f"approved_for_micro_live_execution=False")
    print(f"approved_for_real_live_trading=False")
    print(f"decision={decision}")

if __name__ == "__main__":
    main()
