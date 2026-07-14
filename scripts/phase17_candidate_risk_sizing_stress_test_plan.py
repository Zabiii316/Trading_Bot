importmkdir -p scripts docs data/processed/r json, os, subprocess, time
from pathlib import Path

OUT = Path("data/processed/phase17_candidate_risk_sizing_stress_test_plan.json")
PLAN_DIR = Path("data/processed/risk_stress_plans")
CANDIDATE_REVIEW = Path("data/processed/phase17_final_strategy_candidate_review.json")

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

flags = {
    "BINANCE_TESTNET": os.getenv("BINANCE_TESTNET", ""),
    "BINANCE_USE_TESTNET": os.getenv("BINANCE_USE_TESTNET", ""),
    "BINANCE_ENABLE_LIVE_TRADING": os.getenv("BINANCE_ENABLE_LIVE_TRADING", ""),
    "LIVE_TRADING_ALLOWED": os.getenv("LIVE_TRADING_ALLOWED", ""),
}

safe_mode = flags["BINANCE_ENABLE_LIVE_TRADING"] == "false" and flags["LIVE_TRADING_ALLOWED"] == "false"

candidate_review = load_json(CANDIDATE_REVIEW)
final_candidates = candidate_review.get("final_candidates", [])

PLAN_DIR.mkdir(parents=True, exist_ok=True)

risk_plans = []

for candidate in final_candidates:
    candidate_id = candidate.get("final_candidate_id", "unknown_candidate")
    symbol = candidate.get("symbol", "UNKNOWN")
    params = candidate.get("candidate_parameters", {})

    plan = {
        "candidate_id": candidate_id,
        "symbol": symbol,
        "candidate_parameters": params,
        "risk_sizing_controls": {
            "starting_capital_usd": None,
            "max_single_order_notional_usd": None,
            "max_total_open_notional_usd": None,
            "risk_fraction_per_trade_max": 0.001,
            "daily_loss_limit_usd": None,
            "weekly_loss_limit_usd": None,
            "max_drawdown_limit_usd": None,
            "max_consecutive_losses": None,
            "max_orders_per_day": 3,
            "cooldown_after_loss_minutes": 120
        },
        "stress_tests_required": {
            "fee_sensitivity": True,
            "slippage_sensitivity": True,
            "spread_widening_test": True,
            "latency_delay_test": True,
            "consecutive_loss_test": True,
            "low_liquidity_test": True,
            "kill_switch_test": True,
            "drawdown_stop_test": True
        },
        "stress_test_scenarios": [
            {"name": "base_case", "fee_bps": 4, "slippage_bps": 2, "latency_ms": 0},
            {"name": "high_fee", "fee_bps": 8, "slippage_bps": 2, "latency_ms": 0},
            {"name": "high_slippage", "fee_bps": 4, "slippage_bps": 8, "latency_ms": 0},
            {"name": "high_latency", "fee_bps": 4, "slippage_bps": 4, "latency_ms": 1000},
            {"name": "stress_case", "fee_bps": 8, "slippage_bps": 10, "latency_ms": 1500}
        ],
        "approval_status": "risk_sizing_plan_created_not_approved",
        "approved_for_micro_live_execution": False,
        "approved_for_real_live_trading": False
    }

    plan_path = PLAN_DIR / f"{candidate_id.lower()}_risk_stress_plan.json"
    plan_path.write_text(json.dumps(plan, indent=2))
    plan["plan_path"] = str(plan_path)
    risk_plans.append(plan)

if risk_plans:
    decision = "CANDIDATE_RISK_SIZING_STRESS_TEST_PLAN_CREATED_NOT_APPROVED_FOR_EXECUTION"
    next_phase = "Phase 17.15 — Candidate Stress Test Runner"
else:
    decision = "CANDIDATE_RISK_SIZING_SKIPPED_NO_FINAL_CANDIDATES_STRATEGY_REWORK_REQUIRED"
    next_phase = "Phase 17.15 — Candidate Stress Test Runner or Strategy Redesign"

report = {
    "phase": "phase_17_14_candidate_risk_sizing_stress_test_plan",
    "generated_at_unix": int(time.time()),
    "scope": "candidate_risk_sizing_and_stress_test_plan_only",
    "safety_flags": flags,
    "safe_mode_active": safe_mode,
    "git_working_tree_clean": git_clean(),
    "candidate_review_present": CANDIDATE_REVIEW.exists(),
    "final_candidate_count": len(final_candidates),
    "risk_plan_count": len(risk_plans),
    "risk_plans": risk_plans,
    "approved_for_micro_live_execution": False,
    "approved_for_real_live_trading": False,
    "decision": decision,
    "next_phase": next_phase,
    "safety_notes": [
        "This phase creates risk sizing and stress test plans only.",
        "This phase does not approve live trading.",
        "This phase does not approve micro-live execution.",
        "This phase does not submit Binance orders.",
        "Capital values must be manually approved before any future execution review."
    ],
}

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(report, indent=2))

print(f"Report written to: {OUT}")
print(f"safe_mode_active={safe_mode}")
print(f"candidate_review_present={CANDIDATE_REVIEW.exists()}")
print(f"final_candidate_count={len(final_candidates)}")
print(f"risk_plan_count={len(risk_plans)}")
print("approved_for_micro_live_execution=False")
print("approved_for_real_live_trading=False")
print(f"decision={decision}")
