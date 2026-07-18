import json, os, subprocess, time
from pathlib import Path

OUT = Path("data/processed/phase20_offline_reworked_strategy_runner_dry_run_approval_gate.json")
RUNTIME_OUT = Path("runtime/phase20_offline_reworked_strategy_runner_dry_run_approval_gate_state.json")
PHASE20_DIR = Path("data/processed/phase20_strategy_rework")

DRY_RUN_PLAN = Path("data/processed/phase20_offline_reworked_strategy_runner_dry_run_plan.json")
DRY_RUN_PLAN_RUNTIME = Path("runtime/phase20_offline_reworked_strategy_runner_dry_run_plan_state.json")
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

plan = load_json(DRY_RUN_PLAN)
plan_runtime = load_json(DRY_RUN_PLAN_RUNTIME)
runner = load_json(RUNNER_DESIGN)
rules = load_json(CANDIDATE_RULES)
gate = load_json(QUALITY_GATE)
spec = load_json(BACKTEST_SPEC)

offline_runner_dry_run_plan_ready = (
    plan.get("offline_runner_dry_run_plan_ready") is True
    or plan_runtime.get("offline_runner_dry_run_plan_ready") is True
)

offline_runner_design_ready = runner.get("offline_runner_design_ready") is True
candidate_rejection_rules_ready = rules.get("candidate_rejection_rules_ready") is True
strategy_quality_gate_v2_ready = gate.get("strategy_quality_gate_v2_ready") is True
offline_backtest_spec_ready = spec.get("offline_backtest_spec_ready") is True

selected_option = plan.get("selected_option") or plan_runtime.get("selected_option")
selected_phase19_path = plan.get("selected_phase19_path") or plan_runtime.get("selected_phase19_path")
selected_next_action = plan.get("selected_next_action") or plan_runtime.get("selected_next_action")

manual_dry_run_approval_granted = False
dry_run_allowed = False
run_dry_run_now = False
run_backtest_now = False
execution_allowed = False

approval_gate_checks = {
    "safe_mode_active": safe_mode,
    "dry_run_plan_present": DRY_RUN_PLAN.exists(),
    "dry_run_plan_runtime_present": DRY_RUN_PLAN_RUNTIME.exists(),
    "runner_design_present": RUNNER_DESIGN.exists(),
    "candidate_rules_present": CANDIDATE_RULES.exists(),
    "quality_gate_present": QUALITY_GATE.exists(),
    "backtest_spec_present": BACKTEST_SPEC.exists(),
    "offline_runner_dry_run_plan_ready": offline_runner_dry_run_plan_ready,
    "offline_runner_design_ready": offline_runner_design_ready,
    "candidate_rejection_rules_ready": candidate_rejection_rules_ready,
    "strategy_quality_gate_v2_ready": strategy_quality_gate_v2_ready,
    "offline_backtest_spec_ready": offline_backtest_spec_ready,
    "selected_option_is_remain_on_hold": selected_option == "remain_on_hold",
    "selected_next_action_is_remain_on_hold": selected_next_action == "remain_on_hold",
    "manual_dry_run_approval_not_granted": manual_dry_run_approval_granted is False,
    "dry_run_not_allowed": dry_run_allowed is False,
    "run_dry_run_now_false": run_dry_run_now is False,
    "run_backtest_now_false": run_backtest_now is False,
    "execution_allowed_false": execution_allowed is False,
    "approved_for_execution_false": plan.get("approved_for_execution") is False,
    "approved_for_paper_shadow_false": plan.get("approved_for_paper_shadow") is False,
    "approved_for_live_false": plan.get("approved_for_live") is False,
    "paper_shadow_not_started": plan.get("paper_shadow_started") is False,
    "paper_shadow_start_not_approved": plan.get("approved_for_paper_shadow_start") is False,
    "exchange_order_submission_disabled": plan.get("exchange_order_submission") is False,
    "micro_live_not_approved": plan.get("approved_for_micro_live_execution") is False,
    "real_live_not_approved": plan.get("approved_for_real_live_trading") is False,
}

blockers = [k for k, v in approval_gate_checks.items() if v is not True]
dry_run_approval_gate_ready = all(approval_gate_checks.values())

if dry_run_approval_gate_ready:
    decision = "PHASE_20_OFFLINE_REWORKED_STRATEGY_RUNNER_DRY_RUN_APPROVAL_GATE_CREATED_NOT_APPROVED_FOR_DRY_RUN"
    next_phase = "Phase 20.11 — Offline Reworked Strategy Runner Dry Run Manual Approval Record"
else:
    decision = "PHASE_20_OFFLINE_REWORKED_STRATEGY_RUNNER_DRY_RUN_APPROVAL_GATE_BLOCKED_REVIEW_REQUIRED"
    next_phase = "Phase 20.11 — Offline Runner Dry Run Approval Gate Fix"

approval_gate = {
    "phase": "phase_20_10_offline_reworked_strategy_runner_dry_run_approval_gate_record",
    "created_at_unix": int(time.time()),
    "git_head": current_git_head,
    "system_state": "HOLD_RESEARCH_ONLY",
    "selected_option": selected_option,
    "selected_phase19_path": selected_phase19_path,
    "selected_next_action": selected_next_action,
    "dry_run_approval_gate_ready": dry_run_approval_gate_ready,
    "manual_dry_run_approval_granted": False,
    "dry_run_allowed": False,
    "run_dry_run_now": False,
    "run_backtest_now": False,
    "execution_allowed": False,
    "approval_gate_checks": approval_gate_checks,
    "blockers": blockers,
    "required_manual_approval_fields": {
        "approved_by": None,
        "approved_at_unix": None,
        "approval_scope": "offline_reworked_strategy_runner_dry_run_only",
        "approval_statement_required": "I approve Phase 20 offline runner dry run only. I do not approve paper shadow, micro-live, live trading, exchange orders, or real capital usage."
    },
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

gate_file = PHASE20_DIR / "offline_reworked_strategy_runner_dry_run_approval_gate.json"
template_file = PHASE20_DIR / "offline_reworked_strategy_runner_dry_run_manual_approval_template.json"

manual_template = {
    "phase": "phase_20_10_manual_approval_template",
    "manual_dry_run_approval_granted": False,
    "approved_by": None,
    "approved_at_unix": None,
    "approval_scope": "offline_reworked_strategy_runner_dry_run_only",
    "dry_run_allowed": False,
    "run_dry_run_now": False,
    "run_backtest_now": False,
    "approved_for_execution": False,
    "approved_for_paper_shadow": False,
    "approved_for_live": False,
    "exchange_order_submission": False,
    "approval_statement_required": approval_gate["required_manual_approval_fields"]["approval_statement_required"]
}

write_json(gate_file, approval_gate)
write_json(template_file, manual_template)
write_json(RUNTIME_OUT, approval_gate)

report = {
    "phase": "phase_20_10_offline_reworked_strategy_runner_dry_run_approval_gate",
    "generated_at_unix": int(time.time()),
    "scope": "dry_run_approval_gate_only_no_dry_run_no_backtest_no_execution",
    "git_head": current_git_head,
    "safety_flags": flags,
    "safe_mode_active": safe_mode,
    "git_working_tree_clean": git_clean_before_outputs,
    "dry_run_approval_gate_ready": dry_run_approval_gate_ready,
    "selected_option": selected_option,
    "selected_phase19_path": selected_phase19_path,
    "selected_next_action": selected_next_action,
    "approval_gate_checks": approval_gate_checks,
    "blockers": blockers,
    "gate_file": str(gate_file),
    "manual_approval_template_file": str(template_file),
    "runtime_gate_file": str(RUNTIME_OUT),
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
        "This phase creates the dry-run approval gate only.",
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
print(f"Runtime gate written to: {RUNTIME_OUT}")
print(f"Gate file written to: {gate_file}")
print(f"Manual approval template written to: {template_file}")
print(f"safe_mode_active={safe_mode}")
print(f"dry_run_approval_gate_ready={dry_run_approval_gate_ready}")
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
