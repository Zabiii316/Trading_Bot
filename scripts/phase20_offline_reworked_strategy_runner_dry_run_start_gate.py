import json, os, subprocess, time
from pathlib import Path

OUT = Path("data/processed/phase20_offline_reworked_strategy_runner_dry_run_start_gate.json")
RUNTIME_OUT = Path("runtime/phase20_offline_reworked_strategy_runner_dry_run_start_gate_state.json")
PHASE20_DIR = Path("data/processed/phase20_strategy_rework")

MANUAL_RECORD = Path("data/processed/phase20_offline_reworked_strategy_runner_dry_run_manual_approval_record.json")
MANUAL_RECORD_RUNTIME = Path("runtime/phase20_offline_reworked_strategy_runner_dry_run_manual_approval_record_state.json")
MANUAL_RECORD_FILE = Path("data/processed/phase20_strategy_rework/offline_reworked_strategy_runner_dry_run_manual_approval_record.json")
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

manual = load_json(MANUAL_RECORD)
manual_runtime = load_json(MANUAL_RECORD_RUNTIME)
manual_file = load_json(MANUAL_RECORD_FILE)
approval_gate = load_json(APPROVAL_GATE)
plan = load_json(DRY_RUN_PLAN)
runner = load_json(RUNNER_DESIGN)
rules = load_json(CANDIDATE_RULES)
quality = load_json(QUALITY_GATE)
spec = load_json(BACKTEST_SPEC)

manual_approval_record_ready = (
    manual.get("manual_approval_record_ready") is True
    or manual_runtime.get("manual_approval_record_ready") is True
    or manual_file.get("manual_approval_record_ready") is True
)

dry_run_approval_gate_ready = approval_gate.get("dry_run_approval_gate_ready") is True
offline_runner_dry_run_plan_ready = plan.get("offline_runner_dry_run_plan_ready") is True
offline_runner_design_ready = runner.get("offline_runner_design_ready") is True
candidate_rejection_rules_ready = rules.get("candidate_rejection_rules_ready") is True
strategy_quality_gate_v2_ready = quality.get("strategy_quality_gate_v2_ready") is True
offline_backtest_spec_ready = spec.get("offline_backtest_spec_ready") is True

selected_option = manual.get("selected_option") or manual_runtime.get("selected_option") or manual_file.get("selected_option")
selected_phase19_path = manual.get("selected_phase19_path") or manual_runtime.get("selected_phase19_path") or manual_file.get("selected_phase19_path")
selected_next_action = manual.get("selected_next_action") or manual_runtime.get("selected_next_action") or manual_file.get("selected_next_action")

manual_dry_run_approval_granted = False
dry_run_allowed = False
run_dry_run_now = False
run_backtest_now = False
execution_allowed = False

start_gate_checks = {
    "safe_mode_active": safe_mode,
    "manual_record_present": MANUAL_RECORD.exists(),
    "manual_record_runtime_present": MANUAL_RECORD_RUNTIME.exists(),
    "manual_record_file_present": MANUAL_RECORD_FILE.exists(),
    "approval_gate_present": APPROVAL_GATE.exists(),
    "dry_run_plan_present": DRY_RUN_PLAN.exists(),
    "runner_design_present": RUNNER_DESIGN.exists(),
    "candidate_rules_present": CANDIDATE_RULES.exists(),
    "quality_gate_present": QUALITY_GATE.exists(),
    "backtest_spec_present": BACKTEST_SPEC.exists(),
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
    "approved_for_execution_false": manual.get("approved_for_execution") is False,
    "approved_for_paper_shadow_false": manual.get("approved_for_paper_shadow") is False,
    "approved_for_live_false": manual.get("approved_for_live") is False,
    "paper_shadow_not_started": manual.get("paper_shadow_started") is False,
    "paper_shadow_start_not_approved": manual.get("approved_for_paper_shadow_start") is False,
    "exchange_order_submission_disabled": manual.get("exchange_order_submission") is False,
    "micro_live_not_approved": manual.get("approved_for_micro_live_execution") is False,
    "real_live_not_approved": manual.get("approved_for_real_live_trading") is False,
}

blockers = [k for k, v in start_gate_checks.items() if v is not True]
dry_run_start_gate_ready = all(start_gate_checks.values())

if dry_run_start_gate_ready:
    decision = "PHASE_20_OFFLINE_REWORKED_STRATEGY_RUNNER_DRY_RUN_START_GATE_CREATED_START_BLOCKED_MANUAL_APPROVAL_REQUIRED"
    next_phase = "Phase 20.13 — Offline Reworked Strategy Runner Dry Run Blocked Start Review"
else:
    decision = "PHASE_20_OFFLINE_REWORKED_STRATEGY_RUNNER_DRY_RUN_START_GATE_BLOCKED_REVIEW_REQUIRED"
    next_phase = "Phase 20.13 — Offline Runner Dry Run Start Gate Fix"

start_gate_record = {
    "phase": "phase_20_12_offline_reworked_strategy_runner_dry_run_start_gate_record",
    "created_at_unix": int(time.time()),
    "git_head": current_git_head,
    "system_state": "HOLD_RESEARCH_ONLY",
    "selected_option": selected_option,
    "selected_phase19_path": selected_phase19_path,
    "selected_next_action": selected_next_action,
    "dry_run_start_gate_ready": dry_run_start_gate_ready,
    "manual_dry_run_approval_granted": False,
    "dry_run_allowed": False,
    "run_dry_run_now": False,
    "run_backtest_now": False,
    "execution_allowed": False,
    "blocked_reason": "manual_dry_run_approval_required",
    "start_gate_checks": start_gate_checks,
    "blockers": blockers,
    "allowed_actions": [
        "blocked_start_review_only",
        "manual_approval_review_only",
        "documentation_only"
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

gate_file = PHASE20_DIR / "offline_reworked_strategy_runner_dry_run_start_gate.json"

write_json(gate_file, start_gate_record)
write_json(RUNTIME_OUT, start_gate_record)

report = {
    "phase": "phase_20_12_offline_reworked_strategy_runner_dry_run_start_gate",
    "generated_at_unix": int(time.time()),
    "scope": "dry_run_start_gate_only_no_dry_run_no_backtest_no_execution",
    "git_head": current_git_head,
    "safety_flags": flags,
    "safe_mode_active": safe_mode,
    "git_working_tree_clean": git_clean_before_outputs,
    "dry_run_start_gate_ready": dry_run_start_gate_ready,
    "selected_option": selected_option,
    "selected_phase19_path": selected_phase19_path,
    "selected_next_action": selected_next_action,
    "start_gate_checks": start_gate_checks,
    "blockers": blockers,
    "gate_file": str(gate_file),
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
        "This phase creates the dry-run start gate only.",
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
print(f"Runtime gate written to: {RUNTIME_OUT}")
print(f"Start gate written to: {gate_file}")
print(f"safe_mode_active={safe_mode}")
print(f"dry_run_start_gate_ready={dry_run_start_gate_ready}")
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
