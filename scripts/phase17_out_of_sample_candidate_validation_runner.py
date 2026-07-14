import json, os, subprocess, time, statistics
from pathlib import Path

OUT = Path("data/processed/phase17_out_of_sample_candidate_validation_runner.json")
CANDIDATES_INPUT = Path("data/processed/phase17_parameter_sweep_results_review_candidate_selection.json")
SPLIT_INPUT = Path("data/processed/phase17_out_of_sample_validation_dataset_split.json")
OOS_DIR = Path("data/processed/oos_datasets")
RESULTS_DIR = Path("data/processed/oos_results")

MIN_PROFIT_FACTOR = 1.20
MIN_WIN_RATE = 45.0
MAX_DRAWDOWN_PCT = 20.0
MIN_TRADES = 10
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

def load_points(path):
    points = []
    if not path.exists():
        return points

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

    points.sort(key=lambda x: x["time_ms"])
    return points

def moving_average(values, end_index, window):
    if end_index - window + 1 < 0:
        return None
    return statistics.mean(values[end_index - window + 1:end_index + 1])

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

def trend_ok(name, prices, i, slow_ma):
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

def risk_exit(name, prices, i, entry_price, entry_index):
    price = prices[i]

    if name == "fixed_exit":
        if price <= entry_price * 0.995:
            return True
        if price >= entry_price * 1.005:
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

def run_candidate_backtest(points, candidate):
    fast = int(candidate.get("fast_window", 5))
    slow = int(candidate.get("slow_window", 20))
    trend_filter = candidate.get("trend_filter", "none")
    risk_filter = candidate.get("risk_filter", "fixed_exit")
    fee_bps = float(candidate.get("fee_bps", 4))
    slippage_bps = float(candidate.get("slippage_bps", 2))

    prices = [p["price"] for p in points]
    times = [p["time_ms"] for p in points]

    if len(prices) < slow + 10:
        return {
            "status": "insufficient_oos_price_points",
            "price_points": len(prices),
            "trade_count": 0,
            "net_return_bps": 0.0,
            "win_rate_pct": 0.0,
            "profit_factor": None,
            "max_drawdown_pct": 0.0,
            "quality_gate_passed": False,
        }

    in_position = False
    entry_price = None
    entry_index = None
    trades = []
    equity = 1.0
    equity_curve = [equity]

    for i in range(slow, len(prices)):
        fast_ma = moving_average(prices, i, fast)
        slow_ma = moving_average(prices, i, slow)
        prev_fast = moving_average(prices, i - 1, fast)
        prev_slow = moving_average(prices, i - 1, slow)

        if fast_ma is None or slow_ma is None or prev_fast is None or prev_slow is None:
            continue

        price = prices[i]

        bullish_cross = prev_fast <= prev_slow and fast_ma > slow_ma
        bearish_cross = prev_fast >= prev_slow and fast_ma < slow_ma

        if not in_position:
            if bullish_cross and trend_ok(trend_filter, prices, i, slow_ma):
                in_position = True
                entry_price = price * (1 + slippage_bps / 10000)
                entry_index = i

        else:
            should_exit = bearish_cross or risk_exit(risk_filter, prices, i, entry_price, entry_index)

            if should_exit:
                exit_price = price * (1 - slippage_bps / 10000)
                gross = (exit_price - entry_price) / entry_price
                net = gross - ((fee_bps * 2) / 10000)

                equity *= (1 + net)
                equity_curve.append(equity)
                trades.append(round(net * 10000, 4))

                in_position = False
                entry_price = None
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

    return {
        "status": "oos_validation_complete",
        "price_points": len(prices),
        "trade_count": len(trades),
        "winning_trades": len(wins),
        "losing_trades": len(losses),
        "net_return_bps": net_return,
        "win_rate_pct": win_rate,
        "profit_factor": profit_factor,
        "max_drawdown_pct": dd,
        "quality_gate_passed": gate_passed,
        "sample_returns_bps": trades[:20],
    }

flags = {
    "BINANCE_TESTNET": os.getenv("BINANCE_TESTNET", ""),
    "BINANCE_USE_TESTNET": os.getenv("BINANCE_USE_TESTNET", ""),
    "BINANCE_ENABLE_LIVE_TRADING": os.getenv("BINANCE_ENABLE_LIVE_TRADING", ""),
    "LIVE_TRADING_ALLOWED": os.getenv("LIVE_TRADING_ALLOWED", ""),
}

safe_mode = flags["BINANCE_ENABLE_LIVE_TRADING"] == "false" and flags["LIVE_TRADING_ALLOWED"] == "false"

candidate_report = load_json(CANDIDATES_INPUT)
split_report = load_json(SPLIT_INPUT)

selected_candidates = candidate_report.get("selected_candidates", [])

RESULTS_DIR.mkdir(parents=True, exist_ok=True)

candidate_results = []
passed_candidates = []
failed_candidates = []

for idx, candidate in enumerate(selected_candidates, start=1):
    symbol = str(candidate.get("symbol", "")).upper()

    validation_path = OOS_DIR / f"{symbol.lower()}_validation_oos_phase17.jsonl"
    test_path = OOS_DIR / f"{symbol.lower()}_test_oos_phase17.jsonl"

    validation_points = load_points(validation_path)
    test_points = load_points(test_path)

    validation_result = run_candidate_backtest(validation_points, candidate)
    test_result = run_candidate_backtest(test_points, candidate)

    passed = (
        validation_result.get("quality_gate_passed") is True
        and test_result.get("quality_gate_passed") is True
    )

    candidate_id = f"{symbol}_candidate_{idx}"

    result = {
        "candidate_id": candidate_id,
        "symbol": symbol,
        "candidate_parameters": {
            "fast_window": candidate.get("fast_window"),
            "slow_window": candidate.get("slow_window"),
            "trend_filter": candidate.get("trend_filter"),
            "risk_filter": candidate.get("risk_filter"),
            "fee_bps": candidate.get("fee_bps"),
            "slippage_bps": candidate.get("slippage_bps"),
        },
        "validation_dataset": str(validation_path),
        "test_dataset": str(test_path),
        "validation_result": validation_result,
        "test_result": test_result,
        "oos_candidate_passed": passed,
    }

    result_path = RESULTS_DIR / f"{candidate_id.lower()}_oos_validation_result.json"
    result_path.write_text(json.dumps(result, indent=2))
    result["result_path"] = str(result_path)

    candidate_results.append(result)

    if passed:
        passed_candidates.append(result)
    else:
        failed_candidates.append(result)

if passed_candidates:
    decision = "OOS_CANDIDATE_VALIDATION_COMPLETE_CANDIDATES_REQUIRE_REVIEW_NOT_APPROVED_FOR_EXECUTION"
    next_phase = "Phase 17.11 — OOS Results Review and Overfitting Check"
else:
    decision = "OOS_CANDIDATE_VALIDATION_FAILED_STRATEGY_REWORK_REQUIRED_NOT_APPROVED_FOR_EXECUTION"
    next_phase = "Phase 17.11 — OOS Results Review and Overfitting Check"

report = {
    "phase": "phase_17_10_out_of_sample_candidate_validation_runner",
    "generated_at_unix": int(time.time()),
    "scope": "out_of_sample_candidate_validation_only",
    "safety_flags": flags,
    "safe_mode_active": safe_mode,
    "git_working_tree_clean": git_clean(),
    "candidate_input_present": CANDIDATES_INPUT.exists(),
    "split_input_present": SPLIT_INPUT.exists(),
    "selected_candidate_count": len(selected_candidates),
    "tested_candidate_count": len(candidate_results),
    "passed_candidate_count": len(passed_candidates),
    "failed_candidate_count": len(failed_candidates),
    "passed_candidates": passed_candidates,
    "failed_candidates": failed_candidates,
    "approved_for_micro_live_execution": False,
    "approved_for_real_live_trading": False,
    "decision": decision,
    "next_phase": next_phase,
    "safety_notes": [
        "This phase validates candidates on out-of-sample data only.",
        "This phase does not approve live trading.",
        "This phase does not approve micro-live execution.",
        "This phase does not submit Binance orders.",
        "Passing candidates still require review and overfitting checks."
    ],
}

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(report, indent=2))

print(f"Report written to: {OUT}")
print(f"safe_mode_active={safe_mode}")
print(f"selected_candidate_count={len(selected_candidates)}")
print(f"tested_candidate_count={len(candidate_results)}")
print(f"passed_candidate_count={len(passed_candidates)}")
print(f"failed_candidate_count={len(failed_candidates)}")
print("approved_for_micro_live_execution=False")
print("approved_for_real_live_trading=False")
print(f"decision={decision}")
