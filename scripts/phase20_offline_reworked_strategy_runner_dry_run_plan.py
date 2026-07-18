import json, os, subprocess, time
from pathlib import Path

OUT = Path("data/processed/phase20_offline_reworked_strategy_runner_dry_run_plan.json")
RUNTIME_OUT = Path("runtime/phase20_offline_reworked_strategy_runner_dry_run_plan_state.json")
PHASE20_DIR = Path("data/processed/phase20_strategy_rework")

RUNNER_DESIGN = Path("data/processed/phase20_offline_reworked_strategy_runner_design.json")
RUNNER_RUNTIME = Path("runtime/phase20_offline_reworked_strategy_runner_design_state.json")
CANDIDATE_RULES = Path("data/processed/phase20_candidate_rejection_rules_design.json")
QUALITY_GATE = Path("data/processed/phase20_strategy_quality_gate_v2_design.json")
BACKTEST_SPEC = Path("data/processed/phase20_offline_reworked_strategy_backtest_spec.json")
EXPERIMENT_DESIGN = Path("data/processed/phase20_strategy_rework_experiment_design.json")

BTC_DATASET = Path("data/processed/backtest_datasets/btcusdt_phase17_backtest_dataset.jsonl")
ETH_DATASET = Path("data/processed/backtest_datasets/ethusdt_phase17_backtest_dataset.jsonl")

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

def count_lines(path):
    if not path.exists():
        return 0
    try:
        with path.open("r") as f:
            return sum(1 for _ in f)
    except Exception:
        return 0

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

runner = load_json(RUNNER_DESIGN)
runner_runtime = load_json(RUNNER_RUNTIME)
rules = load_json(CANDIDATE_RULES)
gate = load_json(QUALITY_GATE)
spec = load_json(BACKTEST_SPEC)
experiment = load_json(EXPERIMENT_DESIGN)

offline_runner_design_ready = (
    runner.get("offline_runner_design_ready") is True
    or runner_runtime.get("offline_runner_design_ready") is True
)

candidate_rejection_rules_ready = rules.get("candidate_rejection_rules_ready") is True
strategy_quality_gate_v2_ready = gate.get("strategy_quality_gate_v2_ready") is True
offline_backtest_spec_ready = spec.get("offline_backtest_spec_ready") is True
experiment_design_ready = experiment.get("strategy_rework_experiment_design_ready") is True

selected_option = runner.get("selected_option") or runner_runtime.get("selected_option")
selected_phase19_path = runner.get("selected_phase19_path") or runner_runtime.get("selected_phase19_path")
selected_next_action = runner.get("selected_next_action") or runner_runtime.get("selected_next_action")

btc_rows = count_lines(BTC_DATASET)
eth_rows = count_lines(ETH_DATASET)

dry_run_plan = {
    "plan_id": "phase20_offline_reworked_strategy_runner_dry_run_plan_v1",
    "mode": "offline_research_only",
    "run_dry_run_now": False,
    "run_backtest_now": False,
    "execution_allowed": False,
    "paper_shadow_allowed": False,
    "live_trading_allowed": False,
    "exchange_order_submission": False,
    "real_capital_allowed": False,
    "network_download_allowed": False,
    "dry_run_objectives": [
        "verify_existing_local_dataset_paths",
        "verify_dataset_row_counts",
        "verify_runner_config_can_be_loaded",
        "verify_candidate_rules_can_be_loaded",
        "verify_quality_gate_can_be_loaded",
        "verify_output_paths_are_writable",
        "verify_no_network_download_is_requested",
        "verify_no_exchange_order_submission_is_possible",
        "verify_no_execution_approval_flags_are_true"
    ],
    "planned_dry_run_checks": [
        "check_safe_mode_flags",
        "check_btc_dataset_present",
        "check_eth_dataset_present",
        "check_local_dataset_read_only_mode",
        "check_runner_design_present",
        "check_candidate_rejection_rules_present",
        "check_quality_gate_v2_present",
        "check_backtest_spec_present",
        "check_required_output_directory",
        "check_forbidden_actions_remain_disabled"
    ],
    "future_dry_run_output_files": [
        "data/processed/phase20_strategy_rework/offline_reworked_strategy_runner_dry_run_result.json",
        "data/processed/phase20_strategy_rework/offline_reworked_strategy_runner_dry_run_checks.json",
        "runtime/phase20_offline_reworked_strategy_runner_dry_run_state.json"
    ],
    "dry_run_success_criteria": {
        "safe_mode_active": True,
        "datasets_present": True,
        "runner_design_present": True,
        "candidate_rules_present": True,
        "quality_gate_present": True,
        "network_download_allowed": False,
        "exchange_order_submission": False,
        "approved_for_execution": False,
        "approved_for_paper_shadow": False,
        "approved_for_live": False
    }
}

plan_checks = {
    "safe_mode_active": safe_mode,
    "runner_design_present": RUNNER_DESIGN.exists(),
    "runner_runtime_present": RUNNER_RUNTIME.exists(),
    "candidate_rules_present": CANDIDATE_RULES.exists(),
    "quality_gate_present": QUALITY_GATE.exists(),
    "backtest_spec_present": BACKTEST_SPEC.exists(),
    "experiment_design_present": EXPERIMENT_DESIGN.exists(),
    "offline_runner_design_ready": offline_runner_design_ready,
    "candidate_rejection_rules_ready": candidate_rejection_rules_ready,
    "strategy_quality_gate_v2_ready": strategy_quality_gate_v2_ready,
    "offline_backtest_spec_ready": offline_backtest_spec_ready,
    "experiment_design_ready": experiment_design_ready,
    "selected_option_is_remain_on_hold": selected_option == "remain_on_hold",
    "selected_next_action_is_remain_on_hold": selected_next_action == "remain_on_hold",
    "btc_dataset_present": BTC_DATASET.exists(),
    "eth_dataset_present": ETH_DATASET.exists(),
    "btc_dataset_has_rows": btc_rows > 0,
    "eth_dataset_has_rows": eth_rows > 0,
    "dry_run_plan_created": isinstance(dry_run_plan, dict),
    "run_dry_run_now_false": dry_run_plan["run_dry_run_now"] is False,
    "run_backtest_now_false": dry_run_plan["run_backtest_now"] is False,
    "execution_allowed_false": dry_run_plan["execution_allowed"] is False,
    "paper_shadow_allowed_false": dry_run_plan["paper_shadow_allowed"] is False,
    "live_trading_allowed_false": dry_run_plan["live_trading_allowed"] is False,
    "exchange_order_submission_false": dry_run_plan["exchange_order_submission"] is False,
    "real_capital_allowed_false": dry_run_plan["real_capital_allowed"] is False,
    "network_download_allowed_false": dry_run_plan["network_download_allowed"] is False,
    "approved_for_execution_false": runner.get("approved_for_execution") is False,
    "approved_for_paper_shadow_false": runner.get("approved_for_paper_shadow") is False,
    "approved_for_live_false": runner.get("approved_for_live") is False,
    "paper_shadow_not_started": runner.get("paper_shadow_started") is False,
    "paper_shadow_start_not_approved": runner.get("approved_for_paper_shadow_start") is False,
    "micro_live_not_approved": runner.get("approved_for_micro_live_execution") is False,
    "real_live_not_approved": runner.get("approved_for_real_live_trading") is False,
}

blockers = [k for k, v in plan_checks.items() if v is not True]
offline_runner_dry_run_plan_ready = all(plan_checks.values())

if offline_runner_dry_run_plan_ready:
    decision = "PHASE_20_OFFLINE_REWORKED_STRATEGY_RUNNER_DRY_RUN_PLAN_CREATED_NOT_EXECUTED"
    next_phase = "Phase 20.10 — Offline Reworked Strategy Runner Dry Run Approval Gate"
else:
    decision = "PHASE_20_OFFLINE_REWORKED_STRATEGY_RUNNER_DRY_RUN_PLAN_BLOCKED_REVIEW_REQUIRED"
    next_phase = "Phase 20.10 — Offline Runner Dry Run Plan Fix"

record = {
    "phase": "phase_20_9_offline_reworked_strategy_runner_dry_run_plan_record",
    "created_at_unix": int(time.time()),
    "git_head": current_git_head,
    "system_state": "HOLD_RESEARCH_ONLY",
    "selected_option": selected_option,
    "selected_phase19_path": selected_phase19_path,
    "selected_next_action": selected_next_action,
    "offline_runner_dry_run_plan_ready": offline_runner_dry_run_plan_ready,
    "btc_dataset_rows": btc_rows,
    "eth_dataset_rows": eth_rows,
    "plan_checks": plan_checks,
    "blockers": blockers,
    "dry_run_plan": dry_run_plan,
    "run_dry_run_now": False,
    "run_backtest_now": False,
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

record_file = PHASE20_DIR / "offline_reworked_strategy_runner_dry_run_plan.json"

write_json(record_file, record)
write_json(RUNTIME_OUT, record)

report = {
    "phase": "phase_20_9_offline_reworked_strategy_runner_dry_run_plan",
    "generated_at_unix": int(time.time()),
    "scope": "dry_run_plan_only_no_dry_run_no_backtest_no_execution",
    "git_head": current_git_head,
    "safety_flags": flags,
    "safe_mode_active": safe_mode,
    "git_working_tree_clean": git_clean_before_outputs,
    "offline_runner_dry_run_plan_ready": offline_runner_dry_run_plan_ready,
    "selected_option": selected_option,
    "selected_phase19_path": selected_phase19_path,
    "selected_next_action": selected_next_action,
    "btc_dataset_rows": btc_rows,
    "eth_dataset_rows": eth_rows,
    "dry_run_objective_count": len(dry_run_plan["dry_run_objectives"]),
    "planned_dry_run_check_count": len(dry_run_plan["planned_dry_run_checks"]),
    "plan_checks": plan_checks,
    "blockers": blockers,
    "record_file": str(record_file),
    "runtime_record_file": str(RUNTIME_OUT),
    "run_dry_run_now": False,
    "run_backtest_now": False,
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
        "This phase creates the dry-run plan only.",
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
print(f"Runtime record written to: {RUNTIME_OUT}")
print(f"Record file written to: {record_file}")
print(f"safe_mode_active={safe_mode}")
print(f"offline_runner_dry_run_plan_ready={offline_runner_dry_run_plan_ready}")
print(f"dry_run_objective_count={len(dry_run_plan['dry_run_objectives'])}")
print(f"planned_dry_run_check_count={len(dry_run_plan['planned_dry_run_checks'])}")
print("run_dry_run_now=False")
print("run_backtest_now=False")
print("approved_for_execution=False")
print("approved_for_paper_shadow=False")
print("approved_for_live=False")
print("paper_shadow_started=False")
print("approved_for_paper_shadow_start=False")
print("exchange_order_submission=False")
print("approved_for_micro_live_execution=False")
print("approved_for_real_live_trading=False")
print(f"decision={decision}")
