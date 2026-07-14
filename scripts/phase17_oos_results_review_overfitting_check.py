import json, os, subprocess, time
from pathlib import Path

OUT = Path("data/processed/phase17_oos_results_review_overfitting_check.json")
OOS_INPUT = Path("data/processed/phase17_out_of_sample_candidate_validation_runner.json")
CANDIDATE_INPUT = Path("data/processed/phase17_parameter_sweep_results_review_candidate_selection.json")

MIN_TEST_PROFIT_FACTOR = 1.10
MIN_TEST_WIN_RATE = 40.0
MAX_TEST_DRAWDOWN_PCT = 25.0
MIN_TEST_TRADES = 5
MIN_TEST_NET_RETURN_BPS = 0.0
MAX_NET_RETURN_DEGRADATION_RATIO = 0.70

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

def num(v, default=0.0):
    try:
        if v is None:
            return default
        return float(v)
    except Exception:
        return default

def params_key(symbol, params):
    return (
        str(symbol).upper(),
        int(params.get("fast_window", 0) or 0),
        int(params.get("slow_window", 0) or 0),
        str(params.get("trend_filter", "")),
        str(params.get("risk_filter", "")),
        float(params.get("fee_bps", 0) or 0),
        float(params.get("slippage_bps", 0) or 0),
    )

flags = {
    "BINANCE_TESTNET": os.getenv("BINANCE_TESTNET", ""),
    "BINANCE_USE_TESTNET": os.getenv("BINANCE_USE_TESTNET", ""),
    "BINANCE_ENABLE_LIVE_TRADING": os.getenv("BINANCE_ENABLE_LIVE_TRADING", ""),
    "LIVE_TRADING_ALLOWED": os.getenv("LIVE_TRADING_ALLOWED", ""),
}

safe_mode = flags["BINANCE_ENABLE_LIVE_TRADING"] == "false" and flags["LIVE_TRADING_ALLOWED"] == "false"

oos_report = load_json(OOS_INPUT)
candidate_report = load_json(CANDIDATE_INPUT)

selected_candidates = candidate_report.get("selected_candidates", [])
candidate_results = oos_report.get("passed_candidates", []) + oos_report.get("failed_candidates", [])

insample_map = {}
for c in selected_candidates:
    key = params_key(c.get("symbol"), c)
    insample_map[key] = c

reviews = []
forward_candidates = []
rejected_candidates = []

for result in candidate_results:
    symbol = result.get("symbol", "")
    params = result.get("candidate_parameters", {})
    key = params_key(symbol, params)
    insample = insample_map.get(key, {})

    validation = result.get("validation_result", {})
    test = result.get("test_result", {})

    insample_net = num(insample.get("net_return_bps"))
    validation_net = num(validation.get("net_return_bps"))
    test_net = num(test.get("net_return_bps"))

    test_profit_factor = test.get("profit_factor")
    test_win_rate = num(test.get("win_rate_pct"))
    test_drawdown = num(test.get("max_drawdown_pct"), 999)
    test_trades = int(test.get("trade_count", 0) or 0)

    checks = {
        "test_net_return_positive": test_net > MIN_TEST_NET_RETURN_BPS,
        "test_profit_factor_acceptable": test_profit_factor is not None and num(test_profit_factor) >= MIN_TEST_PROFIT_FACTOR,
        "test_win_rate_acceptable": test_win_rate >= MIN_TEST_WIN_RATE,
        "test_drawdown_acceptable": test_drawdown <= MAX_TEST_DRAWDOWN_PCT,
        "test_trade_count_acceptable": test_trades >= MIN_TEST_TRADES,
        "validation_and_test_same_direction": validation_net > 0 and test_net > 0,
    }

    degradation_ratio = None
    if insample_net > 0:
        degradation_ratio = round((insample_net - test_net) / insample_net, 4)
        checks["insample_to_test_degradation_acceptable"] = degradation_ratio <= MAX_NET_RETURN_DEGRADATION_RATIO
    else:
        checks["insample_to_test_degradation_acceptable"] = False

    overfitting_flags = []
    if not checks["test_net_return_positive"]:
        overfitting_flags.append("test_net_return_not_positive")
    if not checks["test_profit_factor_acceptable"]:
        overfitting_flags.append("test_profit_factor_too_low")
    if not checks["test_win_rate_acceptable"]:
        overfitting_flags.append("test_win_rate_too_low")
    if not checks["test_drawdown_acceptable"]:
        overfitting_flags.append("test_drawdown_too_high")
    if not checks["test_trade_count_acceptable"]:
        overfitting_flags.append("test_trade_count_too_low")
    if not checks["validation_and_test_same_direction"]:
        overfitting_flags.append("validation_test_direction_mismatch")
    if not checks["insample_to_test_degradation_acceptable"]:
        overfitting_flags.append("insample_to_test_degradation_too_large")

    passed_review = all(checks.values())

    review = {
        "candidate_id": result.get("candidate_id"),
        "symbol": symbol,
        "candidate_parameters": params,
        "insample_summary": {
            "net_return_bps": insample_net,
            "profit_factor": insample.get("profit_factor"),
            "win_rate_pct": insample.get("win_rate_pct"),
            "max_drawdown_pct": insample.get("max_drawdown_pct"),
            "trade_count": insample.get("trade_count"),
        },
        "validation_summary": {
            "net_return_bps": validation_net,
            "profit_factor": validation.get("profit_factor"),
            "win_rate_pct": validation.get("win_rate_pct"),
            "max_drawdown_pct": validation.get("max_drawdown_pct"),
            "trade_count": validation.get("trade_count"),
        },
        "test_summary": {
            "net_return_bps": test_net,
            "profit_factor": test_profit_factor,
            "win_rate_pct": test_win_rate,
            "max_drawdown_pct": test_drawdown,
            "trade_count": test_trades,
        },
        "degradation_ratio": degradation_ratio,
        "checks": checks,
        "overfitting_flags": overfitting_flags,
        "oos_review_passed": passed_review,
    }

    reviews.append(review)

    if passed_review:
        forward_candidates.append(review)
    else:
        rejected_candidates.append(review)

if forward_candidates:
    decision = "OOS_REVIEW_COMPLETE_CANDIDATES_FORWARD_WALK_FORWARD_REQUIRED_NOT_APPROVED_FOR_EXECUTION"
    next_phase = "Phase 17.12 — Walk-Forward Validation Runner"
elif reviews:
    decision = "OOS_REVIEW_COMPLETE_OVERFITTING_OR_WEAK_OOS_DETECTED_STRATEGY_REWORK_REQUIRED_NOT_APPROVED_FOR_EXECUTION"
    next_phase = "Phase 17.12 — Walk-Forward Validation Runner or Strategy Redesign"
else:
    decision = "OOS_REVIEW_COMPLETE_NO_CANDIDATES_AVAILABLE_STRATEGY_REWORK_REQUIRED_NOT_APPROVED_FOR_EXECUTION"
    next_phase = "Phase 17.12 — Walk-Forward Validation Runner or Strategy Redesign"

report = {
    "phase": "phase_17_11_oos_results_review_overfitting_check",
    "generated_at_unix": int(time.time()),
    "scope": "oos_results_review_and_overfitting_check_only",
    "safety_flags": flags,
    "safe_mode_active": safe_mode,
    "git_working_tree_clean": git_clean(),
    "oos_input_present": OOS_INPUT.exists(),
    "candidate_input_present": CANDIDATE_INPUT.exists(),
    "reviewed_candidate_count": len(reviews),
    "forward_candidate_count": len(forward_candidates),
    "rejected_candidate_count": len(rejected_candidates),
    "thresholds": {
        "min_test_profit_factor": MIN_TEST_PROFIT_FACTOR,
        "min_test_win_rate_pct": MIN_TEST_WIN_RATE,
        "max_test_drawdown_pct": MAX_TEST_DRAWDOWN_PCT,
        "min_test_trades": MIN_TEST_TRADES,
        "max_net_return_degradation_ratio": MAX_NET_RETURN_DEGRADATION_RATIO,
    },
    "forward_candidates": forward_candidates,
    "rejected_candidates": rejected_candidates,
    "approved_for_micro_live_execution": False,
    "approved_for_real_live_trading": False,
    "decision": decision,
    "next_phase": next_phase,
    "safety_notes": [
        "This phase reviews out-of-sample validation results only.",
        "This phase checks for overfitting and weak test performance.",
        "This phase does not approve live trading.",
        "This phase does not approve micro-live execution.",
        "This phase does not submit Binance orders."
    ],
}

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(report, indent=2))

print(f"Report written to: {OUT}")
print(f"safe_mode_active={safe_mode}")
print(f"reviewed_candidate_count={len(reviews)}")
print(f"forward_candidate_count={len(forward_candidates)}")
print(f"rejected_candidate_count={len(rejected_candidates)}")
print("approved_for_micro_live_execution=False")
print("approved_for_real_live_trading=False")
print(f"decision={decision}")
