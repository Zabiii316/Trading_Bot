import json, os, subprocess, time
from pathlib import Path

OUT = Path("data/processed/phase20_offline_reworked_strategy_backtest_spec.json")
RUNTIME_OUT = Path("runtime/phase20_offline_reworked_strategy_backtest_spec_state.json")
PHASE20_DIR = Path("data/processed/phase20_strategy_rework")

EXPERIMENT_DESIGN = Path("data/processed/phase20_strategy_rework_experiment_design.json")
EXPERIMENT_RUNTIME = Path("runtime/phase20_strategy_rework_experiment_design_state.json")
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

experiment = load_json(EXPERIMENT_DESIGN)
experiment_runtime = load_json(EXPERIMENT_RUNTIME)
hypothesis = load_json(HYPOTHESIS_PLAN)
failure = load_json(FAILURE_REVIEW)
readiness = load_json(READINESS)

experiment_design_ready = (
    experiment.get("strategy_rework_experiment_design_ready") is True
    or experiment_runtime.get("strategy_rework_experiment_design_ready") is True
)

selected_option = experiment.get("selected_option") or experiment_runtime.get("selected_option")
selected_phase19_path = experiment.get("selected_phase19_path") or experiment_runtime.get("selected_phase19_path")
selected_next_action = experiment.get("selected_next_action") or experiment_runtime.get("selected_next_action")

btc_rows = count_lines(BTC_DATASET)
eth_rows = count_lines(ETH_DATASET)

backtest_spec = {
    "spec_id": "phase20_offline_reworked_strategy_backtest_spec_v1",
    "mode": "offline_research_only",
    "execution_allowed": False,
    "run_backtest_now": False,
    "datasets": [
        {"symbol": "BTCUSDT", "path": str(BTC_DATASET), "rows": btc_rows},
        {"symbol": "ETHUSDT", "path": str(ETH_DATASET), "rows": eth_rows}
    ],
    "strategy_components_to_test": {
        "entry": [
            "regime_filter_required",
            "multi_timeframe_confirmation_required",
            "minimum_expected_edge_required"
        ],
        "exit": [
            "atr_stop",
            "trailing_stop",
            "time_stop",
            "signal_invalidation_stop"
        ],
        "cost_model": {
            "fee_bps": [4],
            "slippage_bps": [2, 4, 6, 8, 10],
            "must_report_net_after_costs": True
        },
        "risk_model": {
            "position_sizing": "research_only_fixed_fraction",
            "max_risk_fraction": 0.005,
            "live_capital_allowed": False
        }
    },
    "parameter_grid": {
        "fast_windows": [3, 5, 8, 10, 12],
        "slow_windows": [20, 30, 50, 80, 100],
        "regime_filters": [
            "price_above_slow_ma",
            "positive_momentum_only",
            "volatility_band_filter",
            "trend_strength_filter"
        ],
        "confirmation_filters": [
            "single_timeframe_reference",
            "fast_plus_slow_confirmation",
            "momentum_alignment",
            "trend_confirmation_required"
        ],
        "exit_filters": [
            "atr_stop",
            "trailing_stop",
            "time_stop",
            "signal_invalidation_stop"
        ],
        "minimum_expected_edge_bps": [8, 12, 18, 25]
    },
    "required_outputs": [
        "symbol_level_results",
        "combined_results",
        "trade_count",
        "win_rate",
        "profit_factor",
        "net_return_bps",
        "max_drawdown_pct",
        "expectancy_bps",
        "fee_slippage_sensitivity",
        "candidate_rejection_reasons"
    ],
    "candidate_rejection_rules": [
        "reject_if_net_return_bps_not_positive",
        "reject_if_max_drawdown_not_improved_vs_phase17",
        "reject_if_candidate_only_passes_one_symbol",
        "reject_if_trade_count_too_low",
        "reject_if_fee_slippage_sensitivity_fails",
        "reject_if_execution_approval_requested"
    ],
    "approval_limits": {
        "approved_for_execution": False,
        "approved_for_paper_shadow": False,
        "approved_for_live": False,
        "exchange_order_submission": False
    }
}

spec_checks = {
    "safe_mode_active": safe_mode,
    "experiment_design_present": EXPERIMENT_DESIGN.exists(),
    "experiment_runtime_present": EXPERIMENT_RUNTIME.exists(),
    "hypothesis_plan_present": HYPOTHESIS_PLAN.exists(),
    "failure_review_present": FAILURE_REVIEW.exists(),
    "readiness_present": READINESS.exists(),
    "experiment_design_ready": experiment_design_ready,
    "selected_option_is_remain_on_hold": selected_option == "remain_on_hold",
    "selected_next_action_is_remain_on_hold": selected_next_action == "remain_on_hold",
    "btc_dataset_present": BTC_DATASET.exists(),
    "eth_dataset_present": ETH_DATASET.exists(),
    "btc_dataset_has_rows": btc_rows > 0,
    "eth_dataset_has_rows": eth_rows > 0,
    "backtest_spec_created": isinstance(backtest_spec, dict),
    "run_backtest_now_false": backtest_spec["run_backtest_now"] is False,
    "execution_allowed_false": backtest_spec["execution_allowed"] is False,
    "approved_for_execution_false": experiment.get("approved_for_execution") is False,
    "approved_for_paper_shadow_false": experiment.get("approved_for_paper_shadow") is False,
    "approved_for_live_false": experiment.get("approved_for_live") is False,
    "paper_shadow_not_started": experiment.get("paper_shadow_started") is False,
    "paper_shadow_start_not_approved": experiment.get("approved_for_paper_shadow_start") is False,
    "exchange_order_submission_disabled": experiment.get("exchange_order_submission") is False,
    "micro_live_not_approved": experiment.get("approved_for_micro_live_execution") is False,
    "real_live_not_approved": experiment.get("approved_for_real_live_trading") is False,
}

blockers = [k for k, v in spec_checks.items() if v is not True]
offline_backtest_spec_ready = all(spec_checks.values())

if offline_backtest_spec_ready:
    decision = "PHASE_20_OFFLINE_REWORKED_STRATEGY_BACKTEST_SPEC_CREATED_RESEARCH_ONLY_NOT_EXECUTED"
    next_phase = "Phase 20.6 — Strategy Quality Gate V2 Design"
else:
    decision = "PHASE_20_OFFLINE_REWORKED_STRATEGY_BACKTEST_SPEC_BLOCKED_REVIEW_REQUIRED"
    next_phase = "Phase 20.6 — Offline Backtest Spec Fix"

record = {
    "phase": "phase_20_5_offline_reworked_strategy_backtest_spec_record",
    "created_at_unix": int(time.time()),
    "git_head": current_git_head,
    "system_state": "HOLD_RESEARCH_ONLY",
    "selected_option": selected_option,
    "selected_phase19_path": selected_phase19_path,
    "selected_next_action": selected_next_action,
    "offline_backtest_spec_ready": offline_backtest_spec_ready,
    "btc_dataset_rows": btc_rows,
    "eth_dataset_rows": eth_rows,
    "spec_checks": spec_checks,
    "blockers": blockers,
    "backtest_spec": backtest_spec,
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

record_file = PHASE20_DIR / "offline_reworked_strategy_backtest_spec.json"

write_json(record_file, record)
write_json(RUNTIME_OUT, record)

report = {
    "phase": "phase_20_5_offline_reworked_strategy_backtest_spec",
    "generated_at_unix": int(time.time()),
    "scope": "backtest_spec_only_no_backtest_no_execution",
    "git_head": current_git_head,
    "safety_flags": flags,
    "safe_mode_active": safe_mode,
    "git_working_tree_clean": git_clean_before_outputs,
    "offline_backtest_spec_ready": offline_backtest_spec_ready,
    "selected_option": selected_option,
    "selected_phase19_path": selected_phase19_path,
    "selected_next_action": selected_next_action,
    "btc_dataset_rows": btc_rows,
    "eth_dataset_rows": eth_rows,
    "spec_checks": spec_checks,
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
        "This phase creates a backtest specification only.",
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
print(f"offline_backtest_spec_ready={offline_backtest_spec_ready}")
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
