import json, os, subprocess, time
from pathlib import Path

OUT = Path("data/processed/phase21_post_strategy_rework_hold_monitoring_health_check.json")
RUNTIME_OUT = Path("runtime/phase21_post_strategy_rework_hold_monitoring_health_check_state.json")
PHASE21_DIR = Path("data/processed/phase21_hold_monitoring")

PLAN = Path("data/processed/phase21_post_strategy_rework_hold_monitoring_plan.json")
PLAN_RUNTIME = Path("runtime/phase21_post_strategy_rework_hold_monitoring_plan_state.json")
PLAN_FILE = Path("data/processed/phase21_hold_monitoring/post_strategy_rework_hold_monitoring_plan.json")

PHASE20_CLOSEOUT = Path("data/processed/phase20_strategy_rework_safety_closeout.json")
PHASE20_CLOSEOUT_RUNTIME = Path("runtime/phase20_strategy_rework_safety_closeout_state.json")
PHASE20_CLOSEOUT_FILE = Path("data/processed/phase20_strategy_rework/strategy_rework_safety_closeout.json")

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

plan = load_json(PLAN)
plan_runtime = load_json(PLAN_RUNTIME)
plan_file = load_json(PLAN_FILE)
closeout = load_json(PHASE20_CLOSEOUT)
closeout_runtime = load_json(PHASE20_CLOSEOUT_RUNTIME)
closeout_file = load_json(PHASE20_CLOSEOUT_FILE)

plan_ready = (
    plan.get("post_strategy_rework_hold_monitoring_plan_ready") is True
    or plan_runtime.get("post_strategy_rework_hold_monitoring_plan_ready") is True
    or plan_file.get("post_strategy_rework_hold_monitoring_plan_ready") is True
)

phase20_closeout_passed = (
    closeout.get("strategy_rework_safety_closeout_passed") is True
    or closeout_runtime.get("strategy_rework_safety_closeout_passed") is True
    or closeout_file.get("strategy_rework_safety_closeout_passed") is True
)

phase20_status = (
    plan.get("phase20_status")
    or plan_runtime.get("phase20_status")
    or plan_file.get("phase20_status")
    or closeout.get("phase20_status")
    or closeout_file.get("phase20_status")
)

selected_option = (
    plan.get("selected_option")
    or plan_runtime.get("selected_option")
    or plan_file.get("selected_option")
    or closeout.get("selected_option")
    or closeout_file.get("selected_option")
)

selected_phase20_next_action = (
    plan.get("selected_phase20_next_action")
    or plan_runtime.get("selected_phase20_next_action")
    or plan_file.get("selected_phase20_next_action")
    or closeout.get("selected_phase20_next_action")
    or closeout_file.get("selected_phase20_next_action")
)

health_checks = {
    "safe_mode_active": safe_mode,
    "plan_present": PLAN.exists(),
    "plan_runtime_present": PLAN_RUNTIME.exists(),
    "plan_file_present": PLAN_FILE.exists(),
    "phase20_closeout_present": PHASE20_CLOSEOUT.exists(),
    "phase20_closeout_runtime_present": PHASE20_CLOSEOUT_RUNTIME.exists(),
    "phase20_closeout_file_present": PHASE20_CLOSEOUT_FILE.exists(),
    "post_strategy_rework_hold_monitoring_plan_ready": plan_ready,
    "phase20_closeout_passed": phase20_closeout_passed,
    "phase20_status_closed_remain_on_hold": phase20_status == "closed_remain_on_hold",
    "selected_option_is_remain_on_hold": selected_option == "remain_on_hold",
    "selected_phase20_next_action_is_remain_on_hold": selected_phase20_next_action == "remain_on_hold",
    "start_monitoring_now_false": plan.get("start_monitoring_now") is False,
    "run_dry_run_now_false": plan.get("run_dry_run_now") is False,
    "run_backtest_now_false": plan.get("run_backtest_now") is False,
    "execution_allowed_false": plan.get("execution_allowed") is False,
    "approved_for_execution_false": plan.get("approved_for_execution") is False,
    "approved_for_paper_shadow_false": plan.get("approved_for_paper_shadow") is False,
    "approved_for_live_false": plan.get("approved_for_live") is False,
    "paper_shadow_not_started": plan.get("paper_shadow_started") is False,
    "paper_shadow_start_not_approved": plan.get("approved_for_paper_shadow_start") is False,
    "exchange_order_submission_disabled": plan.get("exchange_order_submission") is False,
    "micro_live_not_approved": plan.get("approved_for_micro_live_execution") is False,
    "real_live_not_approved": plan.get("approved_for_real_live_trading") is False,
}

blockers = [k for k, v in health_checks.items() if v is not True]
hold_health_check_passed = all(health_checks.values())

if hold_health_check_passed:
    decision = "PHASE_21_POST_STRATEGY_REWORK_HOLD_MONITORING_HEALTH_CHECK_COMPLETE_HOLD_CONFIRMED_NOT_APPROVED_FOR_EXECUTION"
    next_phase = "Phase 21.3 — Post Strategy Rework Hold Monitoring Review"
else:
    decision = "PHASE_21_POST_STRATEGY_REWORK_HOLD_MONITORING_HEALTH_CHECK_FAILED_REVIEW_REQUIRED"
    next_phase = "Phase 21.3 — Hold Monitoring Health Check Fix"

health_record = {
    "phase": "phase_21_2_post_strategy_rework_hold_monitoring_health_check_record",
    "created_at_unix": int(time.time()),
    "git_head": current_git_head,
    "system_state": "HOLD_RESEARCH_ONLY",
    "phase20_status": phase20_status,
    "selected_option": selected_option,
    "selected_phase20_next_action": selected_phase20_next_action,
    "hold_health_check_passed": hold_health_check_passed,
    "health_checks": health_checks,
    "blockers": blockers,
    "monitoring_started": False,
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

health_file = PHASE21_DIR / "post_strategy_rework_hold_monitoring_health_check.json"

write_json(health_file, health_record)
write_json(RUNTIME_OUT, health_record)

report = {
    "phase": "phase_21_2_post_strategy_rework_hold_monitoring_health_check",
    "generated_at_unix": int(time.time()),
    "scope": "local_hold_health_check_only_no_execution",
    "git_head": current_git_head,
    "safety_flags": flags,
    "safe_mode_active": safe_mode,
    "git_working_tree_clean": git_clean_before_outputs,
    "phase20_status": phase20_status,
    "selected_option": selected_option,
    "selected_phase20_next_action": selected_phase20_next_action,
    "hold_health_check_passed": hold_health_check_passed,
    "health_checks": health_checks,
    "blockers": blockers,
    "health_file": str(health_file),
    "runtime_health_file": str(RUNTIME_OUT),
    "monitoring_started": False,
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
        "This phase performs a local hold-state health check only.",
        "This phase does not start trading monitoring jobs.",
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
print(f"Runtime health check written to: {RUNTIME_OUT}")
print(f"Health file written to: {health_file}")
print(f"safe_mode_active={safe_mode}")
print(f"hold_health_check_passed={hold_health_check_passed}")
print(f"phase20_status={phase20_status}")
print(f"selected_phase20_next_action={selected_phase20_next_action}")
print("monitoring_started=False")
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
