import json, os, subprocess, time
from pathlib import Path

OUT = Path("data/processed/phase21_post_strategy_rework_hold_monitoring_final_hold_state_consolidation.json")
RUNTIME_OUT = Path("runtime/phase21_post_strategy_rework_hold_monitoring_final_hold_state_consolidation_state.json")
PHASE21_DIR = Path("data/processed/phase21_hold_monitoring")

SELECTION = Path("data/processed/phase21_post_strategy_rework_hold_monitoring_next_action_selection.json")
SELECTION_RUNTIME = Path("runtime/phase21_post_strategy_rework_hold_monitoring_next_action_selection_state.json")
SELECTION_FILE = Path("data/processed/phase21_hold_monitoring/post_strategy_rework_hold_monitoring_next_action_selection.json")

OPTIONS = Path("data/processed/phase21_post_strategy_rework_hold_monitoring_next_action_options.json")
CLOSEOUT = Path("data/processed/phase21_post_strategy_rework_hold_monitoring_safety_closeout.json")
CONSOLIDATION = Path("data/processed/phase21_post_strategy_rework_hold_monitoring_consolidation.json")
REVIEW = Path("data/processed/phase21_post_strategy_rework_hold_monitoring_review.json")
HEALTH = Path("data/processed/phase21_post_strategy_rework_hold_monitoring_health_check.json")
PLAN = Path("data/processed/phase21_post_strategy_rework_hold_monitoring_plan.json")
PHASE20_CLOSEOUT = Path("data/processed/phase20_strategy_rework_safety_closeout.json")

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

selection = load_json(SELECTION)
selection_runtime = load_json(SELECTION_RUNTIME)
selection_file = load_json(SELECTION_FILE)
options = load_json(OPTIONS)
closeout = load_json(CLOSEOUT)
consolidation = load_json(CONSOLIDATION)
review = load_json(REVIEW)
health = load_json(HEALTH)
plan = load_json(PLAN)
phase20 = load_json(PHASE20_CLOSEOUT)

selection_ready = (
    selection.get("hold_monitoring_next_action_selection_ready") is True
    or selection_runtime.get("hold_monitoring_next_action_selection_ready") is True
    or selection_file.get("hold_monitoring_next_action_selection_ready") is True
)

options_ready = options.get("hold_monitoring_next_action_options_ready") is True
safety_closeout_passed = closeout.get("hold_monitoring_safety_closeout_passed") is True
hold_monitoring_consolidated = consolidation.get("hold_monitoring_consolidated") is True
review_passed = review.get("hold_monitoring_review_passed") is True
health_passed = health.get("hold_health_check_passed") is True
plan_ready = plan.get("post_strategy_rework_hold_monitoring_plan_ready") is True
phase20_closeout_passed = phase20.get("strategy_rework_safety_closeout_passed") is True

phase20_status = (
    selection.get("phase20_status")
    or selection_runtime.get("phase20_status")
    or selection_file.get("phase20_status")
    or closeout.get("phase20_status")
    or phase20.get("phase20_status")
)

phase21_status = (
    selection.get("phase21_status")
    or selection_runtime.get("phase21_status")
    or selection_file.get("phase21_status")
    or closeout.get("phase21_status")
)

selected_option = (
    selection.get("selected_option")
    or selection_runtime.get("selected_option")
    or selection_file.get("selected_option")
)

selected_phase20_next_action = (
    selection.get("selected_phase20_next_action")
    or selection_runtime.get("selected_phase20_next_action")
    or selection_file.get("selected_phase20_next_action")
)

selected_phase21_next_action = (
    selection.get("selected_phase21_next_action")
    or selection_runtime.get("selected_phase21_next_action")
    or selection_file.get("selected_phase21_next_action")
)

monitoring_started = False
run_dry_run_now = False
run_backtest_now = False
execution_allowed = False

final_consolidation_checks = {
    "safe_mode_active": safe_mode,
    "selection_present": SELECTION.exists(),
    "selection_runtime_present": SELECTION_RUNTIME.exists(),
    "selection_file_present": SELECTION_FILE.exists(),
    "options_present": OPTIONS.exists(),
    "closeout_present": CLOSEOUT.exists(),
    "consolidation_present": CONSOLIDATION.exists(),
    "review_present": REVIEW.exists(),
    "health_present": HEALTH.exists(),
    "plan_present": PLAN.exists(),
    "phase20_closeout_present": PHASE20_CLOSEOUT.exists(),
    "hold_monitoring_next_action_selection_ready": selection_ready,
    "hold_monitoring_next_action_options_ready": options_ready,
    "hold_monitoring_safety_closeout_passed": safety_closeout_passed,
    "hold_monitoring_consolidated": hold_monitoring_consolidated,
    "hold_monitoring_review_passed": review_passed,
    "hold_health_check_passed": health_passed,
    "post_strategy_rework_hold_monitoring_plan_ready": plan_ready,
    "phase20_closeout_passed": phase20_closeout_passed,
    "phase20_status_closed_remain_on_hold": phase20_status == "closed_remain_on_hold",
    "phase21_status_closed_not_started": phase21_status == "hold_monitoring_closed_not_started",
    "selected_option_is_remain_on_hold": selected_option == "remain_on_hold",
    "selected_phase20_next_action_is_remain_on_hold": selected_phase20_next_action == "remain_on_hold",
    "selected_phase21_next_action_is_remain_on_hold": selected_phase21_next_action == "remain_on_hold",
    "monitoring_not_started": monitoring_started is False,
    "run_dry_run_now_false": run_dry_run_now is False,
    "run_backtest_now_false": run_backtest_now is False,
    "execution_allowed_false": execution_allowed is False,
    "approved_for_execution_false": selection.get("approved_for_execution") is False,
    "approved_for_paper_shadow_false": selection.get("approved_for_paper_shadow") is False,
    "approved_for_live_false": selection.get("approved_for_live") is False,
    "paper_shadow_not_started": selection.get("paper_shadow_started") is False,
    "paper_shadow_start_not_approved": selection.get("approved_for_paper_shadow_start") is False,
    "exchange_order_submission_disabled": selection.get("exchange_order_submission") is False,
    "micro_live_not_approved": selection.get("approved_for_micro_live_execution") is False,
    "real_live_not_approved": selection.get("approved_for_real_live_trading") is False,
}

blockers = [k for k, v in final_consolidation_checks.items() if v is not True]
final_hold_state_consolidated = all(final_consolidation_checks.values())

if final_hold_state_consolidated:
    decision = "PHASE_21_POST_STRATEGY_REWORK_HOLD_MONITORING_FINAL_HOLD_STATE_CONSOLIDATED_REMAIN_ON_HOLD_NOT_APPROVED_FOR_EXECUTION"
    next_phase = "Phase 21.9 — Post Strategy Rework Hold Monitoring Final Safety Closeout"
else:
    decision = "PHASE_21_POST_STRATEGY_REWORK_HOLD_MONITORING_FINAL_HOLD_STATE_CONSOLIDATION_FAILED_REVIEW_REQUIRED"
    next_phase = "Phase 21.9 — Final Hold State Consolidation Fix"

final_record = {
    "phase": "phase_21_8_post_strategy_rework_hold_monitoring_final_hold_state_consolidation_record",
    "created_at_unix": int(time.time()),
    "git_head": current_git_head,
    "system_state": "HOLD_RESEARCH_ONLY",
    "phase20_status": phase20_status,
    "phase21_status": "final_hold_state_consolidated_remain_on_hold",
    "selected_option": selected_option,
    "selected_phase20_next_action": selected_phase20_next_action,
    "selected_phase21_next_action": selected_phase21_next_action,
    "final_hold_state_consolidated": final_hold_state_consolidated,
    "final_consolidation_checks": final_consolidation_checks,
    "blockers": blockers,
    "final_hold_state": {
        "system_state": "HOLD_RESEARCH_ONLY",
        "phase20_status": phase20_status,
        "phase21_status": "final_hold_state_consolidated_remain_on_hold",
        "selected_phase20_next_action": selected_phase20_next_action,
        "selected_phase21_next_action": selected_phase21_next_action,
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
    "allowed_actions": [
        "final_safety_closeout",
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

final_file = PHASE21_DIR / "post_strategy_rework_hold_monitoring_final_hold_state_consolidation.json"

write_json(final_file, final_record)
write_json(RUNTIME_OUT, final_record)

report = {
    "phase": "phase_21_8_post_strategy_rework_hold_monitoring_final_hold_state_consolidation",
    "generated_at_unix": int(time.time()),
    "scope": "final_hold_state_consolidation_only_no_monitoring_started_no_execution",
    "git_head": current_git_head,
    "safety_flags": flags,
    "safe_mode_active": safe_mode,
    "git_working_tree_clean": git_clean_before_outputs,
    "phase20_status": phase20_status,
    "phase21_status": "final_hold_state_consolidated_remain_on_hold",
    "selected_option": selected_option,
    "selected_phase20_next_action": selected_phase20_next_action,
    "selected_phase21_next_action": selected_phase21_next_action,
    "final_hold_state_consolidated": final_hold_state_consolidated,
    "final_consolidation_checks": final_consolidation_checks,
    "blockers": blockers,
    "final_file": str(final_file),
    "runtime_final_file": str(RUNTIME_OUT),
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
        "This phase consolidates the final Phase 21 hold state only.",
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
print(f"Runtime final consolidation written to: {RUNTIME_OUT}")
print(f"Final consolidation file written to: {final_file}")
print(f"safe_mode_active={safe_mode}")
print(f"final_hold_state_consolidated={final_hold_state_consolidated}")
print(f"phase20_status={phase20_status}")
print("phase21_status=final_hold_state_consolidated_remain_on_hold")
print(f"selected_phase21_next_action={selected_phase21_next_action}")
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
