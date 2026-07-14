import json, os, subprocess, time
from pathlib import Path

OUT = Path("data/processed/phase17_parameter_sweep_results_review_candidate_selection.json")
SWEEP_REPORT = Path("data/processed/phase17_parameter_sweep_backtest_runner.json")
SWEEP_RESULTS = Path("data/processed/backtest_results/phase17_parameter_sweep_results.jsonl")

TOP_N_PER_SYMBOL = 5
TOP_N_GLOBAL = 10

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

def load_jsonl(path):
    rows = []
    if not path.exists():
        return rows

    with path.open("r", errors="ignore") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except Exception:
                continue

    return rows

def safe_score(row):
    try:
        return float(row.get("score", -999999))
    except Exception:
        return -999999

def quality_reason(row):
    reasons = []

    if row.get("trade_count", 0) < 30:
        reasons.append("trade_count_below_30")

    if row.get("net_return_bps", 0) <= 0:
        reasons.append("net_return_not_positive")

    pf = row.get("profit_factor")
    if pf is None or pf < 1.2:
        reasons.append("profit_factor_below_1_20")

    if row.get("win_rate_pct", 0) < 45:
        reasons.append("win_rate_below_45_pct")

    if row.get("max_drawdown_pct", 999) > 20:
        reasons.append("drawdown_above_20_pct")

    return reasons

flags = {
    "BINANCE_TESTNET": os.getenv("BINANCE_TESTNET", ""),
    "BINANCE_USE_TESTNET": os.getenv("BINANCE_USE_TESTNET", ""),
    "BINANCE_ENABLE_LIVE_TRADING": os.getenv("BINANCE_ENABLE_LIVE_TRADING", ""),
    "LIVE_TRADING_ALLOWED": os.getenv("LIVE_TRADING_ALLOWED", ""),
}

safe_mode = flags["BINANCE_ENABLE_LIVE_TRADING"] == "false" and flags["LIVE_TRADING_ALLOWED"] == "false"

sweep_report = load_json(SWEEP_REPORT)
rows = load_jsonl(SWEEP_RESULTS)

complete_rows = [r for r in rows if r.get("status") == "sweep_backtest_complete"]
candidate_rows = [r for r in complete_rows if r.get("quality_gate_candidate") is True]
failed_rows = [r for r in complete_rows if r.get("quality_gate_candidate") is not True]

symbols = sorted(set(r.get("symbol", "UNKNOWN") for r in complete_rows))

per_symbol_review = {}
selected_candidates = []

for symbol in symbols:
    symbol_rows = [r for r in complete_rows if r.get("symbol") == symbol]
    symbol_candidates = [r for r in candidate_rows if r.get("symbol") == symbol]
    symbol_failed = [r for r in failed_rows if r.get("symbol") == symbol]

    top_candidates = sorted(symbol_candidates, key=safe_score, reverse=True)[:TOP_N_PER_SYMBOL]
    top_overall = sorted(symbol_rows, key=safe_score, reverse=True)[:TOP_N_PER_SYMBOL]

    selected_candidates.extend(top_candidates[:2])

    per_symbol_review[symbol] = {
        "total_complete_results": len(symbol_rows),
        "quality_gate_candidate_count": len(symbol_candidates),
        "failed_result_count": len(symbol_failed),
        "top_quality_gate_candidates": top_candidates,
        "top_overall_results": top_overall,
        "best_result_rejection_reasons": quality_reason(top_overall[0]) if top_overall else [],
    }

selected_candidates = sorted(selected_candidates, key=safe_score, reverse=True)[:TOP_N_GLOBAL]
top_global = sorted(complete_rows, key=safe_score, reverse=True)[:TOP_N_GLOBAL]

if selected_candidates:
    decision = "PARAMETER_SWEEP_REVIEW_COMPLETE_CANDIDATES_SELECTED_OOS_VALIDATION_REQUIRED_NOT_APPROVED_FOR_EXECUTION"
    next_phase = "Phase 17.9 — Out-of-Sample Validation Dataset Split"
else:
    decision = "PARAMETER_SWEEP_REVIEW_COMPLETE_NO_APPROVED_CANDIDATES_STRATEGY_REWORK_REQUIRED"
    next_phase = "Phase 17.9 — Out-of-Sample Validation Dataset Split or Strategy Redesign"

report = {
    "phase": "phase_17_8_parameter_sweep_results_review_candidate_selection",
    "generated_at_unix": int(time.time()),
    "scope": "parameter_sweep_results_review_and_candidate_selection_only",
    "safety_flags": flags,
    "safe_mode_active": safe_mode,
    "git_working_tree_clean": git_clean(),
    "sweep_report_present": SWEEP_REPORT.exists(),
    "sweep_results_present": SWEEP_RESULTS.exists(),
    "total_sweep_rows": len(rows),
    "complete_result_count": len(complete_rows),
    "quality_gate_candidate_count": len(candidate_rows),
    "symbols_reviewed": symbols,
    "per_symbol_review": per_symbol_review,
    "selected_candidates": selected_candidates,
    "top_global_results": top_global,
    "approved_for_micro_live_execution": False,
    "approved_for_real_live_trading": False,
    "decision": decision,
    "next_phase": next_phase,
    "safety_notes": [
        "This phase reviews parameter sweep results only.",
        "Selected candidates are not approved for live trading.",
        "Selected candidates require out-of-sample validation.",
        "This phase does not submit Binance orders.",
        "Live trading flags must remain disabled."
    ],
}

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(report, indent=2))

print(f"Report written to: {OUT}")
print(f"safe_mode_active={safe_mode}")
print(f"total_sweep_rows={len(rows)}")
print(f"complete_result_count={len(complete_rows)}")
print(f"quality_gate_candidate_count={len(candidate_rows)}")
print(f"selected_candidate_count={len(selected_candidates)}")
print("approved_for_micro_live_execution=False")
print("approved_for_real_live_trading=False")
print(f"decision={decision}")
