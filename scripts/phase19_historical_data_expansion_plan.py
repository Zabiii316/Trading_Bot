import json, os, subprocess, time
from pathlib import Path

OUT = Path("data/processed/phase19_historical_data_expansion_plan.json")
RUNTIME_OUT = Path("runtime/phase19_historical_data_expansion_plan_state.json")
PLAN_DIR = Path("data/processed/phase19_strategy_rework")

PHASE19_DECISION = Path("data/processed/phase19_strategy_rework_historical_data_expansion_decision.json")
PHASE18_CLOSEOUT = Path("data/processed/phase18_final_safety_closeout.json")

def run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True)

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

def git_clean():
    return run(["git", "status", "--short"]).stdout.strip() == ""

def git_head():
    r = run(["git", "rev-parse", "HEAD"])
    return r.stdout.strip() if r.returncode == 0 else None

flags = {
    "BINANCE_TESTNET": os.getenv("BINANCE_TESTNET", ""),
    "BINANCE_USE_TESTNET": os.getenv("BINANCE_USE_TESTNET", ""),
    "BINANCE_ENABLE_LIVE_TRADING": os.getenv("BINANCE_ENABLE_LIVE_TRADING", ""),
    "LIVE_TRADING_ALLOWED": os.getenv("LIVE_TRADING_ALLOWED", ""),
}

safe_mode = flags["BINANCE_ENABLE_LIVE_TRADING"] == "false" and flags["LIVE_TRADING_ALLOWED"] == "false"

phase19_decision = load_json(PHASE19_DECISION)
phase18_closeout = load_json(PHASE18_CLOSEOUT)

selected_option = phase19_decision.get("selected_option") or phase18_closeout.get("selected_option")
selected_path = phase19_decision.get("selected_phase19_path")
phase19_decision_ready = phase19_decision.get("phase19_decision_ready") is True
phase18_closed_safely = phase18_closeout.get("phase18_closed_safely") is True

plan_checks = {
    "safe_mode_active": safe_mode,
    "phase19_decision_present": PHASE19_DECISION.exists(),
    "phase19_decision_ready": phase19_decision_ready,
    "phase18_closeout_present": PHASE18_CLOSEOUT.exists(),
    "phase18_closed_safely": phase18_closed_safely,
    "selected_option_is_remain_on_hold": selected_option == "remain_on_hold",
    "selected_path_is_data_expansion_first": selected_path == "historical_data_expansion_first_then_strategy_rework",
    "paper_shadow_not_started": phase19_decision.get("paper_shadow_started") is False,
    "paper_shadow_start_not_approved": phase19_decision.get("approved_for_paper_shadow_start") is False,
    "exchange_order_submission_disabled": phase19_decision.get("exchange_order_submission") is False,
    "micro_live_not_approved": phase19_decision.get("approved_for_micro_live_execution") is False,
    "real_live_not_approved": phase19_decision.get("approved_for_real_live_trading") is False,
}

blockers = [k for k, v in plan_checks.items() if v is not True]
plan_ready = all(plan_checks.values())

decision = (
    "PHASE_19_HISTORICAL_DATA_EXPANSION_PLAN_CREATED_NOT_APPROVED_FOR_EXECUTION"
    if plan_ready else
    "PHASE_19_HISTORICAL_DATA_EXPANSION_PLAN_BLOCKED_REVIEW_REQUIRED"
)

next_phase = (
    "Phase 19.3 — Historical Data Expansion Manifest Builder"
    if plan_ready else
    "Phase 19.3 — Historical Data Expansion Plan Review"
)

plan = {
    "phase": "phase_19_2_historical_data_expansion_plan",
    "generated_at_unix": int(time.time()),
    "git_head": git_head(),
    "scope": "historical_data_expansion_plan_only_no_execution",
    "safety_flags": flags,
    "safe_mode_active": safe_mode,
    "git_working_tree_clean": git_clean(),
    "selected_option": selected_option,
    "selected_phase19_path": selected_path,
    "historical_data_expansion_plan_ready": plan_ready,
    "plan_checks": plan_checks,
    "blockers": blockers,
    "historical_data_requirements": {
        "mode": "offline_research_only",
        "minimum_target_symbols": ["BTCUSDT", "ETHUSDT", "BNBUSDT"],
        "optional_extra_symbols": ["SOLUSDT", "XRPUSDT", "ADAUSDT"],
        "minimum_timeframes": ["1m", "5m", "15m", "1h"],
        "preferred_history_window_days": 180,
        "minimum_history_window_days": 90
    },
    "paper_shadow_started": False,
    "approved_for_paper_shadow_start": False,
    "exchange_order_submission": False,
    "real_capital_allowed": False,
    "live_trading_enabled": False,
    "approved_for_micro_live_execution": False,
    "approved_for_real_live_trading": False,
    "decision": decision,
    "next_phase": next_phase,
}

PLAN_DIR.mkdir(parents=True, exist_ok=True)
plan_file = PLAN_DIR / "historical_data_expansion_plan.json"

write_json(OUT, plan)
write_json(RUNTIME_OUT, plan)
write_json(plan_file, plan)

print(f"Report written to: {OUT}")
print(f"Runtime plan written to: {RUNTIME_OUT}")
print(f"Plan written to: {plan_file}")
print(f"safe_mode_active={safe_mode}")
print(f"selected_option={selected_option}")
print(f"selected_phase19_path={selected_path}")
print(f"historical_data_expansion_plan_ready={plan_ready}")
print("paper_shadow_started=False")
print("approved_for_paper_shadow_start=False")
print("exchange_order_submission=False")
print("approved_for_micro_live_execution=False")
print("approved_for_real_live_trading=False")
print(f"decision={decision}")
