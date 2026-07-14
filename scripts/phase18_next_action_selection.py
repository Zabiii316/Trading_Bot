import argparse
import json
import os
import subprocess
import time
from pathlib import Path

OUT = Path("data/processed/phase18_next_action_selection.json")
RUNTIME_OUT = Path("runtime/phase18_next_action_selection_state.json")
NEXT_ACTION_DIR = Path("data/processed/phase18_next_action")

PHASE17_CLOSEOUT = Path("data/processed/phase17_safety_closeout_next_action_options.json")
PHASE17_RUNTIME_CLOSEOUT = Path("runtime/phase17_safety_closeout_state.json")

VALID_OPTIONS = [
    "remain_on_hold",
    "paper_shadow_approval_path",
    "strategy_rework_path",
    "expand_historical_data_path",
    "monitoring_dashboard_review"
]

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

def next_phase_for_option(option):
    if option == "remain_on_hold":
        return "Phase 18.2 — Hold State Monitoring Plan"
    if option == "paper_shadow_approval_path":
        return "Phase 18.2 — Paper Shadow Approval Workflow Plan"
    if option == "strategy_rework_path":
        return "Phase 18.2 — Strategy Rework Backlog"
    if option == "expand_historical_data_path":
        return "Phase 18.2 — Historical Data Expansion Plan"
    if option == "monitoring_dashboard_review":
        return "Phase 18.2 — Monitoring Dashboard Review Plan"
    return "Phase 18.2 — Hold State Monitoring Plan"

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--option", choices=VALID_OPTIONS, default="remain_on_hold")
    args = parser.parse_args()

    flags = safety_flags()
    is_safe = safe_mode(flags)

    closeout = load_json(PHASE17_CLOSEOUT)
    runtime_closeout = load_json(PHASE17_RUNTIME_CLOSEOUT)

    phase17_closed_safely = (
        closeout.get("phase17_closed_safely") is True
        or runtime_closeout.get("phase17_closed_safely") is True
    )

    hold_state_confirmed = (
        closeout.get("hold_state_confirmed") is True
        or runtime_closeout.get("hold_state_confirmed") is True
    )

    paper_shadow_started = (
        closeout.get("paper_shadow_started") is True
        or runtime_closeout.get("paper_shadow_started") is True
    )

    approved_for_paper_shadow_start = (
        closeout.get("approved_for_paper_shadow_start") is True
        or runtime_closeout.get("approved_for_paper_shadow_start") is True
    )

    exchange_order_submission = (
        closeout.get("exchange_order_submission") is True
        or runtime_closeout.get("exchange_order_submission") is True
    )

    approved_for_micro_live_execution = (
        closeout.get("approved_for_micro_live_execution") is True
        or runtime_closeout.get("approved_for_micro_live_execution") is True
    )

    approved_for_real_live_trading = (
        closeout.get("approved_for_real_live_trading") is True
        or runtime_closeout.get("approved_for_real_live_trading") is True
    )

    selection_checks = {
        "safe_mode_active": is_safe,
        "phase17_closeout_present": PHASE17_CLOSEOUT.exists(),
        "phase17_runtime_closeout_present": PHASE17_RUNTIME_CLOSEOUT.exists(),
        "phase17_closed_safely": phase17_closed_safely,
        "hold_state_confirmed": hold_state_confirmed,
        "paper_shadow_not_started": paper_shadow_started is False,
        "paper_shadow_start_not_approved": approved_for_paper_shadow_start is False,
        "exchange_order_submission_disabled": exchange_order_submission is False,
        "micro_live_not_approved": approved_for_micro_live_execution is False,
        "real_live_not_approved": approved_for_real_live_trading is False,
    }

    blockers = [k for k, v in selection_checks.items() if v is not True]
    selection_valid = all(selection_checks.values())

    if not selection_valid:
        decision = "PHASE_18_NEXT_ACTION_SELECTION_BLOCKED_PHASE17_CLOSEOUT_REVIEW_REQUIRED"
        next_phase = "Phase 18.2 — Phase 17 Closeout Review"
    elif args.option == "remain_on_hold":
        decision = "PHASE_18_NEXT_ACTION_SELECTED_REMAIN_ON_HOLD_NOT_APPROVED_FOR_EXECUTION"
        next_phase = next_phase_for_option(args.option)
    elif args.option == "paper_shadow_approval_path":
        decision = "PHASE_18_NEXT_ACTION_SELECTED_PAPER_SHADOW_APPROVAL_PATH_NOT_APPROVED_FOR_EXECUTION"
        next_phase = next_phase_for_option(args.option)
    elif args.option == "strategy_rework_path":
        decision = "PHASE_18_NEXT_ACTION_SELECTED_STRATEGY_REWORK_PATH_NOT_APPROVED_FOR_EXECUTION"
        next_phase = next_phase_for_option(args.option)
    elif args.option == "expand_historical_data_path":
        decision = "PHASE_18_NEXT_ACTION_SELECTED_HISTORICAL_DATA_EXPANSION_PATH_NOT_APPROVED_FOR_EXECUTION"
        next_phase = next_phase_for_option(args.option)
    else:
        decision = "PHASE_18_NEXT_ACTION_SELECTED_MONITORING_DASHBOARD_REVIEW_NOT_APPROVED_FOR_EXECUTION"
        next_phase = next_phase_for_option(args.option)

    NEXT_ACTION_DIR.mkdir(parents=True, exist_ok=True)

    action_record = {
        "phase": "phase_18_1_next_action_selection_record",
        "created_at_unix": int(time.time()),
        "selected_option": args.option,
        "valid_options": VALID_OPTIONS,
        "selection_checks": selection_checks,
        "blockers": blockers,
        "selection_valid": selection_valid,
        "paper_shadow_started": False,
        "approved_for_paper_shadow_start": False,
        "exchange_order_submission": False,
        "approved_for_micro_live_execution": False,
        "approved_for_real_live_trading": False,
        "decision": decision,
        "next_phase": next_phase,
    }

    action_file = NEXT_ACTION_DIR / "phase18_next_action_selection_record.json"
    write_json(action_file, action_record)
    write_json(RUNTIME_OUT, action_record)

    report = {
        "phase": "phase_18_1_next_action_selection",
        "generated_at_unix": int(time.time()),
        "scope": "phase_18_next_action_selection_only",
        "selected_option": args.option,
        "valid_options": VALID_OPTIONS,
        "safety_flags": flags,
        "safe_mode_active": is_safe,
        "git_working_tree_clean": git_clean(),
        "selection_checks": selection_checks,
        "blockers": blockers,
        "selection_valid": selection_valid,
        "paper_shadow_started": False,
        "approved_for_paper_shadow_start": False,
        "exchange_order_submission": False,
        "real_capital_allowed": False,
        "live_trading_enabled": False,
        "approved_for_micro_live_execution": False,
        "approved_for_real_live_trading": False,
        "action_record_file": str(action_file),
        "runtime_next_action_file": str(RUNTIME_OUT),
        "decision": decision,
        "next_phase": next_phase,
        "safety_notes": [
            "This phase selects the next action path only.",
            "This phase does not start paper shadow execution.",
            "This phase does not approve micro-live execution.",
            "This phase does not approve real live trading.",
            "This phase does not submit Binance orders.",
            "Real capital and exchange order submission remain disabled."
        ]
    }

    write_json(OUT, report)

    print(f"Report written to: {OUT}")
    print(f"Runtime next action written to: {RUNTIME_OUT}")
    print(f"safe_mode_active={is_safe}")
    print(f"selected_option={args.option}")
    print(f"selection_valid={selection_valid}")
    print("paper_shadow_started=False")
    print("approved_for_paper_shadow_start=False")
    print("exchange_order_submission=False")
    print("approved_for_micro_live_execution=False")
    print("approved_for_real_live_trading=False")
    print(f"decision={decision}")

if __name__ == "__main__":
    main()
