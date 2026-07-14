import json, os, subprocess, time
from pathlib import Path

OUT = Path("data/processed/phase18_hold_state_monitoring_plan.json")
RUNTIME_OUT = Path("runtime/phase18_hold_state_monitoring_plan_state.json")
PLAN_DIR = Path("data/processed/phase18_hold_monitoring")

NEXT_ACTION_INPUT = Path("data/processed/phase18_next_action_selection.json")
RUNTIME_NEXT_ACTION = Path("runtime/phase18_next_action_selection_state.json")
PHASE17_CLOSEOUT = Path("data/processed/phase17_safety_closeout_next_action_options.json")
PHASE17_HOLD_STATE = Path("runtime/phase17_paper_shadow_hold_state.json")

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

flags = {
    "BINANCE_TESTNET": os.getenv("BINANCE_TESTNET", ""),
    "BINANCE_USE_TESTNET": os.getenv("BINANCE_USE_TESTNET", ""),
    "BINANCE_ENABLE_LIVE_TRADING": os.getenv("BINANCE_ENABLE_LIVE_TRADING", ""),
    "LIVE_TRADING_ALLOWED": os.getenv("LIVE_TRADING_ALLOWED", ""),
}

safe_mode = flags["BINANCE_ENABLE_LIVE_TRADING"] == "false" and flags["LIVE_TRADING_ALLOWED"] == "false"

next_action = load_json(NEXT_ACTION_INPUT)
runtime_next_action = load_json(RUNTIME_NEXT_ACTION)
phase17_closeout = load_json(PHASE17_CLOSEOUT)
phase17_hold = load_json(PHASE17_HOLD_STATE)

selected_option = next_action.get("selected_option") or runtime_next_action.get("selected_option")

paper_shadow_started = (
    next_action.get("paper_shadow_started") is True
    or runtime_next_action.get("paper_shadow_started") is True
    or phase17_closeout.get("paper_shadow_started") is True
    or phase17_hold.get("paper_shadow_started") is True
)

approved_for_paper_shadow_start = (
    next_action.get("approved_for_paper_shadow_start") is True
    or runtime_next_action.get("approved_for_paper_shadow_start") is True
    or phase17_closeout.get("approved_for_paper_shadow_start") is True
    or phase17_hold.get("approved_for_paper_shadow_start") is True
)

exchange_order_submission = (
    next_action.get("exchange_order_submission") is True
    or runtime_next_action.get("exchange_order_submission") is True
    or phase17_closeout.get("exchange_order_submission") is True
    or phase17_hold.get("exchange_order_submission") is True
)

approved_for_micro_live_execution = (
    next_action.get("approved_for_micro_live_execution") is True
    or runtime_next_action.get("approved_for_micro_live_execution") is True
    or phase17_closeout.get("approved_for_micro_live_execution") is True
    or phase17_hold.get("approved_for_micro_live_execution") is True
)

approved_for_real_live_trading = (
    next_action.get("approved_for_real_live_trading") is True
    or runtime_next_action.get("approved_for_real_live_trading") is True
    or phase17_closeout.get("approved_for_real_live_trading") is True
    or phase17_hold.get("approved_for_real_live_trading") is True
)

monitoring_checks = {
    "safe_mode_active": safe_mode,
    "next_action_input_present": NEXT_ACTION_INPUT.exists(),
    "runtime_next_action_present": RUNTIME_NEXT_ACTION.exists(),
    "phase17_closeout_present": PHASE17_CLOSEOUT.exists(),
    "phase17_hold_state_present": PHASE17_HOLD_STATE.exists(),
    "selected_option_is_remain_on_hold": selected_option == "remain_on_hold",
    "paper_shadow_not_started": paper_shadow_started is False,
    "paper_shadow_start_not_approved": approved_for_paper_shadow_start is False,
    "exchange_order_submission_disabled": exchange_order_submission is False,
    "micro_live_not_approved": approved_for_micro_live_execution is False,
    "real_live_not_approved": approved_for_real_live_trading is False,
}

blockers = [k for k, v in monitoring_checks.items() if v is not True]
monitoring_plan_ready = all(monitoring_checks.values())

PLAN_DIR.mkdir(parents=True, exist_ok=True)

hold_monitoring_plan = {
    "phase": "phase_18_2_hold_state_monitoring_plan_record",
    "created_at_unix": int(time.time()),
    "selected_option": selected_option,
    "monitoring_mode": "hold_state_only",
    "trading_execution_allowed": False,
    "paper_shadow_execution_allowed": False,
    "exchange_order_submission_allowed": False,
    "real_capital_allowed": False,
    "recommended_checks": [
        "confirm_safe_trading_flags_daily",
        "confirm_no_exchange_order_submission",
        "confirm_no_paper_shadow_started",
        "confirm_no_micro_live_approval",
        "confirm_no_real_live_trading_approval",
        "review_monitoring_dashboard_health",
        "review_git_status_clean",
        "review_runtime_hold_state"
    ],
    "recommended_frequency": {
        "safe_flag_check": "daily",
        "runtime_state_check": "daily",
        "dashboard_health_review": "weekly",
        "phase18_next_action_review": "manual_only"
    },
    "monitoring_checks": monitoring_checks,
    "blockers": blockers,
    "monitoring_plan_ready": monitoring_plan_ready,
    "paper_shadow_started": False,
    "approved_for_paper_shadow_start": False,
    "exchange_order_submission": False,
    "approved_for_micro_live_execution": False,
    "approved_for_real_live_trading": False
}

plan_file = PLAN_DIR / "hold_state_monitoring_plan.json"
write_json(plan_file, hold_monitoring_plan)
write_json(RUNTIME_OUT, hold_monitoring_plan)

if monitoring_plan_ready:
    decision = "PHASE_18_HOLD_STATE_MONITORING_PLAN_CREATED_READY_NOT_APPROVED_FOR_EXECUTION"
    next_phase = "Phase 18.3 — Hold State Monitoring Health Check"
else:
    decision = "PHASE_18_HOLD_STATE_MONITORING_PLAN_BLOCKED_REVIEW_REQUIRED"
    next_phase = "Phase 18.3 — Hold State Monitoring Review"

report = {
    "phase": "phase_18_2_hold_state_monitoring_plan",
    "generated_at_unix": int(time.time()),
    "scope": "hold_state_monitoring_plan_only",
    "selected_option": selected_option,
    "safety_flags": flags,
    "safe_mode_active": safe_mode,
    "git_working_tree_clean": git_clean(),
    "monitoring_checks": monitoring_checks,
    "blockers": blockers,
    "monitoring_plan_ready": monitoring_plan_ready,
    "paper_shadow_started": False,
    "approved_for_paper_shadow_start": False,
    "exchange_order_submission": False,
    "real_capital_allowed": False,
    "live_trading_enabled": False,
    "approved_for_micro_live_execution": False,
    "approved_for_real_live_trading": False,
    "plan_file": str(plan_file),
    "runtime_monitoring_plan_file": str(RUNTIME_OUT),
    "decision": decision,
    "next_phase": next_phase,
    "safety_notes": [
        "This phase creates a hold-state monitoring plan only.",
        "This phase does not start paper shadow execution.",
        "This phase does not approve micro-live execution.",
        "This phase does not approve real live trading.",
        "This phase does not submit Binance orders.",
        "Real capital and exchange order submission remain disabled."
    ]
}

write_json(OUT, report)

print(f"Report written to: {OUT}")
print(f"Runtime monitoring plan written to: {RUNTIME_OUT}")
print(f"Plan written to: {plan_file}")
print(f"safe_mode_active={safe_mode}")
print(f"selected_option={selected_option}")
print(f"monitoring_plan_ready={monitoring_plan_ready}")
print("paper_shadow_started=False")
print("approved_for_paper_shadow_start=False")
print("exchange_order_submission=False")
print("approved_for_micro_live_execution=False")
print("approved_for_real_live_trading=False")
print(f"decision={decision}")
