import json, os, subprocess, time, statistics
from pathlib import Path

OUT = Path("data/processed/phase17_baseline_historical_backtest_runner.json")
DATASET_DIR = Path("data/processed/backtest_datasets")
RESULTS_DIR = Path("data/processed/backtest_results")

FEE_BPS = 4
SLIPPAGE_BPS = 2
FAST_WINDOW = 5
SLOW_WINDOW = 20

def run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True)

def git_clean():
    return run(["git", "status", "--short"]).stdout.strip() == ""

def to_float(value):
    try:
        if value is None:
            return None
        return float(value)
    except Exception:
        return None

def extract_time(row):
    if not isinstance(row, dict):
        return 0
    for key in ["event_time_ms", "received_time_ms", "time_ms", "timestamp_ms", "start_time_ms", "end_time_ms", "t", "T"]:
        value = row.get(key)
        if isinstance(value, int):
            return value
        if isinstance(value, str) and value.isdigit():
            return int(value)
    return 0

def extract_price(row):
    if not isinstance(row, dict):
        return None

    direct_keys = [
        "price", "p", "close", "c", "last_price", "mark_price",
        "mid_price", "vwap", "avwap", "anchored_vwap", "anchor_vwap",
        "best_bid", "best_ask", "bid_price", "ask_price"
    ]

    for key in direct_keys:
        value = to_float(row.get(key))
        if value and value > 0:
            return value

    bid = to_float(row.get("best_bid") or row.get("bid_price"))
    ask = to_float(row.get("best_ask") or row.get("ask_price"))
    if bid and ask and bid > 0 and ask > 0:
        return (bid + ask) / 2

    bids = row.get("bids")
    asks = row.get("asks")
    try:
        if bids and asks:
            bid = to_float(bids[0][0])
            ask = to_float(asks[0][0])
            if bid and ask and bid > 0 and ask > 0:
                return (bid + ask) / 2
    except Exception:
        pass

    return None

def load_dataset(path):
    rows = []
    try:
        with path.open("r", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except Exception:
                    continue

                price = extract_price(row)
                if price and price > 0:
                    rows.append({
                        "time_ms": extract_time(row),
                        "price": price,
                    })
    except Exception:
        return []

    rows.sort(key=lambda x: x["time_ms"])
    return rows

def max_drawdown(equity_curve):
    if not equity_curve:
        return 0.0
    peak = equity_curve[0]
    max_dd = 0.0
    for value in equity_curve:
        peak = max(peak, value)
        if peak > 0:
            dd = (peak - value) / peak
            max_dd = max(max_dd, dd)
    return round(max_dd * 100, 4)

def run_backtest(points):
    prices = [p["price"] for p in points]
    times = [p["time_ms"] for p in points]

    if len(prices) < SLOW_WINDOW + 5:
        return {
            "status": "insufficient_price_points",
            "price_points": len(prices),
            "trade_count": 0,
            "net_return_bps": 0.0,
            "win_rate_pct": 0.0,
            "profit_factor": None,
            "max_drawdown_pct": 0.0,
            "buy_hold_return_bps": 0.0,
        }

    buy_hold_return_bps = ((prices[-1] - prices[0]) / prices[0]) * 10000

    in_position = False
    entry_price = None
    entry_time = None
    trades = []
    equity = 1.0
    equity_curve = [equity]

    for i in range(SLOW_WINDOW, len(prices)):
        fast = statistics.mean(prices[i - FAST_WINDOW + 1:i + 1])
        slow = statistics.mean(prices[i - SLOW_WINDOW + 1:i + 1])
        price = prices[i]

        if not in_position and fast > slow:
            in_position = True
            entry_price = price * (1 + SLIPPAGE_BPS / 10000)
            entry_time = times[i]

        elif in_position and fast < slow:
            exit_price = price * (1 - SLIPPAGE_BPS / 10000)
            gross = (exit_price - entry_price) / entry_price
            net = gross - ((FEE_BPS * 2) / 10000)
            equity *= (1 + net)
            equity_curve.append(equity)

            trades.append({
                "entry_time_ms": entry_time,
                "exit_time_ms": times[i],
                "entry_price": round(entry_price, 8),
                "exit_price": round(exit_price, 8),
                "net_return_bps": round(net * 10000, 4),
            })

            in_position = False
            entry_price = None
            entry_time = None

    if in_position and entry_price:
        exit_price = prices[-1] * (1 - SLIPPAGE_BPS / 10000)
        gross = (exit_price - entry_price) / entry_price
        net = gross - ((FEE_BPS * 2) / 10000)
        equity *= (1 + net)
        equity_curve.append(equity)

        trades.append({
            "entry_time_ms": entry_time,
            "exit_time_ms": times[-1],
            "entry_price": round(entry_price, 8),
            "exit_price": round(exit_price, 8),
            "net_return_bps": round(net * 10000, 4),
        })

    wins = [t["net_return_bps"] for t in trades if t["net_return_bps"] > 0]
    losses = [t["net_return_bps"] for t in trades if t["net_return_bps"] <= 0]

    gross_profit = sum(wins)
    gross_loss = abs(sum(losses))
    profit_factor = round(gross_profit / gross_loss, 4) if gross_loss > 0 else None

    net_return_bps = round((equity - 1) * 10000, 4)
    win_rate_pct = round((len(wins) / len(trades)) * 100, 2) if trades else 0.0

    return {
        "status": "backtest_complete",
        "price_points": len(prices),
        "trade_count": len(trades),
        "winning_trades": len(wins),
        "losing_trades": len(losses),
        "net_return_bps": net_return_bps,
        "buy_hold_return_bps": round(buy_hold_return_bps, 4),
        "win_rate_pct": win_rate_pct,
        "profit_factor": profit_factor,
        "max_drawdown_pct": max_drawdown(equity_curve),
        "fee_bps": FEE_BPS,
        "slippage_bps": SLIPPAGE_BPS,
        "fast_window": FAST_WINDOW,
        "slow_window": SLOW_WINDOW,
        "sample_trades": trades[:20],
    }

flags = {
    "BINANCE_TESTNET": os.getenv("BINANCE_TESTNET", ""),
    "BINANCE_USE_TESTNET": os.getenv("BINANCE_USE_TESTNET", ""),
    "BINANCE_ENABLE_LIVE_TRADING": os.getenv("BINANCE_ENABLE_LIVE_TRADING", ""),
    "LIVE_TRADING_ALLOWED": os.getenv("LIVE_TRADING_ALLOWED", ""),
}

safe_mode = flags["BINANCE_ENABLE_LIVE_TRADING"] == "false" and flags["LIVE_TRADING_ALLOWED"] == "false"

RESULTS_DIR.mkdir(parents=True, exist_ok=True)

datasets = sorted(DATASET_DIR.glob("*_phase17_backtest_dataset.jsonl"))
results = {}

for dataset in datasets:
    symbol = dataset.name.split("_phase17_")[0].upper()
    points = load_dataset(dataset)
    result = run_backtest(points)

    result_path = RESULTS_DIR / f"{symbol.lower()}_phase17_baseline_backtest_result.json"
    result_path.write_text(json.dumps(result, indent=2))

    results[symbol] = {
        "dataset_path": str(dataset),
        "result_path": str(result_path),
        **result,
    }

symbols_backtested = [s for s, r in results.items() if r["status"] == "backtest_complete"]
symbols_insufficient = [s for s, r in results.items() if r["status"] != "backtest_complete"]

report = {
    "phase": "phase_17_4_baseline_historical_backtest_runner",
    "generated_at_unix": int(time.time()),
    "scope": "baseline_historical_backtest_runner_only",
    "safety_flags": flags,
    "safe_mode_active": safe_mode,
    "git_working_tree_clean": git_clean(),
    "dataset_count": len(datasets),
    "symbols_backtested": symbols_backtested,
    "symbols_insufficient": symbols_insufficient,
    "results": results,
    "approved_for_micro_live_execution": False,
    "approved_for_real_live_trading": False,
    "decision": "BASELINE_HISTORICAL_BACKTEST_COMPLETE_REVIEW_REQUIRED_NOT_APPROVED_FOR_EXECUTION",
    "next_phase": "Phase 17.5 — Backtest Results Review and Strategy Quality Gate",
    "safety_notes": [
        "This phase runs local historical backtests only.",
        "This phase does not approve live trading.",
        "This phase does not submit Binance orders.",
        "Backtest results require review before any strategy approval.",
    ],
}

OUT.write_text(json.dumps(report, indent=2))

print(f"Report written to: {OUT}")
print(f"safe_mode_active={safe_mode}")
print(f"dataset_count={len(datasets)}")
print(f"symbols_backtested={','.join(symbols_backtested) if symbols_backtested else 'none'}")
print(f"symbols_insufficient={','.join(symbols_insufficient) if symbols_insufficient else 'none'}")
print("approved_for_micro_live_execution=False")
print("approved_for_real_live_trading=False")
print(f"decision={report['decision']}")
