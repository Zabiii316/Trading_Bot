import json, os, subprocess, time
from pathlib import Path

OUT = Path("data/processed/phase20_offline_reworked_strategy_runner_design.json")
RUNTIME_OUT = Path("runtime/phase20_offline_reworked_strategy_runner_design_state.json")
PHASE20_DIR = Path("data/processed/phase20_strategy_rework")

CANDIDATE_RULES = Path("data/processed/phase20_candidate_rejection_rules_design.json")
CANDIDATE_RULES_RUNTIME = Path("runtime/phase20_candidate_rejection_rules_design_state.json")
QUALITY_GATE = Path("data/processed/phase20_strategy_quality_gate_v2_design.json")
BACKTEST_SPEC = Path("data/processed/phase20_offline_reworked_strategy_backtest_spec.json")
EXPERIMENT_DESIGN = Path("data/processed/phase20_strategy_rework_experiment_design.json")
HYPOTHESIS_PLAN = Path("data/processed/phase20_strategy_rework_hypothesis_plan.json")
FAILURE_REVIEW = Path("data/processed/phase20_strategy_failure_review.json")
READINESS = Path("data/processed/phase20_strategy_rework_readiness_review.json")

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

rules = load_json(CANDIDATE_RULES)
rules_runtime = load_json(CANDIDATE_RULES_RUNTIME)
gate = load_json(QUALITY_GATE)
spec = load_json(BACKTEST_SPEC)
experiment = load_json(EXPERIMENT_DESIGN)
hypothesis = load_json(HYPOTHESIS_PLAN)
failure = load_json(FAILURE_REVIEW)
readiness = load_json(READINESS)

candidate_rejection_rules_ready = (
    rules.get("candidate_rejection_rules_ready") is True
    or rules_runtime.get("candidate_rejection_rules_ready") is True
)

strategy_quality_gate_v2_ready = gate.get("strategy_quality_gate_v2_ready") is True
offline_backtest_spec_ready = spec.get("offline_backtest_spec_ready") is True
experiment_design_ready = experiment.get("strategy_rework_experiment_design_ready") is True
hypothesis_plan_ready = hypothesis.get("strategy_rework_hypothesis_plan_ready") is True
strategy_failure_review_ready = failure.get("strategy_failure_review_ready") is True
research_only_ready = readiness.get("research_only_strategy_rework_ready") is True

selected_option = rules.get("selected_option") or rules_runtime.get("selected_option")
selected_phase19_path = rules.get("selected_phase19_path") or rules_runtime.get("selected_phase19_path")
selected_next_action = rules.get("selected_next_action") or rules_runtime.get("selected_next_action")

btc_rows = count_lines(BTC_DATASET)
eth_rows = count_lines(ETH_DATASET)

offline_runner_design = {
    "runner_design_id": "phase20_offline_reworked_strategy_runner_design_v1",
    "mode": "offline_research_only",
    "run_backtest_now": False,
    "execution_allowed": False,
    "paper_shadow_allowed": False,
    "live_trading_allowed": False,
    "exchange_order_submission": False,
    "real_capital_allowed": False,
    "input_datasets": [
        {
            "symbol": "BTCUSDT",
            "path": str(BTC_DATASET),
            "rows": btc_rows,
            "read_only": True
        },
        {
            "symbol": "ETHUSDT",
            "path": str(ETH_DATASET),
            "rows": eth_rows,
            "read_only": True
        }
    ],
    "runner_stages": [
        "load_existing_local_dataset_only",
        "validate_dataset_schema",
        "generate_reworked_strategy_variants",
        "apply_regime_filter",
        "apply_multi_timeframe_confirmation",
        "apply_fee_slippage_edge_filter",
        "simulate_entries_and_exits_offline_only",
        "calculate_symbol_level_metrics",
        "calculate_combined_metrics",
        "apply_candidate_rejection_rules_v2",
        "apply_strategy_quality_gate_v2",
        "write_research_results_only"
    ],
    "forbidden_runner_actions": [
        "network_download",
        "historical_data_import",
        "binance_api_order_submit",
        "paper_shadow_start",
        "micro_live_execution",
        "real_live_trading",
        "real_capital_usage",
        "production_api_key_usage"
    ],
    "required_output_files": [
        "data/processed/phase20_strategy_rework/offline_reworked_strategy_runner_results.jsonl",
        "data/processed/phase20_strategy_rework/offline_reworked_strategy_runner_summary.json",
        "data/processed/phase20_strategy_rework/offline_reworked_strategy_rejected_candidates.jsonl"
    ],
    "required_result_fields": [
        "candidate_id",
        "symbol",
        "strategy_variant",
        "trade_count",
        "win_rate",
        "profit_factor",
        "net_return_bps",
        "max_drawdown_pct",
        "expectancy_bps",
        "fee_slippage_sensitivity",
        "candidate_rejection_reasons",
        "quality_gate_v2_passed",
        "approved_for_execution",
        "approved_for_paper_shadow",
        "approved_for_live",
        "exchange_order_submission"
    ],
    "safety_defaults": {
        "approved_for_execution": False,
        "approved_for_paper_shadow": False,
        "approved_for_live": False,
        "paper_shadow_started": False,
        "approved_for_paper_shadow_start": False,
        "exchange_order_submission": False,
        "approved_for_micro_live_execution": False,
        "approved_for_real_live_trading": False
    }
}

runner_checks = {
    "safe_mode_active": safe_mode,
    "candidate_rules_present": CANDIDATE_RULES.exists(),
    "candidate_rules_runtime_present": CANDIDATE_RULES_RUNTIME.exists(),
    "quality_gate_present": QUALITY_GATE.exists(),
    "backtest_spec_present": BACKTEST_SPEC.exists(),
    "experiment_design_present": EXPERIMENT_DESIGN.exists(),
    "hypothesis_plan_present": HYPOTHESIS_PLAN.exists(),
    "failure_review_present": FAILURE_REVIEW.exists(),
    "readiness_present": READINESS.exists(),
    "candidate_rejection_rules_ready": candidate_rejection_rules_ready,
    "strategy_quality_gate_v2_ready": strategy_quality_gate_v2_ready,
    "offline_backtest_spec_ready": offline_backtest_spec_ready,
    "experiment_design_ready": experiment_design_ready,
    "hypothesis_plan_ready": hypothesis_plan_ready,
    "strategy_failure_review_ready": strategy_failure_review_ready,
    "research_only_ready": research_only_ready,
    "selected_option_is_remain_on_hold": selected_option == "remain_on_hold",
    "selected_next_action_is_remain_on_hold": selected_next_action == "remain_on_hold",
    "btc_dataset_present": BTC_DATASET.exists(),
    "eth_dataset_present": ETH_DATASET.exists(),
    "btc_dataset_has_rows": btc_rows > 0,
    "eth_dataset_has_rows": eth_rows > 0,
    "runner_design_created": isinstance(offline_runner_design, dict),
    "runner_stage_count_sufficient": len(offline_runner_design["runner_stages"]) >= 10,
    "required_result_fields_created": len(offline_runner_design["required_result_fields"]) >= 12,
    "run_backtest_now_false": offline_runner_design["run_backtest_now"] is False,
    "execution_allowed_false": offline_runner_design["execution_allowed"] is False,
    "paper_shadow_allowed_false": offline_runner_design["paper_shadow_allowed"] is False,
    "live_trading_allowed_false": offline_runner_design["live_trading_allowed"] is False,
    "exchange_order_submission_false": offline_runner_design["exchange_order_submission"] is False,
    "real_capital_allowed_false": offline_runner_design["real_capital_allowed"] is False,
    "approved_for_execution_false": rules.get("approved_for_execution") is False,
    "approved_for_paper_shadow_false": rules.get("approved_for_paper_shadow") is False,
    "approved_for_live_false": rules.get("approved_for_live") is False,
    "paper_shadow_not_started": rules.get("paper_shadow_started") is False,
    "paper_shadow_start_not_approved": rules.get("approved_for_paper_shadow_start") is False,
    "micro_live_not_approved": rules.get("approved_for_micro_live_execution") is False,
    "real_live_not_approved": rules.get("approved_for_real_live_trading") is False,
}

blockers = [k for k, v in runner_checks.items() if v is not True]
offline_runner_design_ready = all(runner_checks.values())

if offline_runner_design_ready:
    decision = "PHASE_20_OFFLINE_REWORKED_STRATEGY_RUNNER_DESIGNED_RESEARCH_ONLY_NOT_EXECUTED"
    next_phase = "Phase 20.9 — Offline Reworked Strategy Runner Dry Run Plan"
else:
    decision = "PHASE_20_OFFLINE_REWORKED_STRATEGY_RUNNER_DESIGN_BLOCKED_REVIEW_REQUIRED"
    next_phase = "Phase 20.9 — Offline Runner Design Fix"

record = {
    "phase": "phase_20_8_offline_reworked_strategy_runner_design_record",
    "created_at_unix": int(time.time()),
    "git_head": current_git_head,
    "system_state": "HOLD_RESEARCH_ONLY",
    "selected_option": selected_option,
    "selected_phase19_path": selected_phase19_path,
    "selected_next_action": selected_next_action,
    "offline_runner_design_ready": offline_runner_design_ready,
    "btc_dataset_rows": btc_rows,
    "eth_dataset_rows": eth_rows,
    "runner_checks": runner_checks,
    "blockers": blockers,
    "offline_runner_design": offline_runner_design,
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

record_file = PHASE20_DIR / "offline_reworked_strategy_runner_design.json"

write_json(record_file, record)
write_json(RUNTIME_OUT, record)

report = {
    "phase": "phase_20_8_offline_reworked_strategy_runner_design",
    "generated_at_unix": int(time.time()),
    "scope": "offline_runner_design_only_no_backtest_no_execution",
    "git_head": current_git_head,
    "safety_flags": flags,
    "safe_mode_active": safe_mode,
    "git_working_tree_clean": git_clean_before_outputs,
    "offline_runner_design_ready": offline_runner_design_ready,
    "selected_option": selected_option,
    "selected_phase19_path": selected_phase19_path,
    "selected_next_action": selected_next_action,
    "btc_dataset_rows": btc_rows,
    "eth_dataset_rows": eth_rows,
    "runner_stage_count": len(offline_runner_design["runner_stages"]),
    "required_result_field_count": len(offline_runner_design["required_result_fields"]),
    "runner_checks": runner_checks,
    "blockers": blockers,
    "record_file": str(record_file),
    "runtime_record_file": str(RUNTIME_OUT),
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
        "This phase designs the offline reworked strategy runner only.",
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
print(f"offline_runner_design_ready={offline_runner_design_ready}")
print(f"runner_stage_count={len(offline_runner_design['runner_stages'])}")
print(f"required_result_field_count={len(offline_runner_design['required_result_fields'])}")
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
