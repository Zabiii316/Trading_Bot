import json, os, subprocess, time
from pathlib import Path

OUT = Path("data/processed/phase17_strategy_rework_parameter_sweep_design.json")
INPUT = Path("data/processed/phase17_backtest_results_review_quality_gate.json")

def run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True)

def git_clean():
    return run(["git", "status", "--short"]).stdout.strip() == ""

def load(path):
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except Exception:
        return {}

flags = {
    "BINANCE_TESTNET": os.getenv("BINANCE_TESTNET", ""),
    "BINANCE_USE_TESTNET": os.getenv("BINANCE_USE_TESTNET", ""),
    "BINANCE_ENABLE_LIVE_TRADING": os.getenv("BINANCE_ENABLE_LIVE_TRADING", ""),
    "LIVE_TRADING_ALLOWED": os.getenv("LIVE_TRADING_ALLOWED", ""),
}

safe_mode = flags["BINANCE_ENABLE_LIVE_TRADING"] == "false" and flags["LIVE_TRADING_ALLOWED"] == "false"

quality_gate = load(INPUT)
failed_symbols = quality_gate.get("failed_symbols", [])
approved_symbols = quality_gate.get("approved_symbols", [])

parameter_grid = {
    "fast_windows": [3, 5, 8, 10, 12],
    "slow_windows": [20, 30, 50, 80, 100],
    "trend_filters": [
        "none",
        "price_above_slow_ma",
        "higher_high_higher_low",
        "positive_momentum_only"
    ],
    "risk_filters": [
        "fixed_exit",
        "atr_stop",
        "trailing_stop",
        "time_based_exit"
    ],
    "fee_bps": [4],
    "slippage_bps": [2, 4, 6],
}

strategy_rework_plan = {
    "problem_summary": [
        "Baseline moving-average strategy failed the quality gate.",
        "BTCUSDT and ETHUSDT showed negative net returns.",
        "The baseline strategy likely over-trades weak signals.",
        "A parameter sweep is required before any future approval review."
    ],
    "rework_actions": [
        "Test multiple fast/slow moving-average combinations.",
        "Add trend filters to avoid sideways-market entries.",
        "Add risk filters to reduce drawdown and repeated losing trades.",
        "Compare fee/slippage sensitivity.",
        "Reject configurations with low trade count, negative expectancy, or excessive drawdown.",
        "Require out-of-sample review after any promising parameter set."
    ],
    "quality_gate_for_next_phase": {
        "minimum_profit_factor": 1.20,
        "minimum_win_rate_pct": 45.0,
        "maximum_drawdown_pct": 20.0,
        "minimum_trades": 30,
        "minimum_net_return_bps": 0.0
    }
}

total_combinations = (
    len(parameter_grid["fast_windows"])
    * len(parameter_grid["slow_windows"])
    * len(parameter_grid["trend_filters"])
    * len(parameter_grid["risk_filters"])
    * len(parameter_grid["fee_bps"])
    * len(parameter_grid["slippage_bps"])
)

report = {
    "phase": "phase_17_6_strategy_rework_parameter_sweep_design",
    "generated_at_unix": int(time.time()),
    "scope": "strategy_rework_plan_and_parameter_sweep_design_only",
    "safety_flags": flags,
    "safe_mode_active": safe_mode,
    "git_working_tree_clean": git_clean(),
    "quality_gate_input_present": INPUT.exists(),
    "previous_approved_symbols": approved_symbols,
    "previous_failed_symbols": failed_symbols,
    "strategy_rework_plan": strategy_rework_plan,
    "parameter_grid": parameter_grid,
    "total_parameter_combinations": total_combinations,
    "approved_for_micro_live_execution": False,
    "approved_for_real_live_trading": False,
    "decision": "STRATEGY_REWORK_PARAMETER_SWEEP_DESIGN_CREATED_NOT_APPROVED_FOR_EXECUTION",
    "next_phase": "Phase 17.7 — Parameter Sweep Backtest Runner",
    "safety_notes": [
        "This phase designs a strategy rework and parameter sweep only.",
        "This phase does not approve live trading.",
        "This phase does not approve micro-live execution.",
        "This phase does not submit Binance orders.",
        "Strategy must pass future backtest and review gates before any execution approval."
    ],
}

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(report, indent=2))

print(f"Report written to: {OUT}")
print(f"safe_mode_active={safe_mode}")
print(f"quality_gate_input_present={INPUT.exists()}")
print(f"previous_failed_symbols={','.join(failed_symbols) if failed_symbols else 'none'}")
print(f"total_parameter_combinations={total_combinations}")
print("approved_for_micro_live_execution=False")
print("approved_for_real_live_trading=False")
print(f"decision={report['decision']}")
