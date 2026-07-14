import json, os, subprocess, time, statistics
from pathlib import Path

OUT = Path("data/processed/phase17_walk_forward_validation_runner.json")
OOS_REVIEW_INPUT = Path("data/processed/phase17_oos_results_review_overfitting_check.json")
DATASET_DIR = Path("data/processed/backtest_datasets")
RESULTS_DIR = Path("data/processed/walk_forward_results")

WINDOW_COUNT = 5
MIN_TRADES_PER_WINDOW = 3
MIN_PASSING_WINDOW_RATIO = 0.60
MIN_AVERAGE_NET_RETURN_BPS = 0.0
MAX_WORST_DRAWDOWN_PCT = 30.0

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
        return price <= stop

    if name == "trailing_stop":
        if i <= entry_index:
            return False
        high_since_entry = max(prices[entry_index:i + 1])
        return price <= high_since_entry * 0.997

    if name == "time_based_exit":
        return i - entry_index >= 80

    return False

def run_backtest(points, params):
    fast = int(params.get("fast_window", 5) or 5)
    slow = int(params.get("slow_window", 20) or 20)
    trend_filter = params.get("trend_filter", "none")
    risk_filter = params.get("risk_filter", "fixed_exit")
    fee_bps = float(params.get("fee_bps", 4) or 4)
    slippage_bps = float(params.get("slippage_bps", 2) or 2)

    prices = [p["price"] for p in points]

    if len(prices) < slow + 10:
        return {
            "status": "insufficient_walk_forward_points",
            "price_points": len(prices),
            "trade_count": 0,
            "net_return_bps": 0.0,
            "win_rate_pct": 0.0,
            "profit_factor": None,
            "max_drawdown_pct": 0.0,
            "window_passed": False
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
            if bearish_cross or risk_exit(risk_filter, prices, i, entry_price, entry_index):
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

    window_passed = len(trades) >= MIN_TRADES_PER_WINDOW and net_return > 0

    return {
        "status": "walk_forward_window_complete",
        "price_points": len(prices),
        "trade_count": len(trades),
        "winning_trades": len(wins),
        "losing_trades": len(losses),
        "net_return_bps": net_return,
        "win_rate_pct": win_rate,
        "profit_factor": profit_factor,
        "max_drawdown_pct": dd,
        "window_passed": window_passed,
        "sample_returns_bps": trades[:20]
    }

def split_windows(points, window_count):
    if not points:
        return []

    size = len(points) // window_count
    windows = []

    for i in range(window_count):
        start = i * size
        end = len(points) if i == window_count - 1 else (i + 1) * size
        windows.append(points[start:end])

    return windows

flags = {
    "BINANCE_TESTNET": os.getenv("BINANCE_TESTNET", ""),
    "BINANCE_USE_TESTNET": os.getenv("BINANCE_USE_TESTNET", ""),
    "BINANCE_ENABLE_LIVE_TRADING": os.getenv("BINANCE_ENABLE_LIVE_TRADING", ""),
    "LIVE_TRADING_ALLOWED": os.getenv("LIVE_TRADING_ALLOWED", ""),
}

safe_mode = flags["BINANCE_ENABLE_LIVE_TRADING"] == "false" and flags["LIVE_TRADING_ALLOWED"] == "false"

oos_review = load_json(OOS_REVIEW_INPUT)
forward_candidates = oos_review.get("forward_candidates", [])

RESULTS_DIR.mkdir(parents=True, exist_ok=True)

candidate_reviews = []
walk_forward_passed = []
walk_forward_failed = []

for idx, candidate in enumerate(forward_candidates, start=1):
    symbol = str(candidate.get("symbol", "")).upper()
    params = candidate.get("candidate_parameters", {})

    dataset = DATASET_DIR / f"{symbol.lower()}_phase17_backtest_dataset.jsonl"
    points = load_points(dataset)
    windows = split_windows(points, WINDOW_COUNT)

    window_results = []
    for window_index, window_points in enumerate(windows, start=1):
        result = run_backtest(window_points, params)
        result["window_index"] = window_index
        window_results.append(result)

    passing_windows = [r for r in window_results if r.get("window_passed") is True]
    net_returns = [float(r.get("net_return_bps", 0) or 0) for r in window_results]
    drawdowns = [float(r.get("max_drawdown_pct", 0) or 0) for r in window_results]

    passing_ratio = round(len(passing_windows) / len(window_results), 4) if window_results else 0.0
    average_net_return = round(sum(net_returns) / len(net_returns), 4) if net_returns else 0.0
    worst_drawdown = round(max(drawdowns), 4) if drawdowns else 0.0

    checks = {
        "enough_windows": len(window_results) == WINDOW_COUNT,
        "passing_window_ratio_ok": passing_ratio >= MIN_PASSING_WINDOW_RATIO,
        "average_net_return_positive": average_net_return > MIN_AVERAGE_NET_RETURN_BPS,
        "worst_drawdown_acceptable": worst_drawdown <= MAX_WORST_DRAWDOWN_PCT,
    }

    passed = all(checks.values())

    candidate_id = f"{symbol}_walk_forward_candidate_{idx}"

    review = {
        "candidate_id": candidate_id,
        "symbol": symbol,
        "dataset": str(dataset),
        "candidate_parameters": params,
        "window_count": len(window_results),
        "passing_window_count": len(passing_windows),
        "passing_window_ratio": passing_ratio,
        "average_net_return_bps": average_net_return,
        "worst_drawdown_pct": worst_drawdown,
        "checks": checks,
        "walk_forward_passed": passed,
        "window_results": window_results,
    }

    result_path = RESULTS_DIR / f"{candidate_id.lower()}_result.json"
    result_path.write_text(json.dumps(review, indent=2))
    review["result_path"] = str(result_path)

    candidate_reviews.append(review)

    if passed:
        walk_forward_passed.append(review)
    else:
        walk_forward_failed.append(review)

if walk_forward_passed:
    decision = "WALK_FORWARD_VALIDATION_COMPLETE_CANDIDATES_REQUIRE_FINAL_REVIEW_NOT_APPROVED_FOR_EXECUTION"
    next_phase = "Phase 17.13 — Final Strategy Candidate Review"
elif candidate_reviews:
    decision = "WALK_FORWARD_VALIDATION_FAILED_STRATEGY_REWORK_REQUIRED_NOT_APPROVED_FOR_EXECUTION"
    next_phase = "Phase 17.13 — Final Strategy Candidate Review or Strategy Redesign"
else:
    decision = "WALK_FORWARD_VALIDATION_SKIPPED_NO_FORWARD_CANDIDATES_STRATEGY_REWORK_REQUIRED_NOT_APPROVED_FOR_EXECUTION"
    next_phase = "Phase 17.13 — Final Strategy Candidate Review or Strategy Redesign"

report = {
    "phase": "phase_17_12_walk_forward_validation_runner",
    "generated_at_unix": int(time.time()),
    "scope": "walk_forward_validation_only",
    "safety_flags": flags,
    "safe_mode_active": safe_mode,
    "git_working_tree_clean": git_clean(),
    "oos_review_input_present": OOS_REVIEW_INPUT.exists(),
    "forward_candidate_count": len(forward_candidates),
    "tested_candidate_count": len(candidate_reviews),
    "walk_forward_passed_count": len(walk_forward_passed),
    "walk_forward_failed_count": len(walk_forward_failed),
    "thresholds": {
        "window_count": WINDOW_COUNT,
        "min_trades_per_window": MIN_TRADES_PER_WINDOW,
        "min_passing_window_ratio": MIN_PASSING_WINDOW_RATIO,
        "min_average_net_return_bps": MIN_AVERAGE_NET_RETURN_BPS,
        "max_worst_drawdown_pct": MAX_WORST_DRAWDOWN_PCT,
    },
    "walk_forward_passed_candidates": walk_forward_passed,
    "walk_forward_failed_candidates": walk_forward_failed,
    "approved_for_micro_live_execution": False,
    "approved_for_real_live_trading": False,
    "decision": decision,
    "next_phase": next_phase,
    "safety_notes": [
        "This phase performs walk-forward validation only.",
        "This phase does not approve live trading.",
        "This phase does not approve micro-live execution.",
        "This phase does not submit Binance orders.",
        "Any passing candidate still requires final review."
    ],
}

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(report, indent=2))

print(f"Report written to: {OUT}")
print(f"safe_mode_active={safe_mode}")
print(f"forward_candidate_count={len(forward_candidates)}")
print(f"tested_candidate_count={len(candidate_reviews)}")
print(f"walk_forward_passed_count={len(walk_forward_passed)}")
print(f"walk_forward_failed_count={len(walk_forward_failed)}")
print("approved_for_micro_live_execution=False")
print("approved_for_real_live_trading=False")
print(f"decision={decision}")
