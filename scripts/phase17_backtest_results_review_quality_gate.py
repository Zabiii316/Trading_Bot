import json, os, subprocess, time
from pathlib import Path

OUT = Path("data/processed/phase17_backtest_results_review_quality_gate.json")
INPUT = Path("data/processed/phase17_baseline_historical_backtest_runner.json")

MIN_PROFIT_FACTOR = 1.20
MIN_WIN_RATE = 45.0
MAX_DRAWDOWN_PCT = 20.0
MIN_TRADES = 30
MIN_NET_RETURN_BPS = 0.0

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

backtest = load(INPUT)
results = backtest.get("results", {})

quality_results = {}
approved_symbols = []
failed_symbols = []

for symbol, result in results.items():
    trade_count = result.get("trade_count", 0) or 0
    win_rate = result.get("win_rate_pct", 0) or 0
    profit_factor = result.get("profit_factor")
    max_drawdown = result.get("max_drawdown_pct", 999) or 999
    net_return = result.get("net_return_bps", 0) or 0

    checks = {
        "minimum_trades_passed": trade_count >= MIN_TRADES,
        "net_return_positive": net_return > MIN_NET_RETURN_BPS,
        "profit_factor_passed": profit_factor is not None and profit_factor >= MIN_PROFIT_FACTOR,
        "win_rate_passed": win_rate >= MIN_WIN_RATE,
        "drawdown_passed": max_drawdown <= MAX_DRAWDOWN_PCT,
    }

    passed = all(checks.values())

    quality_results[symbol] = {
        "status": result.get("status"),
        "trade_count": trade_count,
        "net_return_bps": net_return,
        "win_rate_pct": win_rate,
        "profit_factor": profit_factor,
        "max_drawdown_pct": max_drawdown,
        "checks": checks,
        "quality_gate_passed": passed,
    }

    if passed:
        approved_symbols.append(symbol)
    else:
        failed_symbols.append(symbol)

report = {
    "phase": "phase_17_5_backtest_results_review_quality_gate",
    "generated_at_unix": int(time.time()),
    "scope": "backtest_results_review_and_strategy_quality_gate_only",
    "safety_flags": flags,
    "safe_mode_active": safe_mode,
    "git_working_tree_clean": git_clean(),
    "input_present": INPUT.exists(),
    "thresholds": {
        "min_profit_factor": MIN_PROFIT_FACTOR,
        "min_win_rate_pct": MIN_WIN_RATE,
        "max_drawdown_pct": MAX_DRAWDOWN_PCT,
        "min_trades": MIN_TRADES,
        "min_net_return_bps": MIN_NET_RETURN_BPS,
    },
    "quality_results": quality_results,
    "approved_symbols": approved_symbols,
    "failed_symbols": failed_symbols,
    "strategy_quality_gate_passed": len(approved_symbols) > 0 and len(failed_symbols) == 0,
    "approved_for_micro_live_execution": False,
    "approved_for_real_live_trading": False,
    "decision": "BACKTEST_QUALITY_GATE_FAILED_STRATEGY_REWORK_REQUIRED_NOT_APPROVED_FOR_EXECUTION",
    "next_phase": "Phase 17.6 — Strategy Rework Plan and Parameter Sweep Design",
    "safety_notes": [
        "Baseline strategy failed the quality gate.",
        "This phase does not approve live trading.",
        "This phase does not approve micro-live execution.",
        "Strategy logic must be improved before any future approval gate.",
    ],
}

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(report, indent=2))

print(f"Report written to: {OUT}")
print(f"safe_mode_active={safe_mode}")
print(f"input_present={INPUT.exists()}")
print(f"approved_symbols={','.join(approved_symbols) if approved_symbols else 'none'}")
print(f"failed_symbols={','.join(failed_symbols) if failed_symbols else 'none'}")
print("strategy_quality_gate_passed=False")
print("approved_for_micro_live_execution=False")
print("approved_for_real_live_trading=False")
print(f"decision={report['decision']}")
