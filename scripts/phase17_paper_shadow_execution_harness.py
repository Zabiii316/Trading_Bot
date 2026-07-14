import argparse
import json
import os
import subprocess
import time
from pathlib import Path

OUT = Path("data/processed/phase17_paper_shadow_execution_harness.json")
PLAN_INPUT = Path("data/processed/phase17_paper_shadow_trading_plan.json")
STATE_FILE = Path("runtime/phase17_paper_shadow_state.json")
HARNESS_DIR = Path("data/processed/paper_shadow_execution")

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

def build_harness(action):
    flags = safety_flags()
    is_safe = safe_mode(flags)

    plan_report = load_json(PLAN_INPUT)
    paper_shadow_plans = plan_report.get("paper_shadow_plans", [])

    HARNESS_DIR.mkdir(parents=True, exist_ok=True)

    harness_sessions = []

    for idx, plan in enumerate(paper_shadow_plans, start=1):
        session_id = f"paper_shadow_session_{idx}_{str(plan.get('symbol', 'unknown')).lower()}"

        session = {
            "session_id": session_id,
            "source_plan_id": plan.get("paper_shadow_plan_id"),
            "source_candidate_id": plan.get("source_candidate_id"),
            "symbol": plan.get("symbol"),
            "candidate_parameters": plan.get("candidate_parameters"),
            "mode": "paper_shadow_only",
            "exchange_order_submission": False,
            "real_capital_allowed": False,
            "live_trading_enabled": False,
            "duration_days": plan.get("duration_days"),
            "minimum_shadow_signals_required": plan.get("minimum_shadow_signals_required"),
            "required_metrics": plan.get("required_metrics", []),
            "status": "HARNESS_CREATED_NOT_STARTED",
            "approved_for_micro_live_execution": False,
            "approved_for_real_live_trading": False,
        }

        session_path = HARNESS_DIR / f"{session_id}.json"
        write_json(session_path, session)
        session["session_path"] = str(session_path)

        harness_sessions.append(session)

    if action == "start":
        session_status = "PAPER_SHADOW_START_REQUEST_REJECTED_MANUAL_START_GATE_REQUIRED"
    else:
        session_status = "PAPER_SHADOW_HARNESS_CREATED_NOT_STARTED"

    if harness_sessions:
        decision = "PAPER_SHADOW_EXECUTION_HARNESS_CREATED_NOT_STARTED_NOT_APPROVED_FOR_EXECUTION"
        next_phase = "Phase 17.19 — Paper Shadow Start Gate"
    else:
        decision = "PAPER_SHADOW_EXECUTION_HARNESS_SKIPPED_NO_PAPER_SHADOW_PLANS_STRATEGY_REWORK_REQUIRED"
        next_phase = "Phase 17.19 — Paper Shadow Start Gate or Strategy Redesign"

    state = {
        "phase": "phase_17_18_paper_shadow_execution_harness_state",
        "updated_at_unix": int(time.time()),
        "session_status": session_status,
        "paper_shadow_started": False,
        "paper_shadow_completed": False,
        "exchange_order_submission": False,
        "live_trading_enabled": False,
        "real_capital_allowed": False,
        "harness_session_count": len(harness_sessions),
        "harness_sessions": harness_sessions,
        "approved_for_micro_live_execution": False,
        "approved_for_real_live_trading": False,
    }

    write_json(STATE_FILE, state)

    report = {
        "phase": "phase_17_18_paper_shadow_execution_harness",
        "generated_at_unix": int(time.time()),
        "scope": "paper_shadow_execution_harness_only",
        "action_requested": action,
        "safety_flags": flags,
        "safe_mode_active": is_safe,
        "git_working_tree_clean": git_clean(),
        "plan_input_present": PLAN_INPUT.exists(),
        "paper_shadow_plan_count": len(paper_shadow_plans),
        "harness_session_count": len(harness_sessions),
        "state_file": str(STATE_FILE),
        "harness_sessions": harness_sessions,
        "paper_shadow_started": False,
        "paper_shadow_completed": False,
        "exchange_order_submission": False,
        "live_trading_enabled": False,
        "real_capital_allowed": False,
        "approved_for_micro_live_execution": False,
        "approved_for_real_live_trading": False,
        "decision": decision,
        "next_phase": next_phase,
        "safety_notes": [
            "This phase creates the paper shadow execution harness only.",
            "This phase does not start paper shadow trading.",
            "This phase does not approve live trading.",
            "This phase does not approve micro-live execution.",
            "This phase does not submit Binance orders.",
            "A separate manual start gate is required before any paper shadow session can run."
        ],
    }

    write_json(OUT, report)

    print(f"Report written to: {OUT}")
    print(f"State written to: {STATE_FILE}")
    print(f"safe_mode_active={is_safe}")
    print(f"paper_shadow_plan_count={len(paper_shadow_plans)}")
    print(f"harness_session_count={len(harness_sessions)}")
    print("paper_shadow_started=False")
    print("exchange_order_submission=False")
    print("approved_for_micro_live_execution=False")
    print("approved_for_real_live_trading=False")
    print(f"decision={decision}")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--action", choices=["create", "status", "start"], default="create")
    args = parser.parse_args()

    if args.action == "status" and STATE_FILE.exists():
        print(STATE_FILE.read_text())
        return

    build_harness(args.action)

if __name__ == "__main__":
    main()
