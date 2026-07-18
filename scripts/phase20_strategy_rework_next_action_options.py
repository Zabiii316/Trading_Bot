import json, os, subprocess, time
from pathlib import Path

OUT = Path("data/processed/phase20_strategy_rework_next_action_options.json")
RUNTIME_OUT = Path("runtime/phase20_strategy_rework_next_action_options_state.json")
PHASE20_DIR = Path("data/processed/phase20_strategy_rework")

DRY_RUN_CLOSEOUT = Path("data/processed/phase20_offline_reworked_strategy_runner_dry_run_safety_closeout.json")
DRY_RUN_CLOSEOUT_RUNTIME = Path("runtime/phase20_offline_reworked_strategy_runner_dry_run_safety_closeout_state.json")
DRY_RUN_CLOSEOUT_FILE = Path("data/processed/phase20_strategy_rework/offline_reworked_strategy_runner_dry_run_safety_closeout.json")

HOLD_CONSOLIDATION = Path("data/processed/phase20_offline_reworked_strategy_runner_dry_run_hold_state_consolidation.json")
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

closeout = load_json(DRY_RUN_CLOSEOUT)
closeout_runtime = load_json(DRY_RUN_CLOSEOUT_RUNTIME)
closeout_file_data = load_json(DRY_RUN_CLOSEOUT_FILE)
hold = load_json(HOLD_CONSOLIDATION)
blocked = load_json(BLOCKED_REVIEW)
start_gate = load_json(START_GATE)
manual = load_json(MANUAL_RECORD)
approval_gate = load_json(APPROVAL_GATE)
plan = load_json(DRY_RUN_PLAN)
runner = load_json(RUNNER_DESIGN)
rules = load_json(CANDIDATE_RULES)
quality = load_json(QUALITY_GATE)
spec = load_json(BACKTEST_SPEC)

dry_run_safety_closeout_passed = (
    closeout.get("dry_run_safety_closeout_passed") is True
    or closeout_runtime.get("dry_run_safety_closeout_passed") is True
    or closeout_file_data.get("dry_run_safety_closeout_passed") is True
)

dry_run_hold_state_consolidated = hold.get("dry_run_hold_state_consolidated") is True
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
    closeout.get("selected_option")
    or closeout_runtime.get("selected_option")
    or closeout_file_data.get("selected_option")
    or hold.get("selected_option")
    or manual.get("selected_option")
)

selected_phase19_path = (
    closeout.get("selected_phase19_path")
    or closeout_runtime.get("selected_phase19_path")
    or closeout_file_data.get("selected_phase19_path")
    or hold.get("selected_phase19_path")
    or manual.get("selected_phase19_path")
)

previous_selected_next_action = (
    closeout.get("selected_next_action")
    or closeout_runtime.get("selected_next_action")
    or closeout_file_data.get("selected_next_action")
    or hold.get("selected_next_action")
    or manual.get("selected_next_action")
)

selected_phase20_next_action = "remain_on_hold"

manual_dry_run_approval_granted = False
dry_run_allowed = False
run_dry_run_now = False
run_backtest_now = False
execution_allowed = False

next_action_options = [
    {
        "option_id": "remain_on_hold",
        "description": "Keep Phase 20 strategy rework in research-only hold state because dry-run approval has not been granted.",
        "recommended": True,
        "dry_run_allowed": False,
        "backtest_allowed": False,
        "execution_allowed": False
    },
    {
        "option_id": "manual_dry_run_approval_review",
        "description": "Review the manual approval template before any future dry-run approval decision.",
        "recommended": True,
        "dry_run_allowed": False,
        "backtest_allowed": False,
        "execution_allowed": False
    },
    {
        "option_id": "runner_code_skeleton_design_only",
        "description": "Create a non-executing offline runner code skeleton in a future phase, with run flags disabled by default.",
        "recommended": False,
        "dry_run_allowed": False,
        "backtest_allowed": False,
        "execution_allowed": False
    },
    {
        "option_id": "continue_documentation_only",
        "description": "Continue documenting Phase 20 strategy rework assumptions, gates, and blocked actions.",
        "recommended": True,
        "dry_run_allowed": False,
        "backtest_allowed": False,
        "execution_allowed": False
    }
]

option_checks = {
    "safe_mode_active": safe_mode,
    "dry_run_closeout_present": DRY_RUN_CLOSEOUT.exists(),
    "dry_run_closeout_runtime_present": DRY_RUN_CLOSEOUT_RUNTIME.exists(),
    "dry_run_closeout_file_present": DRY_RUN_CLOSEOUT_FILE.exists(),
    "hold_consolidation_present": HOLD_CONSOLIDATION.exists(),
    "blocked_review_present": BLOCKED_REVIEW.exists(),
    "start_gate_present": START_GATE.exists(),
    "manual_record_present": MANUAL_RECORD.exists(),
    "approval_gate_present": APPROVAL_GATE.exists(),
    "dry_run_plan_present": DRY_RUN_PLAN.exists(),
    "runner_design_present": RUNNER_DESIGN.exists(),
    "candidate_rules_present": CANDIDATE_RULES.exists(),
    "quality_gate_present": QUALITY_GATE.exists(),
    "backtest_spec_present": BACKTEST_SPEC.exists(),
    "dry_run_safety_closeout_passed": dry_run_safety_closeout_passed,
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
    "previous_selected_next_action_is_remain_on_hold": previous_selected_next_action == "remain_on_hold",
    "selected_phase20_next_action_is_remain_on_hold": selected_phase20_next_action == "remain_on_hold",
    "manual_dry_run_approval_not_granted": manual_dry_run_approval_granted is False,
    "dry_run_blocked": dry_run_allowed is False,
    "run_dry_run_now_false": run_dry_run_now is False,
    "run_backtest_now_false": run_backtest_now is False,
    "execution_allowed_false": execution_allowed is False,
    "next_action_options_created": len(next_action_options) >= 4,
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
strategy_rework_next_action_options_ready = all(option_checks.values())

if strategy_rework_next_action_options_ready:
    decision = "PHASE_20_STRATEGY_REWORK_NEXT_ACTION_OPTIONS_CREATED_REMAIN_ON_HOLD_NOT_APPROVED_FOR_EXECUTION"
    next_phase = "Phase 20.17 — Strategy Rework Next Action Selection"
else:
    decision = "PHASE_20_STRATEGY_REWORK_NEXT_ACTION_OPTIONS_BLOCKED_REVIEW_REQUIRED"
    next_phase = "Phase 20.17 — Strategy Rework Next Action Options Fix"

options_record = {
    "phase": "phase_20_16_strategy_rework_next_action_options_record",
    "created_at_unix": int(time.time()),
    "git_head": current_git_head,
    "system_state": "HOLD_RESEARCH_ONLY",
    "selected_option": selected_option,
    "selected_phase19_path": selected_phase19_path,
    "previous_selected_next_action": previous_selected_next_action,
    "selected_phase20_next_action": selected_phase20_next_action,
    "strategy_rework_next_action_options_ready": strategy_rework_next_action_options_ready,
    "manual_dry_run_approval_granted": False,
    "dry_run_allowed": False,
    "run_dry_run_now": False,
    "run_backtest_now": False,
    "execution_allowed": False,
    "option_checks": option_checks,
    "blockers": blockers,
    "next_action_options": next_action_options,
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

options_file = PHASE20_DIR / "strategy_rework_next_action_options.json"

write_json(options_file, options_record)
write_json(RUNTIME_OUT, options_record)

report = {
    "phase": "phase_20_16_strategy_rework_next_action_options",
    "generated_at_unix": int(time.time()),
    "scope": "next_action_options_only_no_dry_run_no_backtest_no_execution",
    "git_head": current_git_head,
    "safety_flags": flags,
    "safe_mode_active": safe_mode,
    "git_working_tree_clean": git_clean_before_outputs,
    "strategy_rework_next_action_options_ready": strategy_rework_next_action_options_ready,
    "selected_option": selected_option,
    "selected_phase19_path": selected_phase19_path,
    "previous_selected_next_action": previous_selected_next_action,
    "selected_phase20_next_action": selected_phase20_next_action,
    "next_action_option_count": len(next_action_options),
    "option_checks": option_checks,
    "blockers": blockers,
    "options_file": str(options_file),
    "runtime_options_file": str(RUNTIME_OUT),
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
        "This phase creates next-action options only.",
        "Selected Phase 20 next action remains remain_on_hold.",
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
print(f"Runtime options written to: {RUNTIME_OUT}")
print(f"Options file written to: {options_file}")
print(f"safe_mode_active={safe_mode}")
print(f"strategy_rework_next_action_options_ready={strategy_rework_next_action_options_ready}")
print(f"selected_phase20_next_action={selected_phase20_next_action}")
print(f"next_action_option_count={len(next_action_options)}")
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
