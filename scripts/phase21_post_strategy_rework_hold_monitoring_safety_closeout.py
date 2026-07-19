import json, os, subprocess, time
from pathlib import Path

OUT = Path("data/processed/phase21_post_strategy_rework_hold_monitoring_safety_closeout.json")
RUNTIME_OUT = Path("runtime/phase21_post_strategy_rework_hold_monitoring_safety_closeout_state.json")
PHASE21_DIR = Path("data/processed/phase21_hold_monitoring")

CONSOLIDATION = Path("data/processed/phase21_post_strategy_rework_hold_monitoring_consolidation.json")
CONSOLIDATION_RUNTIME = Path("runtime/phase21_post_strategy_rework_hold_monitoring_consolidation_state.json")
CONSOLIDATION_FILE = Path("data/processed/phase21_hold_monitoring/post_strategy_rework_hold_monitoring_consolidation.json")

REVIEW = Path("data/processed/phase21_post_strategy_rework_hold_monitoring_review.json")
REVIEW_FILE = Path("data/processed/phase21_hold_monitoring/post_strategy_rework_hold_monitoring_review.json")

HEALTH = Path("data/processed/phase21_post_strategy_rework_hold_monitoring_health_check.json")
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

consolidation = load_json(CONSOLIDATION)
consolidation_runtime = load_json(CONSOLIDATION_RUNTIME)
consolidation_file = load_json(CONSOLIDATION_FILE)
review = load_json(REVIEW)
review_file = load_json(REVIEW_FILE)
health = load_json(HEALTH)
health_file = load_json(HEALTH_FILE)
plan = load_json(PLAN)
plan_file = load_json(PLAN_FILE)
phase20 = load_json(PHASE20_CLOSEOUT)
phase20_file = load_json(PHASE20_CLOSEOUT_FILE)

hold_monitoring_consolidated = (
    consolidation.get("hold_monitoring_consolidated") is True
    or consolidation_runtime.get("hold_monitoring_consolidated") is True
    or consolidation_file.get("hold_monitoring_consolidated") is True
)

hold_monitoring_review_passed = (
    review.get("hold_monitoring_review_passed") is True
    or review_file.get("hold_monitoring_review_passed") is True
)

hold_health_check_passed = (
    health.get("hold_health_check_passed") is True
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
    consolidation.get("phase20_status")
    or consolidation_runtime.get("phase20_status")
    or consolidation_file.get("phase20_status")
    or review.get("phase20_status")
    or health.get("phase20_status")
    or plan.get("phase20_status")
    or phase20.get("phase20_status")
)

selected_option = (
    consolidation.get("selected_option")
    or consolidation_runtime.get("selected_option")
    or consolidation_file.get("selected_option")
    or review.get("selected_option")
    or health.get("selected_option")
    or plan.get("selected_option")
    or phase20.get("selected_option")
)

selected_phase20_next_action = (
    consolidation.get("selected_phase20_next_action")
    or consolidation_runtime.get("selected_phase20_next_action")
    or consolidation_file.get("selected_phase20_next_action")
    or review.get("selected_phase20_next_action")
    or health.get("selected_phase20_next_action")
    or plan.get("selected_phase20_next_action")
    or phase20.get("selected_phase20_next_action")
)

monitoring_started = False
run_dry_run_now = False
run_backtest_now = False
execution_allowed = False

closeout_checks = {
    "safe_mode_active": safe_mode,
    "consolidation_present": CONSOLIDATION.exists(),
    "consolidation_runtime_present": CONSOLIDATION_RUNTIME.exists(),
    "consolidation_file_present": CONSOLIDATION_FILE.exists(),
    "review_present": REVIEW.exists(),
    "review_file_present": REVIEW_FILE.exists(),
    "health_present": HEALTH.exists(),
    "health_file_present": HEALTH_FILE.exists(),
    "plan_present": PLAN.exists(),
    "plan_file_present": PLAN_FILE.exists(),
    "phase20_closeout_present": PHASE20_CLOSEOUT.exists(),
    "phase20_closeout_file_present": PHASE20_CLOSEOUT_FILE.exists(),
    "hold_monitoring_consolidated": hold_monitoring_consolidated,
    "hold_monitoring_review_passed": hold_monitoring_review_passed,
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
    "approved_for_execution_false": consolidation.get("approved_for_execution") is False,
    "approved_for_paper_shadow_false": consolidation.get("approved_for_paper_shadow") is False,
    "approved_for_live_false": consolidation.get("approved_for_live") is False,
    "paper_shadow_not_started": consolidation.get("paper_shadow_started") is False,
    "paper_shadow_start_not_approved": consolidation.get("approved_for_paper_shadow_start") is False,
    "exchange_order_submission_disabled": consolidation.get("exchange_order_submission") is False,
    "micro_live_not_approved": consolidation.get("approved_for_micro_live_execution") is False,
    "real_live_not_approved": consolidation.get("approved_for_real_live_trading") is False,
}

blockers = [k for k, v in closeout_checks.items() if v is not True]
hold_monitoring_safety_closeout_passed = all(closeout_checks.values())

if hold_monitoring_safety_closeout_passed:
    decision = "PHASE_21_POST_STRATEGY_REWORK_HOLD_MONITORING_SAFETY_CLOSEOUT_COMPLETE_HOLD_CONFIRMED_NOT_APPROVED_FOR_EXECUTION"
    next_phase = "Phase 21.6 — Post Strategy Rework Hold Monitoring Next Action Options"
else:
    decision = "PHASE_21_POST_STRATEGY_REWORK_HOLD_MONITORING_SAFETY_CLOSEOUT_FAILED_REVIEW_REQUIRED"
    next_phase = "Phase 21.6 — Hold Monitoring Safety Closeout Fix"

closeout_record = {
    "phase": "phase_21_5_post_strategy_rework_hold_monitoring_safety_closeout_record",
    "created_at_unix": int(time.time()),
    "git_head": current_git_head,
    "system_state": "HOLD_RESEARCH_ONLY",
    "phase20_status": phase20_status,
    "phase21_status": "hold_monitoring_closed_not_started",
    "selected_option": selected_option,
    "selected_phase20_next_action": selected_phase20_next_action,
    "hold_monitoring_safety_closeout_passed": hold_monitoring_safety_closeout_passed,
    "closeout_checks": closeout_checks,
    "blockers": blockers,
    "final_hold_monitoring_state": {
        "phase21_status": "hold_monitoring_closed_not_started",
        "monitoring_state": "closed_hold_confirmed_not_started",
        "phase20_status": phase20_status,
        "selected_phase20_next_action": selected_phase20_next_action,
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
        "approved_for_real_live_trading": False
    },
    "allowed_next_actions": [
        "post_strategy_rework_hold_monitoring_next_action_options",
        "documentation_only",
        "manual_approval_review_only"
    ],
    "blocked_actions": [
        "monitoring_job_execution",
        "offline_runner_dry_run_execution",
        "backtest_execution",
        "paper_shadow_start",
        "micro_live_execution",
        "real_live_trading",
        "exchange_order_submission",
        "real_capital_usage",
        "production_api_key_usage"
    ],
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

closeout_file = PHASE21_DIR / "post_strategy_rework_hold_monitoring_safety_closeout.json"

write_json(closeout_file, closeout_record)
write_json(RUNTIME_OUT, closeout_record)

report = {
    "phase": "phase_21_5_post_strategy_rework_hold_monitoring_safety_closeout",
    "generated_at_unix": int(time.time()),
    "scope": "hold_monitoring_safety_closeout_only_no_monitoring_started_no_execution",
    "git_head": current_git_head,
    "safety_flags": flags,
    "safe_mode_active": safe_mode,
    "git_working_tree_clean": git_clean_before_outputs,
    "phase20_status": phase20_status,
    "phase21_status": "hold_monitoring_closed_not_started",
    "selected_option": selected_option,
    "selected_phase20_next_action": selected_phase20_next_action,
    "hold_monitoring_safety_closeout_passed": hold_monitoring_safety_closeout_passed,
    "closeout_checks": closeout_checks,
    "blockers": blockers,
    "closeout_file": str(closeout_file),
    "runtime_closeout_file": str(RUNTIME_OUT),
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
        "This phase safely closes the Phase 21 hold-monitoring branch.",
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
print(f"Runtime closeout written to: {RUNTIME_OUT}")
print(f"Closeout file written to: {closeout_file}")
print(f"safe_mode_active={safe_mode}")
print(f"hold_monitoring_safety_closeout_passed={hold_monitoring_safety_closeout_passed}")
print(f"phase20_status={phase20_status}")
print("phase21_status=hold_monitoring_closed_not_started")
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
