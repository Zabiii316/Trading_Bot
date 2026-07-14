import json, os, subprocess, time
from pathlib import Path

OUT = Path("data/processed/phase17_strategy_hardening_baseline.json")

INPUTS = {
    "phase16_release": "data/processed/phase16_final_documentation_repository_release.json",
    "phase16_readiness": "data/processed/phase16_final_micro_live_readiness_review.json",
    "operator_runbook": "data/processed/phase16_operator_runbook_human_approval_package.json",
}

def run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True)

def git_clean():
    return run(["git", "status", "--short"]).stdout.strip() == ""

def git_commit():
    r = run(["git", "rev-parse", "HEAD"])
    return r.stdout.strip() if r.returncode == 0 else ""

def tag_exists(tag):
    r = run(["git", "tag", "--list", tag])
    return r.stdout.strip() == tag

def load(path):
    p = Path(path)
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text())
    except Exception:
        return {}

flags = {
    "BINANCE_TESTNET": os.getenv("BINANCE_TESTNET", ""),
    "BINANCE_USE_TESTNET": os.getenv("BINANCE_USE_TESTNET", ""),
    "BINANCE_ENABLE_LIVE_TRADING": os.getenv("BINANCE_ENABLE_LIVE_TRADING", ""),
    "LIVE_TRADING_ALLOWED": os.getenv("LIVE_TRADING_ALLOWED", ""),
}

safe_mode = flags["BINANCE_ENABLE_LIVE_TRADING"] == "false" and flags["LIVE_TRADING_ALLOWED"] == "false"
present = {k: Path(v).exists() for k, v in INPUTS.items()}

phase16_release = load(INPUTS["phase16_release"])

hardening_plan = {
    "backtest_expansion": [
        "Run multi-day historical backtests.",
        "Add multi-market coverage: BTCUSDT, ETHUSDT, BNBUSDT.",
        "Test multiple volatility regimes.",
        "Include fees, slippage, spread, and latency assumptions.",
        "Track profit factor, max drawdown, win rate, expectancy, Sharpe-like score, and trade count."
    ],
    "strategy_validation": [
        "Separate in-sample and out-of-sample periods.",
        "Avoid overfitting to one testnet trade.",
        "Require enough trades before any future execution approval.",
        "Compare baseline rules against stricter filters.",
        "Document losing conditions and invalidation rules."
    ],
    "risk_hardening": [
        "Define approved capital limit.",
        "Define max single-order notional.",
        "Define daily and weekly loss limits.",
        "Define maximum drawdown stop.",
        "Define max consecutive-loss stop."
    ],
    "execution_hardening": [
        "Keep live trading disabled.",
        "Keep kill switch procedure available.",
        "Add dry-run execution validation before every test.",
        "Confirm order precision and quantity rounding rules.",
        "Confirm no production order is submitted during Phase 17."
    ]
}

checks = {
    "phase16_release_present": present["phase16_release"],
    "phase16_readiness_present": present["phase16_readiness"],
    "operator_runbook_present": present["operator_runbook"],
    "phase16_tag_present": tag_exists("phase16-controlled-testnet-review-v1"),
    "safe_mode_active": safe_mode,
    "git_working_tree_clean": git_clean(),
    "phase16_not_live_approved": phase16_release.get("approved_for_real_live_trading") is False,
}

report = {
    "phase": "phase_17_1_strategy_hardening_baseline",
    "generated_at_unix": int(time.time()),
    "scope": "strategy_hardening_backtest_expansion_planning_only",
    "git_commit": git_commit(),
    "safety_flags": flags,
    "inputs_present": present,
    "checks": checks,
    "hardening_plan": hardening_plan,
    "approved_for_micro_live_execution": False,
    "approved_for_real_live_trading": False,
    "decision": "PHASE_17_STRATEGY_HARDENING_BASELINE_CREATED_NOT_APPROVED_FOR_EXECUTION",
    "next_phase": "Phase 17.2 — Historical Data Coverage Audit",
}

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(report, indent=2))

print(f"Report written to: {OUT}")
print(f"safe_mode_active={safe_mode}")
print(f"phase16_tag_present={checks['phase16_tag_present']}")
print(f"git_working_tree_clean={checks['git_working_tree_clean']}")
print("approved_for_micro_live_execution=False")
print("approved_for_real_live_trading=False")
print(f"decision={report['decision']}")
