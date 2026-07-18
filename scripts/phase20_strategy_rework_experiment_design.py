import json, os, subprocess, time
from pathlib import Path

OUT = Path("data/processed/phase20_strategy_rework_experiment_design.json")
RUNTIME_OUT = Path("runtime/phase20_strategy_rework_experiment_design_state.json")
PHASE20_DIR = Path("data/processed/phase20_strategy_rework")

HYPOTHESIS_PLAN = Path("data/processed/phase20_strategy_rework_hypothesis_plan.json")
HYPOTHESIS_RUNTIME = Path("runtime/phase20_strategy_rework_hypothesis_plan_state.json")
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

hypothesis = load_json(HYPOTHESIS_PLAN)
hypothesis_runtime = load_json(HYPOTHESIS_RUNTIME)
failure = load_json(FAILURE_REVIEW)
readiness = load_json(READINESS)

hypothesis_plan_ready = (
    hypothesis.get("strategy_rework_hypothesis_plan_ready") is True
    or hypothesis_runtime.get("strategy_rework_hypothesis_plan_ready") is True
)

selected_option = hypothesis.get("selected_option") or hypothesis_runtime.get("selected_option")
selected_phase19_path = hypothesis.get("selected_phase19_path") or hypothesis_runtime.get("selected_phase19_path")
selected_next_action = hypothesis.get("selected_next_action") or hypothesis_runtime.get("selected_next_action")

btc_rows = count_lines(BTC_DATASET)
eth_rows = count_lines(ETH_DATASET)

experiment_design = {
    "design_id": "phase20_strategy_rework_experiment_design_v1",
    "mode": "offline_research_only",
    "datasets": [
        {
            "symbol": "BTCUSDT",
            "path": str(BTC_DATASET),
            "rows": btc_rows,
            "allowed": BTC_DATASET.exists() and btc_rows > 0
        },
        {
            "symbol": "ETHUSDT",
            "path": str(ETH_DATASET),
            "rows": eth_rows,
            "allowed": ETH_DATASET.exists() and eth_rows > 0
        }
    ],
    "experiment_groups": [
        {
            "group_id": "regime_filter",
            "purpose": "Test whether trend/range/volatility filters reduce bad entries.",
            "variants": [
                "none_baseline_reference",
                "price_above_slow_ma",
                "positive_momentum_only",
                "volatility_band_filter",
                "trend_strength_filter"
            ]
        },
        {
            "group_id": "multi_timeframe_confirmation",
            "purpose": "Test whether higher-timeframe alignment improves signal quality.",
            "variants": [
                "single_timeframe_reference",
                "fast_plus_slow_confirmation",
                "momentum_alignment",
                "trend_confirmation_required"
            ]
        },
        {
            "group_id": "volatility_aware_exits",
            "purpose": "Test stronger loss control and exit logic.",
            "variants": [
                "fixed_exit_reference",
                "atr_stop",
                "atr_take_profit",
                "trailing_stop",
                "time_stop",
                "signal_invalidation_stop"
            ]
        },
        {
            "group_id": "fee_slippage_edge_filter",
            "purpose": "Reject trades where expected edge does not beat costs.",
            "variants": [
                "fee_slippage_6bps",
                "fee_slippage_8bps",
                "fee_slippage_10bps",
                "minimum_expected_edge_12bps",
                "minimum_expected_edge_18bps"
            ]
        },
        {
            "group_id": "robustness_filter",
            "purpose": "Reject unstable or overfit candidates.",
            "variants": [
                "btc_only_reject",
                "eth_only_reject",
                "both_symbols_required",
                "parameter_neighborhood_required",
                "drawdown_cap_required"
            ]
        }
    ],
    "required_metrics": [
        "net_return_bps",
        "gross_return_bps",
        "fee_bps",
        "slippage_bps",
        "trade_count",
        "win_rate",
        "profit_factor",
        "max_drawdown_pct",
        "average_win_bps",
        "average_loss_bps",
        "expectancy_bps",
        "symbol_level_results"
    ],
    "minimum_quality_gate": {
        "net_return_bps_must_be_positive": True,
        "max_drawdown_pct_must_improve_vs_phase17": True,
        "must_pass_btc_and_eth": True,
        "must_include_fees_and_slippage": True,
        "must_not_depend_on_one_symbol": True,
        "must_not_approve_execution": True
    }
}

design_checks = {
    "safe_mode_active": safe_mode,
    "hypothesis_plan_present": HYPOTHESIS_PLAN.exists(),
    "hypothesis_runtime_present": HYPOTHESIS_RUNTIME.exists(),
    "failure_review_present": FAILURE_REVIEW.exists(),
    "readiness_present": READINESS.exists(),
    "hypothesis_plan_ready": hypothesis_plan_ready,
    "selected_option_is_remain_on_hold": selected_option == "remain_on_hold",
    "selected_next_action_is_remain_on_hold": selected_next_action == "remain_on_hold",
    "btc_dataset_present": BTC_DATASET.exists(),
    "eth_dataset_present": ETH_DATASET.exists(),
    "btc_dataset_has_rows": btc_rows > 0,
    "eth_dataset_has_rows": eth_rows > 0,
    "experiment_groups_created": len(experiment_design["experiment_groups"]) >= 5,
    "required_metrics_created": len(experiment_design["required_metrics"]) >= 8,
    "quality_gate_created": isinstance(experiment_design["minimum_quality_gate"], dict),
    "approved_for_execution_false": hypothesis.get("approved_for_execution") is False,
    "approved_for_paper_shadow_false": hypothesis.get("approved_for_paper_shadow") is False,
    "approved_for_live_false": hypothesis.get("approved_for_live") is False,
    "paper_shadow_not_started": hypothesis.get("paper_shadow_started") is False,
    "paper_shadow_start_not_approved": hypothesis.get("approved_for_paper_shadow_start") is False,
    "exchange_order_submission_disabled": hypothesis.get("exchange_order_submission") is False,
    "micro_live_not_approved": hypothesis.get("approved_for_micro_live_execution") is False,
    "real_live_not_approved": hypothesis.get("approved_for_real_live_trading") is False,
}

blockers = [k for k, v in design_checks.items() if v is not True]
strategy_rework_experiment_design_ready = all(design_checks.values())

if strategy_rework_experiment_design_ready:
    decision = "PHASE_20_STRATEGY_REWORK_EXPERIMENT_DESIGN_CREATED_RESEARCH_ONLY_NOT_APPROVED_FOR_EXECUTION"
    next_phase = "Phase 20.5 — Offline Reworked Strategy Backtest Spec"
else:
    decision = "PHASE_20_STRATEGY_REWORK_EXPERIMENT_DESIGN_BLOCKED_REVIEW_REQUIRED"
    next_phase = "Phase 20.5 — Strategy Rework Experiment Design Fix"

record = {
    "phase": "phase_20_4_strategy_rework_experiment_design_record",
    "created_at_unix": int(time.time()),
    "git_head": current_git_head,
    "system_state": "HOLD_RESEARCH_ONLY",
    "selected_option": selected_option,
    "selected_phase19_path": selected_phase19_path,
    "selected_next_action": selected_next_action,
    "strategy_rework_experiment_design_ready": strategy_rework_experiment_design_ready,
    "design_checks": design_checks,
    "blockers": blockers,
    "btc_dataset_rows": btc_rows,
    "eth_dataset_rows": eth_rows,
    "experiment_design": experiment_design,
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

record_file = PHASE20_DIR / "strategy_rework_experiment_design.json"

write_json(record_file, record)
write_json(RUNTIME_OUT, record)

report = {
    "phase": "phase_20_4_strategy_rework_experiment_design",
    "generated_at_unix": int(time.time()),
    "scope": "research_only_experiment_design_no_backtest_no_execution",
    "git_head": current_git_head,
    "safety_flags": flags,
    "safe_mode_active": safe_mode,
    "git_working_tree_clean": git_clean_before_outputs,
    "strategy_rework_experiment_design_ready": strategy_rework_experiment_design_ready,
    "selected_option": selected_option,
    "selected_phase19_path": selected_phase19_path,
    "selected_next_action": selected_next_action,
    "btc_dataset_rows": btc_rows,
    "eth_dataset_rows": eth_rows,
    "experiment_group_count": len(experiment_design["experiment_groups"]),
    "required_metric_count": len(experiment_design["required_metrics"]),
    "design_checks": design_checks,
    "blockers": blockers,
    "record_file": str(record_file),
    "runtime_record_file": str(RUNTIME_OUT),
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
        "This phase creates the offline experiment design only.",
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
print(f"strategy_rework_experiment_design_ready={strategy_rework_experiment_design_ready}")
print(f"experiment_group_count={len(experiment_design['experiment_groups'])}")
print(f"required_metric_count={len(experiment_design['required_metrics'])}")
print("approved_for_execution=False")
print("approved_for_paper_shadow=False")
print("approved_for_live=False")
print("paper_shadow_started=False")
print("approved_for_paper_shadow_start=False")
print("exchange_order_submission=False")
print("approved_for_micro_live_execution=False")
print("approved_for_real_live_trading=False")
print(f"decision={decision}")
