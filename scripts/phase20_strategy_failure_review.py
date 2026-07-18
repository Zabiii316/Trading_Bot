import json, os, subprocess, time
from pathlib import Path

OUT = Path("data/processed/phase20_strategy_failure_review.json")
RUNTIME_OUT = Path("runtime/phase20_strategy_failure_review_state.json")
PHASE20_DIR = Path("data/processed/phase20_strategy_rework")

READINESS = Path("data/processed/phase20_strategy_rework_readiness_review.json")
READINESS_RUNTIME = Path("runtime/phase20_strategy_rework_readiness_review_state.json")

BASELINE_BACKTEST = Path("data/processed/phase17_baseline_historical_backtest_runner.json")
BACKTEST_REVIEW = Path("data/processed/phase17_backtest_results_review_quality_gate.json")
SWEEP_DESIGN = Path("data/processed/phase17_strategy_rework_parameter_sweep_design.json")
SWEEP_RUNNER = Path("data/processed/phase17_parameter_sweep_backtest_runner.json")
CANDIDATE_REVIEW = Path("data/processed/phase17_parameter_sweep_results_review_candidate_selection.json")
SWEEP_RESULTS_JSONL = Path("data/processed/backtest_results/phase17_parameter_sweep_results.jsonl")

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

def compact_keys(data):
    if not isinstance(data, dict):
        return []
    return sorted(list(data.keys()))

flags = {
    "BINANCE_TESTNET": os.getenv("BINANCE_TESTNET", ""),
    "BINANCE_USE_TESTNET": os.getenv("BINANCE_USE_TESTNET", ""),
    "BINANCE_ENABLE_LIVE_TRADING": os.getenv("BINANCE_ENABLE_LIVE_TRADING", ""),
    "LIVE_TRADING_ALLOWED": os.getenv("LIVE_TRADING_ALLOWED", ""),
}

safe_mode = flags["BINANCE_ENABLE_LIVE_TRADING"] == "false" and flags["LIVE_TRADING_ALLOWED"] == "false"
current_git_head = git_head()
git_clean_before_outputs = git_clean()

readiness = load_json(READINESS)
readiness_runtime = load_json(READINESS_RUNTIME)
baseline = load_json(BASELINE_BACKTEST)
review = load_json(BACKTEST_REVIEW)
sweep_design = load_json(SWEEP_DESIGN)
sweep_runner = load_json(SWEEP_RUNNER)
candidate_review = load_json(CANDIDATE_REVIEW)

research_only_ready = (
    readiness.get("research_only_strategy_rework_ready") is True
    or readiness_runtime.get("research_only_strategy_rework_ready") is True
)

selected_option = readiness.get("selected_option") or readiness_runtime.get("selected_option")
selected_phase19_path = readiness.get("selected_phase19_path") or readiness_runtime.get("selected_phase19_path")
selected_next_action = readiness.get("selected_next_action") or readiness_runtime.get("selected_next_action")

btc_rows = count_lines(BTC_DATASET)
eth_rows = count_lines(ETH_DATASET)
sweep_result_rows = count_lines(SWEEP_RESULTS_JSONL)

failure_findings = [
    {
        "finding_id": "baseline_negative_expectancy",
        "description": "Phase 17 baseline backtests showed negative strategy performance, so the current signal logic is not acceptable for execution.",
        "severity": "critical"
    },
    {
        "finding_id": "candidate_selection_not_approved",
        "description": "Parameter sweep and candidate review did not produce an execution-approved strategy candidate.",
        "severity": "critical"
    },
    {
        "finding_id": "historical_data_coverage_limited",
        "description": "Historical expansion remains on hold, so current rework must treat available BTC/ETH datasets as limited research inputs only.",
        "severity": "high"
    },
    {
        "finding_id": "execution_gates_closed",
        "description": "Paper shadow, micro-live, real live trading, and exchange order submission remain disabled.",
        "severity": "safety_control"
    }
]

failure_hypotheses = [
    {
        "hypothesis_id": "weak_regime_filtering",
        "description": "The strategy may be entering during poor market regimes without sufficient trend/range/volatility filtering."
    },
    {
        "hypothesis_id": "exit_logic_too_simple",
        "description": "Losses may not be controlled well enough by the existing exit logic, requiring stronger stop, trailing, time, and invalidation rules."
    },
    {
        "hypothesis_id": "fees_slippage_overpower_edge",
        "description": "The gross signal edge may be too small after fees and slippage."
    },
    {
        "hypothesis_id": "overfit_or_unstable_parameters",
        "description": "Parameter sweep results may be unstable or not robust enough across symbols."
    },
    {
        "hypothesis_id": "limited_data_coverage",
        "description": "BTC/ETH-only or limited timeframe coverage may be insufficient for reliable strategy approval."
    }
]

recommended_rework_directions = [
    "Add explicit market regime classification before signal scoring.",
    "Require multi-timeframe confirmation before long or short signal approval.",
    "Add volatility-aware stop loss and take-profit rules.",
    "Add maximum adverse excursion and maximum favorable excursion review.",
    "Separate entry logic from risk/exit logic for clearer testing.",
    "Reject candidates that only work on one symbol or one small time window.",
    "Keep all next steps offline/research-only until a new backtest quality gate passes."
]

review_checks = {
    "safe_mode_active": safe_mode,
    "phase20_readiness_present": READINESS.exists(),
    "phase20_readiness_runtime_present": READINESS_RUNTIME.exists(),
    "research_only_strategy_rework_ready": research_only_ready,
    "selected_option_is_remain_on_hold": selected_option == "remain_on_hold",
    "selected_next_action_is_remain_on_hold": selected_next_action == "remain_on_hold",
    "baseline_backtest_present": BASELINE_BACKTEST.exists(),
    "backtest_review_present": BACKTEST_REVIEW.exists(),
    "sweep_design_present": SWEEP_DESIGN.exists(),
    "sweep_runner_present": SWEEP_RUNNER.exists(),
    "candidate_review_present": CANDIDATE_REVIEW.exists(),
    "sweep_results_jsonl_present": SWEEP_RESULTS_JSONL.exists(),
    "btc_dataset_present": BTC_DATASET.exists(),
    "eth_dataset_present": ETH_DATASET.exists(),
    "btc_dataset_has_rows": btc_rows > 0,
    "eth_dataset_has_rows": eth_rows > 0,
    "execution_not_approved": readiness.get("approved_for_execution") is False,
    "paper_shadow_not_started": readiness.get("paper_shadow_started") is False,
    "paper_shadow_start_not_approved": readiness.get("approved_for_paper_shadow_start") is False,
    "exchange_order_submission_disabled": readiness.get("exchange_order_submission") is False,
    "micro_live_not_approved": readiness.get("approved_for_micro_live_execution") is False,
    "real_live_not_approved": readiness.get("approved_for_real_live_trading") is False,
}

blockers = [k for k, v in review_checks.items() if v is not True]
strategy_failure_review_ready = all(review_checks.values())

if strategy_failure_review_ready:
    decision = "PHASE_20_STRATEGY_FAILURE_REVIEW_COMPLETE_REWORK_REQUIRED_RESEARCH_ONLY"
    next_phase = "Phase 20.3 — Strategy Rework Hypothesis Plan"
else:
    decision = "PHASE_20_STRATEGY_FAILURE_REVIEW_BLOCKED_REVIEW_REQUIRED"
    next_phase = "Phase 20.3 — Strategy Failure Review Fix"

record = {
    "phase": "phase_20_2_strategy_failure_review_record",
    "created_at_unix": int(time.time()),
    "git_head": current_git_head,
    "system_state": "HOLD_RESEARCH_ONLY",
    "selected_option": selected_option,
    "selected_phase19_path": selected_phase19_path,
    "selected_next_action": selected_next_action,
    "strategy_failure_review_ready": strategy_failure_review_ready,
    "review_checks": review_checks,
    "blockers": blockers,
    "btc_dataset_rows": btc_rows,
    "eth_dataset_rows": eth_rows,
    "sweep_result_rows": sweep_result_rows,
    "source_summary": {
        "baseline_backtest_keys": compact_keys(baseline),
        "backtest_review_keys": compact_keys(review),
        "sweep_design_keys": compact_keys(sweep_design),
        "sweep_runner_keys": compact_keys(sweep_runner),
        "candidate_review_keys": compact_keys(candidate_review)
    },
    "failure_findings": failure_findings,
    "failure_hypotheses": failure_hypotheses,
    "recommended_rework_directions": recommended_rework_directions,
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

record_file = PHASE20_DIR / "strategy_failure_review.json"
write_json(record_file, record)
write_json(RUNTIME_OUT, record)

report = {
    "phase": "phase_20_2_strategy_failure_review",
    "generated_at_unix": int(time.time()),
    "scope": "research_only_failure_review_no_execution",
    "git_head": current_git_head,
    "safety_flags": flags,
    "safe_mode_active": safe_mode,
    "git_working_tree_clean": git_clean_before_outputs,
    "strategy_failure_review_ready": strategy_failure_review_ready,
    "selected_option": selected_option,
    "selected_phase19_path": selected_phase19_path,
    "selected_next_action": selected_next_action,
    "btc_dataset_rows": btc_rows,
    "eth_dataset_rows": eth_rows,
    "sweep_result_rows": sweep_result_rows,
    "review_checks": review_checks,
    "blockers": blockers,
    "failure_findings": failure_findings,
    "failure_hypotheses": failure_hypotheses,
    "recommended_rework_directions": recommended_rework_directions,
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
        "This phase reviews failed strategy/backtest behavior only.",
        "This phase does not approve historical data download.",
        "This phase does not approve historical data import.",
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
print(f"strategy_failure_review_ready={strategy_failure_review_ready}")
print(f"selected_option={selected_option}")
print(f"selected_phase19_path={selected_phase19_path}")
print(f"selected_next_action={selected_next_action}")
print(f"btc_dataset_rows={btc_rows}")
print(f"eth_dataset_rows={eth_rows}")
print(f"sweep_result_rows={sweep_result_rows}")
print("approved_for_execution=False")
print("approved_for_paper_shadow=False")
print("approved_for_live=False")
print("paper_shadow_started=False")
print("approved_for_paper_shadow_start=False")
print("exchange_order_submission=False")
print("approved_for_micro_live_execution=False")
print("approved_for_real_live_trading=False")
print(f"decision={decision}")
