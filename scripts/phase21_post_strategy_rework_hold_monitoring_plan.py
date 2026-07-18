import json, os, subprocess, time
from pathlib import Path

OUT = Path("data/processed/phase21_post_strategy_rework_hold_monitoring_plan.json")
RUNTIME_OUT = Path("runtime/phase21_post_strategy_rework_hold_monitoring_plan_state.json")
PHASE21_DIR = Path("data/processed/phase21_hold_monitoring")

PHASE20_CLOSEOUT = Path("data/processed/phase20_strategy_rework_safety_closeout.json")
PHASE20_CLOSEOUT_RUNTIME = Path("runtime/phase20_strategy_rework_safety_closeout_state.json")
PHASE20_CLOSEOUT_FILE = Path("data/processed/phase20_strategy_rework/strategy_rework_safety_closeout.json")

PHASE20_HOLD = Path("data/processed/phase20_strategy_rework_hold_state_consolidation.json")
PHASE20_SELECTION = Path("data/processed/phase20_strategy_rework_next_action_selection.json")
PHASE20_OPTIONS = Path("data/processed/phase20_strategy_rework_next_action_options.json")
PHASE20_DRY_RUN_CLOSEOUT = Path("data/processed/phase20_offline_reworked_strategy_runner_dry_run_safety_closeout.json")

def run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True)

def git_clean():
    return run(["git", "status", "--short"]).stdout.strip() == ""

def git_head():
    r = run(["git", "rev-parse", "HEAD"])
    return r.stdout.strip() if r.returncode == 0 else None

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
current_git_head = git_head()
git_clean_before_outputs = git_clean()

closeout = load_json(PHASE20_CLOSEOUT)
closeout_runtime = load_json(PHASE20_CLOSEOUT_RUNTIME)
closeout_file_data = load_json(PHASE20_CLOSEOUT_FILE)
hold = load_json(PHASE20_HOLD)
selection = load_json(PHASE20_SELECTION)
options = load_json(PHASE20_OPTIONS)
dry_closeout = load_json(PHASE20_DRY_RUN_CLOSEOUT)

strategy_rework_safety_closeout_passed = (
    closeout.get("strategy_rework_safety_closeout_passed") is True
    or closeout_runtime.get("strategy_rework_safety_closeout_passed") is True
    or closeout_file_data.get("strategy_rework_safety_closeout_passed") is True
)

strategy_rework_hold_state_consolidated = hold.get("strategy_rework_hold_state_consolidated") is True
strategy_rework_next_action_selection_ready = selection.get("strategy_rework_next_action_selection_ready") is True
strategy_rework_next_action_options_ready = options.get("strategy_rework_next_action_options_ready") is True
dry_run_safety_closeout_passed = dry_closeout.get("dry_run_safety_closeout_passed") is True

phase20_status = closeout.get("phase20_status") or closeout_file_data.get("phase20_status")
selected_option = closeout.get("selected_option") or closeout_file_data.get("selected_option")
selected_phase20_next_action = closeout.get("selected_phase20_next_action") or closeout_file_data.get("selected_phase20_next_action")

monitoring_plan = {
    "plan_id": "phase21_post_strategy_rework_hold_monitoring_plan_v1",
    "mode": "hold_monitoring_plan_only",
    "start_monitoring_now": False,
    "run_health_check_now": False,
    "run_dry_run_now": False,
    "run_backtest_now": False,
    "execution_allowed": False,
    "paper_shadow_allowed": False,
    "live_trading_allowed": False,
    "exchange_order_submission": False,
    "monitoring_objectives": [
        "confirm_phase20_closed_remain_on_hold",
        "confirm_safe_mode_flags_remain_active",
        "confirm_no_dry_run_approval_exists",
        "confirm_no_backtest_execution_is_approved",
        "confirm_no_paper_shadow_start_is_approved",
        "confirm_no_micro_live_or_real_live_trading_is_approved",
        "confirm_no_exchange_order_submission_is_allowed"
    ],
    "planned_hold_monitoring_checks": [
        "check_safe_mode_flags",
        "check_phase20_closeout_exists",
        "check_phase20_status_closed_remain_on_hold",
        "check_selected_phase20_next_action_remain_on_hold",
        "check_dry_run_safety_closeout_passed",
        "check_execution_approval_flags_false",
        "check_exchange_order_submission_false",
        "check_real_live_trading_approval_false"
    ],
    "future_monitoring_outputs": [
        "data/processed/phase21_hold_monitoring/post_strategy_rework_hold_monitoring_health_check.json",
        "runtime/phase21_post_strategy_rework_hold_monitoring_health_check_state.json"
    ]
}

plan_checks = {
    "safe_mode_active": safe_mode,
    "phase20_closeout_present": PHASE20_CLOSEOUT.exists(),
    "phase20_closeout_runtime_present": PHASE20_CLOSEOUT_RUNTIME.exists(),
    "phase20_closeout_file_present": PHASE20_CLOSEOUT_FILE.exists(),
    "phase20_hold_present": PHASE20_HOLD.exists(),
    "phase20_selection_present": PHASE20_SELECTION.exists(),
    "phase20_options_present": PHASE20_OPTIONS.exists(),
    "phase20_dry_run_closeout_present": PHASE20_DRY_RUN_CLOSEOUT.exists(),
    "strategy_rework_safety_closeout_passed": strategy_rework_safety_closeout_passed,
    "strategy_rework_hold_state_consolidated": strategy_rework_hold_state_consolidated,
    "strategy_rework_next_action_selection_ready": strategy_rework_next_action_selection_ready,
    "strategy_rework_next_action_options_ready": strategy_rework_next_action_options_ready,
    "dry_run_safety_closeout_passed": dry_run_safety_closeout_passed,
    "phase20_status_closed_remain_on_hold": phase20_status == "closed_remain_on_hold",
    "selected_option_is_remain_on_hold": selected_option == "remain_on_hold",
    "selected_phase20_next_action_is_remain_on_hold": selected_phase20_next_action == "remain_on_hold",
    "start_monitoring_now_false": monitoring_plan["start_monitoring_now"] is False,
    "run_health_check_now_false": monitoring_plan["run_health_check_now"] is False,
    "run_dry_run_now_false": monitoring_plan["run_dry_run_now"] is False,
    "run_backtest_now_false": monitoring_plan["run_backtest_now"] is False,
    "execution_allowed_false": monitoring_plan["execution_allowed"] is False,
    "paper_shadow_allowed_false": monitoring_plan["paper_shadow_allowed"] is False,
    "live_trading_allowed_false": monitoring_plan["live_trading_allowed"] is False,
    "exchange_order_submission_false": monitoring_plan["exchange_order_submission"] is False,
    "approved_for_execution_false": closeout.get("approved_for_execution") is False,
    "approved_for_paper_shadow_false": closeout.get("approved_for_paper_shadow") is False,
    "approved_for_live_false": closeout.get("approved_for_live") is False,
    "paper_shadow_not_started": closeout.get("paper_shadow_started") is False,
    "paper_shadow_start_not_approved": closeout.get("approved_for_paper_shadow_start") is False,
    "micro_live_not_approved": closeout.get("approved_for_micro_live_execution") is False,
    "real_live_not_approved": closeout.get("approved_for_real_live_trading") is False,
}

blockers = [k for k, v in plan_checks.items() if v is not True]
post_strategy_rework_hold_monitoring_plan_ready = all(plan_checks.values())

if post_strategy_rework_hold_monitoring_plan_ready:
    decision = "PHASE_21_POST_STRATEGY_REWORK_HOLD_MONITORING_PLAN_CREATED_NOT_STARTED"
    next_phase = "Phase 21.2 — Post Strategy Rework Hold Monitoring Health Check"
else:
    decision = "PHASE_21_POST_STRATEGY_REWORK_HOLD_MONITORING_PLAN_BLOCKED_REVIEW_REQUIRED"
    next_phase = "Phase 21.2 — Hold Monitoring Plan Fix"

record = {
    "phase": "phase_21_1_post_strategy_rework_hold_monitoring_plan_record",
    "created_at_unix": int(time.time()),
    "git_head": current_git_head,
    "system_state": "HOLD_RESEARCH_ONLY",
    "phase20_status": phase20_status,
    "selected_option": selected_option,
    "selected_phase20_next_action": selected_phase20_next_action,
    "post_strategy_rework_hold_monitoring_plan_ready": post_strategy_rework_hold_monitoring_plan_ready,
    "monitoring_plan": monitoring_plan,
    "plan_checks": plan_checks,
    "blockers": blockers,
    "start_monitoring_now": False,
    "run_health_check_now": False,
    "run_dry_run_now": False,
    "run_backtest_now": False,
    "execution_allowed": False,
    "approved_for_execution": False,
    "approved_for_paper_shadow": False,
    "approved_for_live": False,
    "paper_shadow_started": False,
    "approved_for_paper_shadow_start": False,
    "exchange_order_submission": False,
    "approved_for_micro_live_execution": False,
    "approved_for_real_live_trading": False,
    "decision": decision,
    "next_phase": next_phase
}

record_file = PHASE21_DIR / "post_strategy_rework_hold_monitoring_plan.json"

write_json(record_file, record)
write_json(RUNTIME_OUT, record)

report = {
    "phase": "phase_21_1_post_strategy_rework_hold_monitoring_plan",
    "generated_at_unix": int(time.time()),
    "scope": "hold_monitoring_plan_only_no_monitoring_started_no_execution",
    "git_head": current_git_head,
    "safety_flags": flags,
    "safe_mode_active": safe_mode,
    "git_working_tree_clean": git_clean_before_outputs,
    "phase20_status": phase20_status,
    "selected_option": selected_option,
    "selected_phase20_next_action": selected_phase20_next_action,
    "post_strategy_rework_hold_monitoring_plan_ready": post_strategy_rework_hold_monitoring_plan_ready,
    "monitoring_objective_count": len(monitoring_plan["monitoring_objectives"]),
    "planned_hold_monitoring_check_count": len(monitoring_plan["planned_hold_monitoring_checks"]),
    "plan_checks": plan_checks,
    "blockers": blockers,
    "record_file": str(record_file),
    "runtime_record_file": str(RUNTIME_OUT),
    "start_monitoring_now": False,
    "run_health_check_now": False,
    "run_dry_run_now": False,
    "run_backtest_now": False,
    "execution_allowed": False,
    "approved_for_execution": False,
    "approved_for_paper_shadow": False,
    "approved_for_live": False,
    "paper_shadow_started": False,
    "approved_for_paper_shadow_start": False,
    "exchange_order_submission": False,
    "approved_for_micro_live_execution": False,
    "approved_for_real_live_trading": False,
    "decision": decision,
    "next_phase": next_phase,
    "safety_notes": [
        "This phase creates the Phase 21 hold-monitoring plan only.",
        "This phase does not start monitoring.",
        "This phase does not run a health check.",
        "This phase does not execute a dry run.",
        "This phase does not run a backtest.",
        "This phase does not start paper shadow execution.",
        "This phase does not approve micro-live execution.",
        "This phase does not approve real live trading.",
        "This phase does not submit exchange orders."
    ]
}

write_json(OUT, report)

print(f"Report written to: {OUT}")
print(f"Runtime record written to: {RUNTIME_OUT}")
print(f"Record file written to: {record_file}")
print(f"safe_mode_active={safe_mode}")
print(f"post_strategy_rework_hold_monitoring_plan_ready={post_strategy_rework_hold_monitoring_plan_ready}")
print(f"phase20_status={phase20_status}")
print(f"selected_phase20_next_action={selected_phase20_next_action}")
print("start_monitoring_now=False")
print("run_health_check_now=False")
print("run_dry_run_now=False")
print("run_backtest_now=False")
print("execution_allowed=False")
print("approved_for_execution=False")
print("approved_for_paper_shadow=False")
print("approved_for_live=False")
print("paper_shadow_started=False")
print("approved_for_paper_shadow_start=False")
print("exchange_order_submission=False")
print("approved_for_micro_live_execution=False")
print("approved_for_real_live_trading=False")
print(f"decision={decision}")
