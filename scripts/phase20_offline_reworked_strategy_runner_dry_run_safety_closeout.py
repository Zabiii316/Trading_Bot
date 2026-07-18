import json, os, subprocess, time
from pathlib import Path

OUT = Path("data/processed/phase20_offline_reworked_strategy_runner_dry_run_safety_closeout.json")
RUNTIME_OUT = Path("runtime/phase20_offline_reworked_strategy_runner_dry_run_safety_closeout_state.json")
PHASE20_DIR = Path("data/processed/phase20_strategy_rework")

HOLD_CONSOLIDATION = Path("data/processed/phase20_offline_reworked_strategy_runner_dry_run_hold_state_consolidation.json")
HOLD_CONSOLIDATION_RUNTIME = Path("runtime/phase20_offline_reworked_strategy_runner_dry_run_hold_state_consolidation_state.json")
BLOCKED_REVIEW = Path("data/processed/phase20_offline_reworked_strategy_runner_dry_run_blocked_start_review.json")
START_GATE = Path("data/processed/phase20_offline_reworked_strategy_runner_dry_run_start_gate.json")
MANUAL_RECORD = Path("data/processed/phase20_offline_reworked_strategy_runner_dry_run_manual_approval_record.json")
APPROVAL_GATE = Path("data/processed/phase20_offline_reworked_strategy_runner_dry_run_approval_gate.json")
DRY_RUN_PLAN = Path("data/processed/phase20_offline_reworked_strategy_runner_dry_run_plan.json")
RUNNER_DESIGN = Path("data/processed/phase20_offline_reworked_strategy_runner_design.json")
CANDIDATE_RULES = Path("data/processed/phase20_candidate_rejection_rules_design.json")
QUALITY_GATE = Path("data/processed/phase20_strategy_quality_gate_v2_design.json")
BACKTEST_SPEC = Path("data/processed/phase20_offline_reworked_strategy_backtest_spec.json")

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

hold = load_json(HOLD_CONSOLIDATION)
hold_runtime = load_json(HOLD_CONSOLIDATION_RUNTIME)
blocked = load_json(BLOCKED_REVIEW)
start_gate = load_json(START_GATE)
manual = load_json(MANUAL_RECORD)
approval_gate = load_json(APPROVAL_GATE)
plan = load_json(DRY_RUN_PLAN)
runner = load_json(RUNNER_DESIGN)
rules = load_json(CANDIDATE_RULES)
quality = load_json(QUALITY_GATE)
spec = load_json(BACKTEST_SPEC)

dry_run_hold_state_consolidated = (
    hold.get("dry_run_hold_state_consolidated") is True
    or hold_runtime.get("dry_run_hold_state_consolidated") is True
)

blocked_start_review_passed = blocked.get("blocked_start_review_passed") is True
dry_run_start_gate_ready = start_gate.get("dry_run_start_gate_ready") is True
manual_approval_record_ready = manual.get("manual_approval_record_ready") is True
dry_run_approval_gate_ready = approval_gate.get("dry_run_approval_gate_ready") is True
offline_runner_dry_run_plan_ready = plan.get("offline_runner_dry_run_plan_ready") is True
offline_runner_design_ready = runner.get("offline_runner_design_ready") is True
candidate_rejection_rules_ready = rules.get("candidate_rejection_rules_ready") is True
strategy_quality_gate_v2_ready = quality.get("strategy_quality_gate_v2_ready") is True
offline_backtest_spec_ready = spec.get("offline_backtest_spec_ready") is True

selected_option = (
    hold.get("selected_option")
    or hold_runtime.get("selected_option")
    or blocked.get("selected_option")
    or start_gate.get("selected_option")
    or manual.get("selected_option")
)

selected_phase19_path = (
    hold.get("selected_phase19_path")
    or hold_runtime.get("selected_phase19_path")
    or blocked.get("selected_phase19_path")
    or start_gate.get("selected_phase19_path")
    or manual.get("selected_phase19_path")
)

selected_next_action = (
    hold.get("selected_next_action")
    or hold_runtime.get("selected_next_action")
    or blocked.get("selected_next_action")
    or start_gate.get("selected_next_action")
    or manual.get("selected_next_action")
)

manual_dry_run_approval_granted = False
dry_run_allowed = False
run_dry_run_now = False
run_backtest_now = False
execution_allowed = False

closeout_checks = {
    "safe_mode_active": safe_mode,
    "hold_consolidation_present": HOLD_CONSOLIDATION.exists(),
    "hold_consolidation_runtime_present": HOLD_CONSOLIDATION_RUNTIME.exists(),
    "blocked_review_present": BLOCKED_REVIEW.exists(),
    "start_gate_present": START_GATE.exists(),
    "manual_record_present": MANUAL_RECORD.exists(),
    "approval_gate_present": APPROVAL_GATE.exists(),
    "dry_run_plan_present": DRY_RUN_PLAN.exists(),
    "runner_design_present": RUNNER_DESIGN.exists(),
    "candidate_rules_present": CANDIDATE_RULES.exists(),
    "quality_gate_present": QUALITY_GATE.exists(),
    "backtest_spec_present": BACKTEST_SPEC.exists(),
    "dry_run_hold_state_consolidated": dry_run_hold_state_consolidated,
    "blocked_start_review_passed": blocked_start_review_passed,
    "dry_run_start_gate_ready": dry_run_start_gate_ready,
    "manual_approval_record_ready": manual_approval_record_ready,
    "dry_run_approval_gate_ready": dry_run_approval_gate_ready,
    "offline_runner_dry_run_plan_ready": offline_runner_dry_run_plan_ready,
    "offline_runner_design_ready": offline_runner_design_ready,
    "candidate_rejection_rules_ready": candidate_rejection_rules_ready,
    "strategy_quality_gate_v2_ready": strategy_quality_gate_v2_ready,
    "offline_backtest_spec_ready": offline_backtest_spec_ready,
    "selected_option_is_remain_on_hold": selected_option == "remain_on_hold",
    "selected_next_action_is_remain_on_hold": selected_next_action == "remain_on_hold",
    "manual_dry_run_approval_not_granted": manual_dry_run_approval_granted is False,
    "dry_run_blocked": dry_run_allowed is False,
    "run_dry_run_now_false": run_dry_run_now is False,
    "run_backtest_now_false": run_backtest_now is False,
    "execution_allowed_false": execution_allowed is False,
    "approved_for_execution_false": hold.get("approved_for_execution") is False,
    "approved_for_paper_shadow_false": hold.get("approved_for_paper_shadow") is False,
    "approved_for_live_false": hold.get("approved_for_live") is False,
    "paper_shadow_not_started": hold.get("paper_shadow_started") is False,
    "paper_shadow_start_not_approved": hold.get("approved_for_paper_shadow_start") is False,
    "exchange_order_submission_disabled": hold.get("exchange_order_submission") is False,
    "micro_live_not_approved": hold.get("approved_for_micro_live_execution") is False,
    "real_live_not_approved": hold.get("approved_for_real_live_trading") is False,
}

blockers = [k for k, v in closeout_checks.items() if v is not True]
dry_run_safety_closeout_passed = all(closeout_checks.values())

if dry_run_safety_closeout_passed:
    decision = "PHASE_20_OFFLINE_REWORKED_STRATEGY_RUNNER_DRY_RUN_SAFETY_CLOSEOUT_COMPLETE_DRY_RUN_NOT_APPROVED"
    next_phase = "Phase 20.16 — Strategy Rework Next Action Options"
else:
    decision = "PHASE_20_OFFLINE_REWORKED_STRATEGY_RUNNER_DRY_RUN_SAFETY_CLOSEOUT_FAILED_REVIEW_REQUIRED"
    next_phase = "Phase 20.16 — Offline Runner Dry Run Safety Closeout Fix"

closeout_record = {
    "phase": "phase_20_15_offline_reworked_strategy_runner_dry_run_safety_closeout_record",
    "created_at_unix": int(time.time()),
    "git_head": current_git_head,
    "system_state": "HOLD_RESEARCH_ONLY",
    "selected_option": selected_option,
    "selected_phase19_path": selected_phase19_path,
    "selected_next_action": selected_next_action,
    "dry_run_safety_closeout_passed": dry_run_safety_closeout_passed,
    "manual_dry_run_approval_granted": False,
    "dry_run_allowed": False,
    "run_dry_run_now": False,
    "run_backtest_now": False,
    "execution_allowed": False,
    "blocked_reason": "manual_dry_run_approval_required",
    "closeout_checks": closeout_checks,
    "blockers": blockers,
    "final_dry_run_state": {
        "dry_run_state": "closed_blocked_manual_approval_required",
        "manual_dry_run_approval_granted": False,
        "dry_run_allowed": False,
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
        "strategy_rework_next_action_options",
        "manual_approval_review_only",
        "documentation_only",
        "hold_state_monitoring"
    ],
    "blocked_actions": [
        "offline_runner_dry_run_execution",
        "backtest_execution",
        "paper_shadow_start",
        "micro_live_execution",
        "real_live_trading",
        "exchange_order_submission",
        "real_capital_usage",
        "production_api_key_usage"
    ],
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

closeout_file = PHASE20_DIR / "offline_reworked_strategy_runner_dry_run_safety_closeout.json"

write_json(closeout_file, closeout_record)
write_json(RUNTIME_OUT, closeout_record)

report = {
    "phase": "phase_20_15_offline_reworked_strategy_runner_dry_run_safety_closeout",
    "generated_at_unix": int(time.time()),
    "scope": "dry_run_safety_closeout_only_no_dry_run_no_backtest_no_execution",
    "git_head": current_git_head,
    "safety_flags": flags,
    "safe_mode_active": safe_mode,
    "git_working_tree_clean": git_clean_before_outputs,
    "dry_run_safety_closeout_passed": dry_run_safety_closeout_passed,
    "selected_option": selected_option,
    "selected_phase19_path": selected_phase19_path,
    "selected_next_action": selected_next_action,
    "closeout_checks": closeout_checks,
    "blockers": blockers,
    "closeout_file": str(closeout_file),
    "runtime_closeout_file": str(RUNTIME_OUT),
    "manual_dry_run_approval_granted": False,
    "dry_run_allowed": False,
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
        "This phase safely closes the offline runner dry-run branch.",
        "Dry run remains blocked because manual dry-run approval has not been granted.",
        "This phase does not execute the dry run.",
        "This phase does not run a backtest.",
        "This phase does not start paper shadow execution.",
        "This phase does not approve micro-live execution.",
        "This phase does not approve real live trading.",
        "This phase does not submit Binance orders."
    ]
}

write_json(OUT, report)

print(f"Report written to: {OUT}")
print(f"Runtime closeout written to: {RUNTIME_OUT}")
print(f"Closeout file written to: {closeout_file}")
print(f"safe_mode_active={safe_mode}")
print(f"dry_run_safety_closeout_passed={dry_run_safety_closeout_passed}")
print("manual_dry_run_approval_granted=False")
print("dry_run_allowed=False")
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
