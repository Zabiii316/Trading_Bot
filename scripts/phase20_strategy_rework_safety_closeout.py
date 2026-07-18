import json, os, subprocess, time
from pathlib import Path

OUT = Path("data/processed/phase20_strategy_rework_safety_closeout.json")
RUNTIME_OUT = Path("runtime/phase20_strategy_rework_safety_closeout_state.json")
PHASE20_DIR = Path("data/processed/phase20_strategy_rework")

HOLD = Path("data/processed/phase20_strategy_rework_hold_state_consolidation.json")
HOLD_RUNTIME = Path("runtime/phase20_strategy_rework_hold_state_consolidation_state.json")
HOLD_FILE = Path("data/processed/phase20_strategy_rework/strategy_rework_hold_state_consolidation.json")

SELECTION = Path("data/processed/phase20_strategy_rework_next_action_selection.json")
OPTIONS = Path("data/processed/phase20_strategy_rework_next_action_options.json")
DRY_RUN_CLOSEOUT = Path("data/processed/phase20_offline_reworked_strategy_runner_dry_run_safety_closeout.json")
RUNNER_DESIGN = Path("data/processed/phase20_offline_reworked_strategy_runner_design.json")
QUALITY_GATE = Path("data/processed/phase20_strategy_quality_gate_v2_design.json")
CANDIDATE_RULES = Path("data/processed/phase20_candidate_rejection_rules_design.json")
BACKTEST_SPEC = Path("data/processed/phase20_offline_reworked_strategy_backtest_spec.json")
EXPERIMENT_DESIGN = Path("data/processed/phase20_strategy_rework_experiment_design.json")
HYPOTHESIS_PLAN = Path("data/processed/phase20_strategy_rework_hypothesis_plan.json")
FAILURE_REVIEW = Path("data/processed/phase20_strategy_failure_review.json")
READINESS = Path("data/processed/phase20_strategy_rework_readiness_review.json")

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

hold = load_json(HOLD)
hold_runtime = load_json(HOLD_RUNTIME)
hold_file_data = load_json(HOLD_FILE)
selection = load_json(SELECTION)
options = load_json(OPTIONS)
dry_closeout = load_json(DRY_RUN_CLOSEOUT)
runner = load_json(RUNNER_DESIGN)
quality = load_json(QUALITY_GATE)
rules = load_json(CANDIDATE_RULES)
spec = load_json(BACKTEST_SPEC)
experiment = load_json(EXPERIMENT_DESIGN)
hypothesis = load_json(HYPOTHESIS_PLAN)
failure = load_json(FAILURE_REVIEW)
readiness = load_json(READINESS)

strategy_rework_hold_state_consolidated = (
    hold.get("strategy_rework_hold_state_consolidated") is True
    or hold_runtime.get("strategy_rework_hold_state_consolidated") is True
    or hold_file_data.get("strategy_rework_hold_state_consolidated") is True
)

strategy_rework_next_action_selection_ready = selection.get("strategy_rework_next_action_selection_ready") is True
strategy_rework_next_action_options_ready = options.get("strategy_rework_next_action_options_ready") is True
dry_run_safety_closeout_passed = dry_closeout.get("dry_run_safety_closeout_passed") is True
offline_runner_design_ready = runner.get("offline_runner_design_ready") is True
strategy_quality_gate_v2_ready = quality.get("strategy_quality_gate_v2_ready") is True
candidate_rejection_rules_ready = rules.get("candidate_rejection_rules_ready") is True
offline_backtest_spec_ready = spec.get("offline_backtest_spec_ready") is True
experiment_design_ready = experiment.get("strategy_rework_experiment_design_ready") is True
hypothesis_plan_ready = hypothesis.get("strategy_rework_hypothesis_plan_ready") is True
strategy_failure_review_ready = failure.get("strategy_failure_review_ready") is True
research_only_ready = readiness.get("research_only_strategy_rework_ready") is True

selected_option = (
    hold.get("selected_option")
    or hold_runtime.get("selected_option")
    or hold_file_data.get("selected_option")
)

selected_phase19_path = (
    hold.get("selected_phase19_path")
    or hold_runtime.get("selected_phase19_path")
    or hold_file_data.get("selected_phase19_path")
)

selected_phase20_next_action = (
    hold.get("selected_phase20_next_action")
    or hold_runtime.get("selected_phase20_next_action")
    or hold_file_data.get("selected_phase20_next_action")
)

manual_dry_run_approval_granted = False
dry_run_allowed = False
run_dry_run_now = False
run_backtest_now = False
execution_allowed = False

closeout_checks = {
    "safe_mode_active": safe_mode,
    "hold_consolidation_present": HOLD.exists(),
    "hold_runtime_present": HOLD_RUNTIME.exists(),
    "hold_file_present": HOLD_FILE.exists(),
    "selection_present": SELECTION.exists(),
    "options_present": OPTIONS.exists(),
    "dry_run_closeout_present": DRY_RUN_CLOSEOUT.exists(),
    "runner_design_present": RUNNER_DESIGN.exists(),
    "quality_gate_present": QUALITY_GATE.exists(),
    "candidate_rules_present": CANDIDATE_RULES.exists(),
    "backtest_spec_present": BACKTEST_SPEC.exists(),
    "experiment_design_present": EXPERIMENT_DESIGN.exists(),
    "hypothesis_plan_present": HYPOTHESIS_PLAN.exists(),
    "failure_review_present": FAILURE_REVIEW.exists(),
    "readiness_present": READINESS.exists(),
    "strategy_rework_hold_state_consolidated": strategy_rework_hold_state_consolidated,
    "strategy_rework_next_action_selection_ready": strategy_rework_next_action_selection_ready,
    "strategy_rework_next_action_options_ready": strategy_rework_next_action_options_ready,
    "dry_run_safety_closeout_passed": dry_run_safety_closeout_passed,
    "offline_runner_design_ready": offline_runner_design_ready,
    "strategy_quality_gate_v2_ready": strategy_quality_gate_v2_ready,
    "candidate_rejection_rules_ready": candidate_rejection_rules_ready,
    "offline_backtest_spec_ready": offline_backtest_spec_ready,
    "experiment_design_ready": experiment_design_ready,
    "hypothesis_plan_ready": hypothesis_plan_ready,
    "strategy_failure_review_ready": strategy_failure_review_ready,
    "research_only_ready": research_only_ready,
    "selected_option_is_remain_on_hold": selected_option == "remain_on_hold",
    "selected_phase20_next_action_is_remain_on_hold": selected_phase20_next_action == "remain_on_hold",
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
strategy_rework_safety_closeout_passed = all(closeout_checks.values())

if strategy_rework_safety_closeout_passed:
    decision = "PHASE_20_STRATEGY_REWORK_SAFETY_CLOSEOUT_COMPLETE_REMAIN_ON_HOLD_NOT_APPROVED_FOR_EXECUTION"
    next_phase = "Phase 21.1 — Post Strategy Rework Hold Monitoring Plan"
else:
    decision = "PHASE_20_STRATEGY_REWORK_SAFETY_CLOSEOUT_FAILED_REVIEW_REQUIRED"
    next_phase = "Phase 20.20 — Strategy Rework Safety Closeout Fix"

closeout_record = {
    "phase": "phase_20_19_strategy_rework_safety_closeout_record",
    "created_at_unix": int(time.time()),
    "git_head": current_git_head,
    "system_state": "HOLD_RESEARCH_ONLY",
    "phase20_status": "closed_remain_on_hold",
    "selected_option": selected_option,
    "selected_phase19_path": selected_phase19_path,
    "selected_phase20_next_action": selected_phase20_next_action,
    "strategy_rework_safety_closeout_passed": strategy_rework_safety_closeout_passed,
    "manual_dry_run_approval_granted": False,
    "dry_run_allowed": False,
    "run_dry_run_now": False,
    "run_backtest_now": False,
    "execution_allowed": False,
    "closeout_checks": closeout_checks,
    "blockers": blockers,
    "final_phase20_state": {
        "phase20_status": "closed_remain_on_hold",
        "system_state": "HOLD_RESEARCH_ONLY",
        "selected_phase20_next_action": "remain_on_hold",
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
        "post_strategy_rework_hold_monitoring_plan",
        "manual_approval_review_only",
        "documentation_only",
        "historical_data_expansion_review_only"
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

closeout_file = PHASE20_DIR / "strategy_rework_safety_closeout.json"

write_json(closeout_file, closeout_record)
write_json(RUNTIME_OUT, closeout_record)

report = {
    "phase": "phase_20_19_strategy_rework_safety_closeout",
    "generated_at_unix": int(time.time()),
    "scope": "phase20_safety_closeout_only_no_dry_run_no_backtest_no_execution",
    "git_head": current_git_head,
    "safety_flags": flags,
    "safe_mode_active": safe_mode,
    "git_working_tree_clean": git_clean_before_outputs,
    "strategy_rework_safety_closeout_passed": strategy_rework_safety_closeout_passed,
    "phase20_status": "closed_remain_on_hold",
    "selected_option": selected_option,
    "selected_phase19_path": selected_phase19_path,
    "selected_phase20_next_action": selected_phase20_next_action,
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
        "This phase safely closes Phase 20 strategy rework.",
        "Selected Phase 20 next action remains remain_on_hold.",
        "Manual dry-run approval remains false.",
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
print(f"strategy_rework_safety_closeout_passed={strategy_rework_safety_closeout_passed}")
print("phase20_status=closed_remain_on_hold")
print(f"selected_phase20_next_action={selected_phase20_next_action}")
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
