import argparse
import json
import os
import subprocess
import time
from pathlib import Path

OUT = Path("data/processed/phase17_paper_shadow_manual_approval_update_gate.json")
RUNTIME_OUT = Path("runtime/phase17_paper_shadow_manual_approval_update_gate.json")
UPDATE_DIR = Path("data/processed/paper_shadow_manual_approval_update")

BLOCKED_REVIEW = Path("data/processed/phase17_paper_shadow_blocked_start_review.json")
MANUAL_APPROVAL_RECORD = Path("runtime/phase17_paper_shadow_manual_approval_record.json")
HARNESS_STATE = Path("runtime/phase17_paper_shadow_state.json")

REQUIRED_CONFIRMATION_TEXT = "I approve PAPER SHADOW ONLY with real capital disabled and exchange order submission disabled."

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

def safe_mode(flags):
    return flags["BINANCE_ENABLE_LIVE_TRADING"] == "false" and flags["LIVE_TRADING_ALLOWED"] == "false"

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--action", choices=["create", "status", "approve"], default="create")
    parser.add_argument("--approver-name", default="")
    parser.add_argument("--approver-role", default="")
    parser.add_argument("--confirmation-text", default="")
    args = parser.parse_args()

    flags = safety_flags()
    is_safe = safe_mode(flags)

    blocked_review = load_json(BLOCKED_REVIEW)
    manual_runtime = load_json(MANUAL_APPROVAL_RECORD)
    harness_state = load_json(HARNESS_STATE)

    approval_checks = {
        "safe_mode_active": is_safe,
        "blocked_review_present": BLOCKED_REVIEW.exists(),
        "manual_approval_runtime_present": MANUAL_APPROVAL_RECORD.exists(),
        "harness_state_present": HARNESS_STATE.exists(),
        "paper_shadow_not_started": harness_state.get("paper_shadow_started") is not True,
        "exchange_order_submission_disabled": harness_state.get("exchange_order_submission") is False,
        "real_capital_disabled": harness_state.get("real_capital_allowed") is False,
        "live_trading_disabled": harness_state.get("live_trading_enabled") is False,
        "approver_name_present": bool(args.approver_name.strip()),
        "approver_role_present": bool(args.approver_role.strip()),
        "confirmation_text_matches": args.confirmation_text == REQUIRED_CONFIRMATION_TEXT,
    }

    blockers = [k for k, v in approval_checks.items() if v is not True]

    approve_requested = args.action == "approve"
    approval_allowed = approve_requested and all(approval_checks.values())

    UPDATE_DIR.mkdir(parents=True, exist_ok=True)

    if args.action == "status":
        if RUNTIME_OUT.exists():
            print(RUNTIME_OUT.read_text())
        else:
            print(json.dumps({"status": "no_phase_17_24_runtime_gate_found"}, indent=2))
        return

    if approval_allowed:
        decision = "PAPER_SHADOW_MANUAL_APPROVAL_UPDATED_PAPER_SHADOW_ONLY_APPROVED_NOT_STARTED"
        manual_approval_provided = True
        approved_for_paper_shadow_start = True
        approval_status = "PAPER_SHADOW_ONLY_APPROVED_NOT_STARTED"
    elif approve_requested:
        decision = "PAPER_SHADOW_MANUAL_APPROVAL_UPDATE_REJECTED_CHECKS_FAILED_NOT_APPROVED"
        manual_approval_provided = False
        approved_for_paper_shadow_start = False
        approval_status = "APPROVAL_REJECTED"
    else:
        decision = "PAPER_SHADOW_MANUAL_APPROVAL_UPDATE_GATE_CREATED_NOT_APPROVED"
        manual_approval_provided = False
        approved_for_paper_shadow_start = False
        approval_status = "GATE_CREATED_NOT_APPROVED"

    updated_manual_record = {
        "phase": "phase_17_24_paper_shadow_manual_approval_update_gate_runtime",
        "updated_at_unix": int(time.time()),
        "action_requested": args.action,
        "manual_approval_provided": manual_approval_provided,
        "approved_for_paper_shadow_start": approved_for_paper_shadow_start,
        "approval_scope": "paper_shadow_only",
        "approver_name": args.approver_name if manual_approval_provided else None,
        "approver_role": args.approver_role if manual_approval_provided else None,
        "required_confirmation_text": REQUIRED_CONFIRMATION_TEXT,
        "confirmation_text_matches": args.confirmation_text == REQUIRED_CONFIRMATION_TEXT,
        "real_capital_allowed": False,
        "exchange_order_submission_allowed": False,
        "live_trading_allowed": False,
        "micro_live_execution_allowed": False,
        "paper_shadow_started": False,
        "approved_for_micro_live_execution": False,
        "approved_for_real_live_trading": False,
        "approval_status": approval_status,
        "blockers": blockers,
        "decision": decision
    }

    write_json(RUNTIME_OUT, updated_manual_record)

    update_detail_file = UPDATE_DIR / "paper_shadow_manual_approval_update_detail.json"
    write_json(update_detail_file, updated_manual_record)

    report = {
        "phase": "phase_17_24_paper_shadow_manual_approval_update_gate",
        "generated_at_unix": int(time.time()),
        "scope": "paper_shadow_manual_approval_update_gate_only",
        "action_requested": args.action,
        "safety_flags": flags,
        "safe_mode_active": is_safe,
        "git_working_tree_clean": git_clean(),
        "blocked_review_present": BLOCKED_REVIEW.exists(),
        "manual_approval_runtime_present": MANUAL_APPROVAL_RECORD.exists(),
        "harness_state_present": HARNESS_STATE.exists(),
        "required_confirmation_text": REQUIRED_CONFIRMATION_TEXT,
        "approval_checks": approval_checks,
        "blockers": blockers,
        "manual_approval_provided": manual_approval_provided,
        "approved_for_paper_shadow_start": approved_for_paper_shadow_start,
        "paper_shadow_started": False,
        "exchange_order_submission": False,
        "real_capital_allowed": False,
        "live_trading_enabled": False,
        "approved_for_micro_live_execution": False,
        "approved_for_real_live_trading": False,
        "runtime_update_gate": str(RUNTIME_OUT),
        "update_detail_file": str(update_detail_file),
        "decision": decision,
        "next_phase": "Phase 17.25 — Paper Shadow Start Readiness Recheck",
        "safety_notes": [
            "This phase creates or evaluates a paper-shadow-only manual approval update.",
            "This phase does not start paper shadow execution.",
            "This phase does not approve micro-live execution.",
            "This phase does not approve real live trading.",
            "This phase does not submit Binance orders.",
            "Real capital and exchange order submission remain disabled."
        ]
    }

    write_json(OUT, report)

    print(f"Report written to: {OUT}")
    print(f"Runtime update gate written to: {RUNTIME_OUT}")
    print(f"safe_mode_active={is_safe}")
    print(f"action_requested={args.action}")
    print(f"manual_approval_provided={manual_approval_provided}")
    print(f"approved_for_paper_shadow_start={approved_for_paper_shadow_start}")
    print("paper_shadow_started=False")
    print("exchange_order_submission=False")
    print("approved_for_micro_live_execution=False")
    print("approved_for_real_live_trading=False")
    print(f"decision={decision}")

if __name__ == "__main__":
    main()
