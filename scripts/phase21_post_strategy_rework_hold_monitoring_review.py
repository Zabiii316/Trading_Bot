import json, os, subprocess, time
from pathlib import Path

OUT = Path("data/processed/phase21_post_strategy_rework_hold_monitoring_review.json")
RUNTIME_OUT = Path("runtime/phase21_post_strategy_rework_hold_monitoring_review_state.json")
PHASE21_DIR = Path("data/processed/phase21_hold_monitoring")

HEALTH = Path("data/processed/phase21_post_strategy_rework_hold_monitoring_health_check.json")
HEALTH_RUNTIME = Path("runtime/phase21_post_strategy_rework_hold_monitoring_health_check_state.json")
HEALTH_FILE = Path("data/processed/phase21_hold_monitoring/post_strategy_rework_hold_monitoring_health_check.json")

PLAN = Path("data/processed/phase21_post_strategy_rework_hold_monitoring_plan.json")
PLAN_FILE = Path("data/processed/phase21_hold_monitoring/post_strategy_rework_hold_monitoring_plan.json")

PHASE20_CLOSEOUT = Path("data/processed/phase20_strategy_rework_safety_closeout.json")
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

health = load_json(HEALTH)
health_runtime = load_json(HEALTH_RUNTIME)
health_file = load_json(HEALTH_FILE)
plan = load_json(PLAN)
plan_file = load_json(PLAN_FILE)
phase20 = load_json(PHASE20_CLOSEOUT)
phase20_file = load_json(PHASE20_CLOSEOUT_FILE)

hold_health_check_passed = (
    health.get("hold_health_check_passed") is True
    or health_runtime.get("hold_health_check_passed") is True
    or health_file.get("hold_health_check_passed") is True
)

plan_ready = (
    plan.get("post_strategy_rework_hold_monitoring_plan_ready") is True
    or plan_file.get("post_strategy_rework_hold_monitoring_plan_ready") is True
)

phase20_closeout_passed = (
    phase20.get("strategy_rework_safety_closeout_passed") is True
    or phase20_file.get("strategy_rework_safety_closeout_passed") is True
)

phase20_status = (
    health.get("phase20_status")
    or health_runtime.get("phase20_status")
    or health_file.get("phase20_status")
    or phase20.get("phase20_status")
    or phase20_file.get("phase20_status")
)

selected_option = (
    health.get("selected_option")
    or health_runtime.get("selected_option")
    or health_file.get("selected_option")
    or plan.get("selected_option")
    or phase20.get("selected_option")
)

selected_phase20_next_action = (
    health.get("selected_phase20_next_action")
    or health_runtime.get("selected_phase20_next_action")
    or health_file.get("selected_phase20_next_action")
    or plan.get("selected_phase20_next_action")
    or phase20.get("selected_phase20_next_action")
)

monitoring_started = False
run_dry_run_now = False
run_backtest_now = False
execution_allowed = False

review_checks = {
    "safe_mode_active": safe_mode,
    "health_report_present": HEALTH.exists(),
    "health_runtime_present": HEALTH_RUNTIME.exists(),
    "health_file_present": HEALTH_FILE.exists(),
    "plan_present": PLAN.exists(),
    "plan_file_present": PLAN_FILE.exists(),
    "phase20_closeout_present": PHASE20_CLOSEOUT.exists(),
    "phase20_closeout_file_present": PHASE20_CLOSEOUT_FILE.exists(),
    "hold_health_check_passed": hold_health_check_passed,
    "post_strategy_rework_hold_monitoring_plan_ready": plan_ready,
    "phase20_closeout_passed": phase20_closeout_passed,
    "phase20_status_closed_remain_on_hold": phase20_status == "closed_remain_on_hold",
    "selected_option_is_remain_on_hold": selected_option == "remain_on_hold",
    "selected_phase20_next_action_is_remain_on_hold": selected_phase20_next_action == "remain_on_hold",
    "monitoring_not_started": monitoring_started is False,
    "run_dry_run_now_false": run_dry_run_now is False,
    "run_backtest_now_false": run_backtest_now is False,
    "execution_allowed_false": execution_allowed is False,
    "approved_for_execution_false": health.get("approved_for_execution") is False,
    "approved_for_paper_shadow_false": health.get("approved_for_paper_shadow") is False,
    "approved_for_live_false": health.get("approved_for_live") is False,
    "paper_shadow_not_started": health.get("paper_shadow_started") is False,
    "paper_shadow_start_not_approved": health.get("approved_for_paper_shadow_start") is False,
    "exchange_order_submission_disabled": health.get("exchange_order_submission") is False,
    "micro_live_not_approved": health.get("approved_for_micro_live_execution") is False,
    "real_live_not_approved": health.get("approved_for_real_live_trading") is False,
}

blockers = [k for k, v in review_checks.items() if v is not True]
hold_monitoring_review_passed = all(review_checks.values())

if hold_monitoring_review_passed:
    decision = "PHASE_21_POST_STRATEGY_REWORK_HOLD_MONITORING_REVIEW_COMPLETE_HOLD_CONFIRMED_NOT_APPROVED_FOR_EXECUTION"
    next_phase = "Phase 21.4 — Post Strategy Rework Hold Monitoring Consolidation"
else:
    decision = "PHASE_21_POST_STRATEGY_REWORK_HOLD_MONITORING_REVIEW_FAILED_REVIEW_REQUIRED"
    next_phase = "Phase 21.4 — Hold Monitoring Review Fix"

review_record = {
    "phase": "phase_21_3_post_strategy_rework_hold_monitoring_review_record",
    "created_at_unix": int(time.time()),
    "git_head": current_git_head,
    "system_state": "HOLD_RESEARCH_ONLY",
    "phase20_status": phase20_status,
    "selected_option": selected_option,
    "selected_phase20_next_action": selected_phase20_next_action,
    "hold_monitoring_review_passed": hold_monitoring_review_passed,
    "review_checks": review_checks,
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

review_file = PHASE21_DIR / "post_strategy_rework_hold_monitoring_review.json"

write_json(review_file, review_record)
write_json(RUNTIME_OUT, review_record)

report = {
    "phase": "phase_21_3_post_strategy_rework_hold_monitoring_review",
    "generated_at_unix": int(time.time()),
    "scope": "hold_monitoring_review_only_no_monitoring_started_no_execution",
    "git_head": current_git_head,
    "safety_flags": flags,
    "safe_mode_active": safe_mode,
    "git_working_tree_clean": git_clean_before_outputs,
    "phase20_status": phase20_status,
    "selected_option": selected_option,
    "selected_phase20_next_action": selected_phase20_next_action,
    "hold_monitoring_review_passed": hold_monitoring_review_passed,
    "review_checks": review_checks,
    "blockers": blockers,
    "review_file": str(review_file),
    "runtime_review_file": str(RUNTIME_OUT),
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
        "This phase reviews the hold-monitoring health check only.",
        "This phase does not start monitoring jobs.",
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
print(f"Runtime review written to: {RUNTIME_OUT}")
print(f"Review file written to: {review_file}")
print(f"safe_mode_active={safe_mode}")
print(f"hold_monitoring_review_passed={hold_monitoring_review_passed}")
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
