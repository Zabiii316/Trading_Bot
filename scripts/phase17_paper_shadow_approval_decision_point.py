import argparse
import json
import os
import subprocess
import time
from pathlib import Path

OUT = Path("data/processed/phase17_paper_shadow_approval_decision_point.json")
RUNTIME_OUT = Path("runtime/phase17_paper_shadow_approval_decision_point.json")
DECISION_DIR = Path("data/processed/paper_shadow_approval_decision")

START_ATTEMPT_REVIEW = Path("data/processed/phase17_paper_shadow_start_attempt_review.json")
RUNTIME_START_ATTEMPT_REVIEW = Path("runtime/phase17_paper_shadow_start_attempt_review.json")
APPROVAL_UPDATE = Path("data/processed/phase17_paper_shadow_manual_approval_update_gate.json")
RUNTIME_APPROVAL_UPDATE = Path("runtime/phase17_paper_shadow_manual_approval_update_gate.json")
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
    parser.add_argument("--decision", choices=["hold", "reject", "approve-paper-shadow-only"], default="hold")
    parser.add_argument("--approver-name", default="")
    parser.add_argument("--approver-role", default="")
    parser.add_argument("--confirmation-text", default="")
    args = parser.parse_args()

    flags = safety_flags()
    is_safe = safe_mode(flags)

    start_attempt = load_json(START_ATTEMPT_REVIEW)
    runtime_start_attempt = load_json(RUNTIME_START_ATTEMPT_REVIEW)
    approval_update = load_json(APPROVAL_UPDATE)
    runtime_approval_update = load_json(RUNTIME_APPROVAL_UPDATE)
    harness_state = load_json(HARNESS_STATE)

    paper_shadow_started = (
        start_attempt.get("paper_shadow_started") is True
        or runtime_start_attempt.get("paper_shadow_started") is True
        or harness_state.get("paper_shadow_started") is True
    )

    exchange_order_submission = (
        start_attempt.get("exchange_order_submission") is True
        or runtime_start_attempt.get("exchange_order_submission") is True
        or harness_state.get("exchange_order_submission") is True
    )

    real_capital_allowed = (
        start_attempt.get("real_capital_allowed") is True
        or runtime_start_attempt.get("real_capital_allowed") is True
        or harness_state.get("real_capital_allowed") is True
    )

    live_trading_enabled = (
        start_attempt.get("live_trading_enabled") is True
        or runtime_start_attempt.get("live_trading_enabled") is True
        or harness_state.get("live_trading_enabled") is True
    )

    approval_checks = {
        "safe_mode_active": is_safe,
        "start_attempt_review_present": START_ATTEMPT_REVIEW.exists(),
        "runtime_start_attempt_review_present": RUNTIME_START_ATTEMPT_REVIEW.exists(),
        "approval_update_present": APPROVAL_UPDATE.exists(),
        "runtime_approval_update_present": RUNTIME_APPROVAL_UPDATE.exists(),
        "harness_state_present": HARNESS_STATE.exists(),
        "paper_shadow_not_started": paper_shadow_started is False,
        "exchange_order_submission_disabled": exchange_order_submission is False,
        "real_capital_disabled": real_capital_allowed is False,
        "live_trading_disabled": live_trading_enabled is False,
        "approver_name_present": bool(args.approver_name.strip()),
        "approver_role_present": bool(args.approver_role.strip()),
        "confirmation_text_matches": args.confirmation_text == REQUIRED_CONFIRMATION_TEXT,
    }

    blockers = [k for k, v in approval_checks.items() if v is not True]

    approval_requested = args.decision == "approve-paper-shadow-only"
    approval_allowed = approval_requested and all(approval_checks.values())

    if approval_allowed:
        decision = "PAPER_SHADOW_APPROVAL_DECISION_POINT_APPROVED_PAPER_SHADOW_ONLY_NOT_STARTED"
        manual_decision_status = "APPROVED_PAPER_SHADOW_ONLY_NOT_STARTED"
        manual_approval_provided = True
        approved_for_paper_shadow_start = True
    elif args.decision == "reject":
        decision = "PAPER_SHADOW_APPROVAL_DECISION_POINT_REJECTED_NOT_STARTED"
        manual_decision_status = "REJECTED_NOT_STARTED"
        manual_approval_provided = False
        approved_for_paper_shadow_start = False
    elif approval_requested:
        decision = "PAPER_SHADOW_APPROVAL_DECISION_POINT_APPROVAL_REJECTED_CHECKS_FAILED_NOT_STARTED"
        manual_decision_status = "APPROVAL_REJECTED_CHECKS_FAILED"
        manual_approval_provided = False
        approved_for_paper_shadow_start = False
    else:
        decision = "PAPER_SHADOW_APPROVAL_DECISION_POINT_CREATED_HOLD_NOT_APPROVED_NOT_STARTED"
        manual_decision_status = "HOLD_NOT_APPROVED_NOT_STARTED"
        manual_approval_provided = False
        approved_for_paper_shadow_start = False

    DECISION_DIR.mkdir(parents=True, exist_ok=True)

    decision_detail = {
        "phase": "phase_17_27_paper_shadow_approval_decision_point_detail",
        "created_at_unix": int(time.time()),
        "decision_requested": args.decision,
        "manual_decision_status": manual_decision_status,
        "approval_scope": "paper_shadow_only",
        "required_confirmation_text": REQUIRED_CONFIRMATION_TEXT,
        "approver_name": args.approver_name if manual_approval_provided else None,
        "approver_role": args.approver_role if manual_approval_provided else None,
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
        "decision": decision,
    }

    decision_detail_file = DECISION_DIR / "paper_shadow_approval_decision_detail.json"
    write_json(decision_detail_file, decision_detail)
    write_json(RUNTIME_OUT, decision_detail)

    report = {
        "phase": "phase_17_27_paper_shadow_approval_decision_point",
        "generated_at_unix": int(time.time()),
        "scope": "paper_shadow_approval_decision_point_only",
        "decision_requested": args.decision,
        "safety_flags": flags,
        "safe_mode_active": is_safe,
        "git_working_tree_clean": git_clean(),
        "approval_checks": approval_checks,
        "blockers": blockers,
        "manual_decision_status": manual_decision_status,
        "manual_approval_provided": manual_approval_provided,
        "approved_for_paper_shadow_start": approved_for_paper_shadow_start,
        "paper_shadow_started": False,
        "paper_shadow_completed": False,
        "exchange_order_submission": False,
        "real_capital_allowed": False,
        "live_trading_enabled": False,
        "approved_for_micro_live_execution": False,
        "approved_for_real_live_trading": False,
        "runtime_decision_file": str(RUNTIME_OUT),
        "decision_detail_file": str(decision_detail_file),
        "decision": decision,
        "next_phase": "Phase 17.28 — Paper Shadow Approval Decision Review",
        "safety_notes": [
            "This phase creates the paper shadow approval decision point only.",
            "This phase does not start paper shadow execution.",
            "This phase does not approve micro-live execution.",
            "This phase does not approve real live trading.",
            "This phase does not submit Binance orders.",
            "Real capital and exchange order submission remain disabled."
        ]
    }

    write_json(OUT, report)

    print(f"Report written to: {OUT}")
    print(f"Runtime decision written to: {RUNTIME_OUT}")
    print(f"safe_mode_active={is_safe}")
    print(f"decision_requested={args.decision}")
    print(f"manual_approval_provided={manual_approval_provided}")
    print(f"approved_for_paper_shadow_start={approved_for_paper_shadow_start}")
    print("paper_shadow_started=False")
    print("exchange_order_submission=False")
    print("approved_for_micro_live_execution=False")
    print("approved_for_real_live_trading=False")
    print(f"decision={decision}")

if __name__ == "__main__":
    main()
