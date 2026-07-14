import json, os, subprocess, time, statistics
from pathlib import Path

OUT = Path("data/processed/phase17_parameter_sweep_backtest_runner.json")
RESULTS_JSONL = Path("data/processed/backtest_results/phase17_parameter_sweep_results.jsonl")
DATASET_DIR = Path("data/processed/backtest_datasets")
DESIGN_INPUT = Path("data/processed/phase17_strategy_rework_parameter_sweep_design.json")

MIN_PROFIT_FACTOR = 1.20
MIN_WIN_RATE = 45.0
MAX_DRAWDOWN_PCT = 20.0
MIN_TRADES = 30
MIN_NET_RETURN_BPS = 0.0

def run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True)

def git_clean():
    return run(["git", "status", "--short"]).stdout.strip() == ""

def load_json(path):
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except Exception:
        return {}

def to_float(v):
    try:
        if v is None:
            return None
        return float(v)
    except Exception:
        return None

def extract_time(row):
    for key in ["event_time_ms", "received_time_ms", "time_ms", "timestamp_ms", "start_time_ms", "end_time_ms", "t", "T"]:
        v = row.get(key)
        if isinstance(v, int):
            return v
        if isinstance(v, str) and v.isdigit():
            return int(v)
    return 0

def extract_price(row):
    keys = [
        "price", "p", "close", "c", "last_price", "mark_price",
        "mid_price", "vwap", "avwap", "anchored_vwap", "anchor_vwap",
        "best_bid", "best_ask", "bid_price", "ask_price"
    ]

    for key in keys:
        v = to_float(row.get(key))
        if v and v > 0:
            return v

    bid = to_float(row.get("best_bid") or row.get("bid_price"))
    ask = to_float(row.get("best_ask") or row.get("ask_price"))
    if bid and ask and bid > 0 and ask > 0:
        return (bid + ask) / 2

    return None

def load_dataset(path):
    points = []
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
                    points.append({
                        "time_ms": extract_time(row),
                        "price": price
                    })
    except Exception:
        return []

    points.sort(key=lambda x: x["time_ms"])
    return points

def max_drawdown(equity_curve):
    if not equity_curve:
        return 0.0

    peak = equity_curve[0]
    max_dd = 0.0

    for value in equity_curve:
        peak = max(peak, value)
        if peak > 0:
            max_dd = max(max_dd, (peak - value) / peak)

    return round(max_dd * 100, 4)

def moving_average(values, end_index, window):
    if end_index - window + 1 < 0:
        return None
    return statistics.mean(values[end_index - window + 1:end_index + 1])

def apply_trend_filter(name, prices, i, slow_ma):
    price = prices[i]

    if name == "none":
        return True

    if name == "price_above_slow_ma":
        return slow_ma is not None and price > slow_ma

    if name == "higher_high_higher_low":
        if i < 4:
            return False
        return prices[i] > prices[i - 1] > prices[i - 2] and prices[i - 2] > prices[i - 3]

    if name == "positive_momentum_only":
        if i < 5:
            return False
        return prices[i] > prices[i - 5]

    return True

def should_exit_by_risk_filter(name, prices, i, entry_price, entry_index):
    price = prices[i]

    if name == "fixed_exit":
        if entry_price and price <= entry_price * 0.995:
            return True
        if entry_price and price >= entry_price * 1.005:
            return True

    if name == "atr_stop":
        if i < 15:
            return False
        recent = prices[i - 14:i + 1]
        avg_range = statistics.mean(abs(recent[j] - recent[j - 1]) for j in range(1, len(recent)))
        stop = entry_price - (avg_range * 3)
        if price <= stop:
            return True

    if name == "trailing_stop":
        if i <= entry_index:
            return False
        high_since_entry = max(prices[entry_index:i + 1])
        if price <= high_since_entry * 0.997:
            return True

    if name == "time_based_exit":
        if i - entry_index >= 80:
            return True

    return False

def run_backtest(points, fast_window, slow_window, trend_filter, risk_filter, fee_bps, slippage_bps):
    prices = [p["price"] for p in points]
    times = [p["time_ms"] for p in points]

    if len(prices) < slow_window + 10:
        return {
            "status": "insufficient_price_points",
            "price_points": len(prices),
            "trade_count": 0,
            "net_return_bps": 0.0,
            "win_rate_pct": 0.0,
            "profit_factor": None,
            "max_drawdown_pct": 0.0,
        }

    in_position = False
    entry_price = None
    entry_time = None
    entry_index = None

    trades = []
    equity = 1.0
    equity_curve = [equity]

    for i in range(slow_window, len(prices)):
        fast = moving_average(prices, i, fast_window)
        slow = moving_average(prices, i, slow_window)
        prev_fast = moving_average(prices, i - 1, fast_window)
        prev_slow = moving_average(prices, i - 1, slow_window)

        if fast is None or slow is None or prev_fast is None or prev_slow is None:
            continue

        price = prices[i]
        bullish_cross = prev_fast <= prev_slow and fast > slow
        bearish_cross = prev_fast >= prev_slow and fast < slow

        if not in_position:
            if bullish_cross and apply_trend_filter(trend_filter, prices, i, slow):
                in_position = True
                entry_price = price * (1 + slippage_bps / 10000)
                entry_time = times[i]
                entry_index = i

        else:
            risk_exit = should_exit_by_risk_filter(risk_filter, prices, i, entry_price, entry_index)

            if bearish_cross or risk_exit:
                exit_price = price * (1 - slippage_bps / 10000)
                gross = (exit_price - entry_price) / entry_price
                net = gross - ((fee_bps * 2) / 10000)

                equity *= (1 + net)
                equity_curve.append(equity)

                trades.append(round(net * 10000, 4))

                in_position = False
                entry_price = None
                entry_time = None
                entry_index = None

    if in_position and entry_price:
        exit_price = prices[-1] * (1 - slippage_bps / 10000)
        gross = (exit_price - entry_price) / entry_price
        net = gross - ((fee_bps * 2) / 10000)
        equity *= (1 + net)
        equity_curve.append(equity)
        trades.append(round(net * 10000, 4))

    wins = [x for x in trades if x > 0]
    losses = [x for x in trades if x <= 0]

    gross_profit = sum(wins)
    gross_loss = abs(sum(losses))

    profit_factor = round(gross_profit / gross_loss, 4) if gross_loss > 0 else None
    win_rate = round((len(wins) / len(trades)) * 100, 2) if trades else 0.0
    net_return = round((equity - 1) * 10000, 4)
    dd = max_drawdown(equity_curve)

    gate_passed = (
        len(trades) >= MIN_TRADES
        and net_return > MIN_NET_RETURN_BPS
        and profit_factor is not None
        and profit_factor >= MIN_PROFIT_FACTOR
        and win_rate >= MIN_WIN_RATE
        and dd <= MAX_DRAWDOWN_PCT
    )

    score = net_return - (dd * 20)
    if profit_factor:
        score += profit_factor * 100
    score += win_rate

    return {
        "status": "sweep_backtest_complete",
        "price_points": len(prices),
        "trade_count": len(trades),
        "winning_trades": len(wins),
        "losing_trades": len(losses),
        "net_return_bps": net_return,
        "win_rate_pct": win_rate,
        "profit_factor": profit_factor,
        "max_drawdown_pct": dd,
        "quality_gate_candidate": gate_passed,
        "score": round(score, 4),
    }

design = load_json(DESIGN_INPUT)
grid = design.get("parameter_grid", {})

fast_windows = grid.get("fast_windows", [3, 5, 8, 10, 12])
slow_windows = grid.get("slow_windows", [20, 30, 50, 80, 100])
trend_filters = grid.get("trend_filters", ["none", "price_above_slow_ma", "higher_high_higher_low", "positive_momentum_only"])
risk_filters = grid.get("risk_filters", ["fixed_exit", "atr_stop", "trailing_stop", "time_based_exit"])
fee_bps_values = grid.get("fee_bps", [4])
slippage_bps_values = grid.get("slippage_bps", [2, 4, 6])

flags = {
    "BINANCE_TESTNET": os.getenv("BINANCE_TESTNET", ""),
    "BINANCE_USE_TESTNET": os.getenv("BINANCE_USE_TESTNET", ""),
    "BINANCE_ENABLE_LIVE_TRADING": os.getenv("BINANCE_ENABLE_LIVE_TRADING", ""),
    "LIVE_TRADING_ALLOWED": os.getenv("LIVE_TRADING_ALLOWED", ""),
}

safe_mode = flags["BINANCE_ENABLE_LIVE_TRADING"] == "false" and flags["LIVE_TRADING_ALLOWED"] == "false"

datasets = sorted(DATASET_DIR.glob("*_phase17_backtest_dataset.jsonl"))
RESULTS_JSONL.parent.mkdir(parents=True, exist_ok=True)

summary = {}
all_results = []

with RESULTS_JSONL.open("w") as out:
    for dataset in datasets:
        symbol = dataset.name.split("_phase17_")[0].upper()
        points = load_dataset(dataset)

        symbol_results = []

        for fast in fast_windows:
            for slow in slow_windows:
                if fast >= slow:
                    continue

                for trend_filter in trend_filters:
                    for risk_filter in risk_filters:
                        for fee_bps in fee_bps_values:
                            for slippage_bps in slippage_bps_values:
                                result = run_backtest(
                                    points,
                                    fast,
                                    slow,
                                    trend_filter,
                                    risk_filter,
                                    fee_bps,
                                    slippage_bps,
                                )

                                row = {
                                    "symbol": symbol,
                                    "dataset_path": str(dataset),
                                    "fast_window": fast,
                                    "slow_window": slow,
                                    "trend_filter": trend_filter,
                                    "risk_filter": risk_filter,
                                    "fee_bps": fee_bps,
                                    "slippage_bps": slippage_bps,
                                    **result,
                                }

                                out.write(json.dumps(row, separators=(",", ":")) + "\n")
                                symbol_results.append(row)
                                all_results.append(row)

        complete = [r for r in symbol_results if r["status"] == "sweep_backtest_complete"]
        candidates = [r for r in complete if r.get("quality_gate_candidate") is True]
        top = sorted(complete, key=lambda x: x.get("score", -999999), reverse=True)[:10]

        summary[symbol] = {
            "dataset_path": str(dataset),
            "price_points": len(points),
            "total_parameter_results": len(symbol_results),
            "complete_results": len(complete),
            "quality_gate_candidates": len(candidates),
            "best_result": top[0] if top else None,
            "top_results": top,
        }

candidate_count = sum(1 for r in all_results if r.get("quality_gate_candidate") is True)

report = {
    "phase": "phase_17_7_parameter_sweep_backtest_runner",
    "generated_at_unix": int(time.time()),
    "scope": "parameter_sweep_backtest_runner_only",
    "safety_flags": flags,
    "safe_mode_active": safe_mode,
    "git_working_tree_clean": git_clean(),
    "design_input_present": DESIGN_INPUT.exists(),
    "dataset_count": len(datasets),
    "results_jsonl": str(RESULTS_JSONL),
    "total_results": len(all_results),
    "quality_gate_candidate_count": candidate_count,
    "summary": summary,
    "approved_for_micro_live_execution": False,
    "approved_for_real_live_trading": False,
    "decision": "PARAMETER_SWEEP_BACKTEST_COMPLETE_REVIEW_REQUIRED_NOT_APPROVED_FOR_EXECUTION",
    "next_phase": "Phase 17.8 — Parameter Sweep Results Review and Candidate Selection",
    "safety_notes": [
        "This phase runs local parameter sweep backtests only.",
        "This phase does not approve live trading.",
        "This phase does not approve micro-live execution.",
        "This phase does not submit Binance orders.",
        "Any candidate result must be reviewed in a separate quality gate."
    ],
}

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(report, indent=2))

print(f"Report written to: {OUT}")
print(f"results_jsonl={RESULTS_JSONL}")
print(f"safe_mode_active={safe_mode}")
print(f"dataset_count={len(datasets)}")
print(f"total_results={len(all_results)}")
print(f"quality_gate_candidate_count={candidate_count}")
print("approved_for_micro_live_execution=False")
print("approved_for_real_live_trading=False")
print(f"decision={report['decision']}")
