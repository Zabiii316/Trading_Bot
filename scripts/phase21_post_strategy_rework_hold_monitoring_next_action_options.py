import json, os, subprocess, time
from pathlib import Path

OUT = Path("data/processed/phase21_post_strategy_rework_hold_monitoring_next_action_options.json")
RUNTIME_OUT = Path("runtime/phase21_post_strategy_rework_hold_monitoring_next_action_options_state.json")
PHASE21_DIR = Path("data/processed/phase21_hold_monitoring")

CLOSEOUT = Path("data/processed/phase21_post_strategy_rework_hold_monitoring_safety_closeout.json")
CLOSEOUT_RUNTIME = Path("runtime/phase21_post_strategy_rework_hold_monitoring_safety_closeout_state.json")
CLOSEOUT_FILE = Path("data/processed/phase21_hold_monitoring/post_strategy_rework_hold_monitoring_safety_closeout.json")

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

closeout = load_json(CLOSEOUT)
closeout_runtime = load_json(CLOSEOUT_RUNTIME)
closeout_file = load_json(CLOSEOUT_FILE)
consolidation = load_json(CONSOLIDATION)
review = load_json(REVIEW)
health = load_json(HEALTH)
plan = load_json(PLAN)
phase20 = load_json(PHASE20_CLOSEOUT)

hold_monitoring_safety_closeout_passed = (
    closeout.get("hold_monitoring_safety_closeout_passed") is True
    or closeout_runtime.get("hold_monitoring_safety_closeout_passed") is True
    or closeout_file.get("hold_monitoring_safety_closeout_passed") is True
)

hold_monitoring_consolidated = consolidation.get("hold_monitoring_consolidated") is True
hold_monitoring_review_passed = review.get("hold_monitoring_review_passed") is True
hold_health_check_passed = health.get("hold_health_check_passed") is True
plan_ready = plan.get("post_strategy_rework_hold_monitoring_plan_ready") is True
phase20_closeout_passed = phase20.get("strategy_rework_safety_closeout_passed") is True

phase20_status = (
    closeout.get("phase20_status")
    or closeout_runtime.get("phase20_status")
    or closeout_file.get("phase20_status")
    or phase20.get("phase20_status")
)

phase21_status = (
    closeout.get("phase21_status")
    or closeout_runtime.get("phase21_status")
    or closeout_file.get("phase21_status")
)

selected_option = (
    closeout.get("selected_option")
    or closeout_runtime.get("selected_option")
    or closeout_file.get("selected_option")
)

selected_phase20_next_action = (
    closeout.get("selected_phase20_next_action")
    or closeout_runtime.get("selected_phase20_next_action")
    or closeout_file.get("selected_phase20_next_action")
)

selected_phase21_next_action = "remain_on_hold"

monitoring_started = False
run_dry_run_now = False
run_backtest_now = False
execution_allowed = False

next_action_options = [
    {
        "option_id": "remain_on_hold",
        "description": "Keep Phase 21 in hold state because no monitoring, dry run, backtest, paper shadow, or live execution approval exists.",
        "recommended": True,
        "monitoring_allowed": False,
        "dry_run_allowed": False,
        "backtest_allowed": False,
        "execution_allowed": False
    },
    {
        "option_id": "documentation_only",
        "description": "Continue documentation-only review of Phase 20 and Phase 21 hold-state evidence.",
        "recommended": True,
        "monitoring_allowed": False,
        "dry_run_allowed": False,
        "backtest_allowed": False,
        "execution_allowed": False
    },
    {
        "option_id": "manual_approval_review_only",
        "description": "Review manual approval requirements without granting approval or starting any execution.",
        "recommended": True,
        "monitoring_allowed": False,
        "dry_run_allowed": False,
        "backtest_allowed": False,
        "execution_allowed": False
    },
    {
        "option_id": "future_hold_health_check_plan_only",
        "description": "Create a future hold-health-check plan only, with execution flags disabled.",
        "recommended": False,
        "monitoring_allowed": False,
        "dry_run_allowed": False,
        "backtest_allowed": False,
        "execution_allowed": False
    }
]

option_checks = {
    "safe_mode_active": safe_mode,
    "closeout_present": CLOSEOUT.exists(),
    "closeout_runtime_present": CLOSEOUT_RUNTIME.exists(),
    "closeout_file_present": CLOSEOUT_FILE.exists(),
    "consolidation_present": CONSOLIDATION.exists(),
    "review_present": REVIEW.exists(),
    "health_present": HEALTH.exists(),
    "plan_present": PLAN.exists(),
    "phase20_closeout_present": PHASE20_CLOSEOUT.exists(),
    "hold_monitoring_safety_closeout_passed": hold_monitoring_safety_closeout_passed,
    "hold_monitoring_consolidated": hold_monitoring_consolidated,
    "hold_monitoring_review_passed": hold_monitoring_review_passed,
    "hold_health_check_passed": hold_health_check_passed,
    "post_strategy_rework_hold_monitoring_plan_ready": plan_ready,
    "phase20_closeout_passed": phase20_closeout_passed,
    "phase20_status_closed_remain_on_hold": phase20_status == "closed_remain_on_hold",
    "phase21_status_closed_not_started": phase21_status == "hold_monitoring_closed_not_started",
    "selected_option_is_remain_on_hold": selected_option == "remain_on_hold",
    "selected_phase20_next_action_is_remain_on_hold": selected_phase20_next_action == "remain_on_hold",
    "selected_phase21_next_action_is_remain_on_hold": selected_phase21_next_action == "remain_on_hold",
    "next_action_options_created": len(next_action_options) >= 4,
    "monitoring_not_started": monitoring_started is False,
    "run_dry_run_now_false": run_dry_run_now is False,
    "run_backtest_now_false": run_backtest_now is False,
    "execution_allowed_false": execution_allowed is False,
    "approved_for_execution_false": closeout.get("approved_for_execution") is False,
    "approved_for_paper_shadow_false": closeout.get("approved_for_paper_shadow") is False,
    "approved_for_live_false": closeout.get("approved_for_live") is False,
    "paper_shadow_not_started": closeout.get("paper_shadow_started") is False,
    "paper_shadow_start_not_approved": closeout.get("approved_for_paper_shadow_start") is False,
    "exchange_order_submission_disabled": closeout.get("exchange_order_submission") is False,
    "micro_live_not_approved": closeout.get("approved_for_micro_live_execution") is False,
    "real_live_not_approved": closeout.get("approved_for_real_live_trading") is False,
}

blockers = [k for k, v in option_checks.items() if v is not True]
hold_monitoring_next_action_options_ready = all(option_checks.values())

if hold_monitoring_next_action_options_ready:
    decision = "PHASE_21_POST_STRATEGY_REWORK_HOLD_MONITORING_NEXT_ACTION_OPTIONS_CREATED_REMAIN_ON_HOLD_NOT_APPROVED_FOR_EXECUTION"
    next_phase = "Phase 21.7 — Post Strategy Rework Hold Monitoring Next Action Selection"
else:
    decision = "PHASE_21_POST_STRATEGY_REWORK_HOLD_MONITORING_NEXT_ACTION_OPTIONS_BLOCKED_REVIEW_REQUIRED"
    next_phase = "Phase 21.7 — Hold Monitoring Next Action Options Fix"

options_record = {
    "phase": "phase_21_6_post_strategy_rework_hold_monitoring_next_action_options_record",
    "created_at_unix": int(time.time()),
    "git_head": current_git_head,
    "system_state": "HOLD_RESEARCH_ONLY",
    "phase20_status": phase20_status,
    "phase21_status": phase21_status,
    "selected_option": selected_option,
    "selected_phase20_next_action": selected_phase20_next_action,
    "selected_phase21_next_action": selected_phase21_next_action,
    "hold_monitoring_next_action_options_ready": hold_monitoring_next_action_options_ready,
    "next_action_options": next_action_options,
    "option_checks": option_checks,
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

options_file = PHASE21_DIR / "post_strategy_rework_hold_monitoring_next_action_options.json"

write_json(options_file, options_record)
write_json(RUNTIME_OUT, options_record)

report = {
    "phase": "phase_21_6_post_strategy_rework_hold_monitoring_next_action_options",
    "generated_at_unix": int(time.time()),
    "scope": "next_action_options_only_no_monitoring_started_no_execution",
    "git_head": current_git_head,
    "safety_flags": flags,
    "safe_mode_active": safe_mode,
    "git_working_tree_clean": git_clean_before_outputs,
    "phase20_status": phase20_status,
    "phase21_status": phase21_status,
    "selected_option": selected_option,
    "selected_phase20_next_action": selected_phase20_next_action,
    "selected_phase21_next_action": selected_phase21_next_action,
    "hold_monitoring_next_action_options_ready": hold_monitoring_next_action_options_ready,
    "next_action_option_count": len(next_action_options),
    "option_checks": option_checks,
    "blockers": blockers,
    "options_file": str(options_file),
    "runtime_options_file": str(RUNTIME_OUT),
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
        "This phase creates Phase 21 next-action options only.",
        "Selected Phase 21 next action remains remain_on_hold.",
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
print(f"Runtime options written to: {RUNTIME_OUT}")
print(f"Options file written to: {options_file}")
print(f"safe_mode_active={safe_mode}")
print(f"hold_monitoring_next_action_options_ready={hold_monitoring_next_action_options_ready}")
print(f"phase20_status={phase20_status}")
print(f"phase21_status={phase21_status}")
print(f"selected_phase21_next_action={selected_phase21_next_action}")
print(f"next_action_option_count={len(next_action_options)}")
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
