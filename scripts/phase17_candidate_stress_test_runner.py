import json, os, subprocess, time, statistics
from pathlib import Path

OUT = Path("data/processed/phase17_candidate_stress_test_runner.json")
PLAN_INPUT = Path("data/processed/phase17_candidate_risk_sizing_stress_test_plan.json")
DATASET_DIR = Path("data/processed/backtest_datasets")
RESULTS_DIR = Path("data/processed/stress_test_results")

MIN_TRADES = 3
MAX_STRESS_DRAWDOWN_PCT = 35.0
MIN_PASSING_SCENARIO_RATIO = 0.60

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

def fill_index(i, latency_bars, max_index):
    return min(i + latency_bars, max_index)

def run_stress_backtest(points, params, scenario):
    fast = int(params.get("fast_window", 5) or 5)
    slow = int(params.get("slow_window", 20) or 20)
    trend_filter = params.get("trend_filter", "none")
    risk_filter = params.get("risk_filter", "fixed_exit")

    fee_bps = float(scenario.get("fee_bps", params.get("fee_bps", 4)) or 4)
    slippage_bps = float(scenario.get("slippage_bps", params.get("slippage_bps", 2)) or 2)
    latency_ms = int(scenario.get("latency_ms", 0) or 0)
    latency_bars = min(5, max(0, latency_ms // 500))

    prices = [p["price"] for p in points]

    if len(prices) < slow + 10:
        return {
            "status": "insufficient_stress_points",
            "price_points": len(prices),
            "trade_count": 0,
            "net_return_bps": 0.0,
            "win_rate_pct": 0.0,
            "profit_factor": None,
            "max_drawdown_pct": 0.0,
            "scenario_passed": False
        }

    in_position = False
    entry_price = None
    entry_index = None
    trades = []
    equity = 1.0
    equity_curve = [equity]

    max_i = len(prices) - 1

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
                fi = fill_index(i, latency_bars, max_i)
                entry_price = prices[fi] * (1 + slippage_bps / 10000)
                entry_index = fi
                in_position = True

        else:
            if bearish_cross or risk_exit(risk_filter, prices, i, entry_price, entry_index):
                fi = fill_index(i, latency_bars, max_i)
                exit_price = prices[fi] * (1 - slippage_bps / 10000)
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

    scenario_passed = (
        len(trades) >= MIN_TRADES
        and net_return > 0
        and dd <= MAX_STRESS_DRAWDOWN_PCT
    )

    return {
        "status": "stress_test_complete",
        "price_points": len(prices),
        "trade_count": len(trades),
        "winning_trades": len(wins),
        "losing_trades": len(losses),
        "net_return_bps": net_return,
        "win_rate_pct": win_rate,
        "profit_factor": profit_factor,
        "max_drawdown_pct": dd,
        "scenario_passed": scenario_passed,
        "sample_returns_bps": trades[:20]
    }

flags = {
    "BINANCE_TESTNET": os.getenv("BINANCE_TESTNET", ""),
    "BINANCE_USE_TESTNET": os.getenv("BINANCE_USE_TESTNET", ""),
    "BINANCE_ENABLE_LIVE_TRADING": os.getenv("BINANCE_ENABLE_LIVE_TRADING", ""),
    "LIVE_TRADING_ALLOWED": os.getenv("LIVE_TRADING_ALLOWED", ""),
}

safe_mode = flags["BINANCE_ENABLE_LIVE_TRADING"] == "false" and flags["LIVE_TRADING_ALLOWED"] == "false"

plan_report = load_json(PLAN_INPUT)
risk_plans = plan_report.get("risk_plans", [])

RESULTS_DIR.mkdir(parents=True, exist_ok=True)

candidate_results = []
passed_candidates = []
failed_candidates = []

for plan in risk_plans:
    candidate_id = plan.get("candidate_id", "unknown_candidate")
    symbol = str(plan.get("symbol", "")).upper()
    params = plan.get("candidate_parameters", {})
    scenarios = plan.get("stress_test_scenarios", [])

    dataset_path = DATASET_DIR / f"{symbol.lower()}_phase17_backtest_dataset.jsonl"
    points = load_points(dataset_path)

    scenario_results = []

    for scenario in scenarios:
        result = run_stress_backtest(points, params, scenario)
        scenario_results.append({
            "scenario": scenario,
            "result": result,
        })

    passed_scenarios = [r for r in scenario_results if r["result"].get("scenario_passed") is True]
    passing_ratio = round(len(passed_scenarios) / len(scenario_results), 4) if scenario_results else 0.0

    candidate_passed = (
        len(scenario_results) > 0
        and passing_ratio >= MIN_PASSING_SCENARIO_RATIO
    )

    candidate_result = {
        "candidate_id": candidate_id,
        "symbol": symbol,
        "dataset": str(dataset_path),
        "candidate_parameters": params,
        "scenario_count": len(scenario_results),
        "passed_scenario_count": len(passed_scenarios),
        "passing_scenario_ratio": passing_ratio,
        "candidate_stress_test_passed": candidate_passed,
        "scenario_results": scenario_results,
        "approved_for_micro_live_execution": False,
        "approved_for_real_live_trading": False,
    }

    result_path = RESULTS_DIR / f"{candidate_id.lower()}_stress_test_result.json"
    result_path.write_text(json.dumps(candidate_result, indent=2))
    candidate_result["result_path"] = str(result_path)

    candidate_results.append(candidate_result)

    if candidate_passed:
        passed_candidates.append(candidate_result)
    else:
        failed_candidates.append(candidate_result)

if passed_candidates:
    decision = "CANDIDATE_STRESS_TEST_COMPLETE_CANDIDATES_REQUIRE_REVIEW_NOT_APPROVED_FOR_EXECUTION"
    next_phase = "Phase 17.16 — Stress Test Results Review"
elif candidate_results:
    decision = "CANDIDATE_STRESS_TEST_FAILED_STRATEGY_REWORK_REQUIRED_NOT_APPROVED_FOR_EXECUTION"
    next_phase = "Phase 17.16 — Stress Test Results Review or Strategy Redesign"
else:
    decision = "CANDIDATE_STRESS_TEST_SKIPPED_NO_RISK_PLANS_STRATEGY_REWORK_REQUIRED_NOT_APPROVED_FOR_EXECUTION"
    next_phase = "Phase 17.16 — Stress Test Results Review or Strategy Redesign"

report = {
    "phase": "phase_17_15_candidate_stress_test_runner",
    "generated_at_unix": int(time.time()),
    "scope": "candidate_stress_test_runner_only",
    "safety_flags": flags,
    "safe_mode_active": safe_mode,
    "git_working_tree_clean": git_clean(),
    "plan_input_present": PLAN_INPUT.exists(),
    "risk_plan_count": len(risk_plans),
    "tested_candidate_count": len(candidate_results),
    "passed_candidate_count": len(passed_candidates),
    "failed_candidate_count": len(failed_candidates),
    "thresholds": {
        "min_trades": MIN_TRADES,
        "max_stress_drawdown_pct": MAX_STRESS_DRAWDOWN_PCT,
        "min_passing_scenario_ratio": MIN_PASSING_SCENARIO_RATIO
    },
    "passed_candidates": passed_candidates,
    "failed_candidates": failed_candidates,
    "approved_for_micro_live_execution": False,
    "approved_for_real_live_trading": False,
    "decision": decision,
    "next_phase": next_phase,
    "safety_notes": [
        "This phase performs candidate stress tests only.",
        "This phase does not approve live trading.",
        "This phase does not approve micro-live execution.",
        "This phase does not submit Binance orders.",
        "Stress-test candidates require separate review before any future execution gate."
    ],
}

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(report, indent=2))

print(f"Report written to: {OUT}")
print(f"safe_mode_active={safe_mode}")
print(f"risk_plan_count={len(risk_plans)}")
print(f"tested_candidate_count={len(candidate_results)}")
print(f"passed_candidate_count={len(passed_candidates)}")
print(f"failed_candidate_count={len(failed_candidates)}")
print("approved_for_micro_live_execution=False")
print("approved_for_real_live_trading=False")
print(f"decision={decision}")
