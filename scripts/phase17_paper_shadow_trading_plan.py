import json, os, subprocess, time
from pathlib import Path

OUT = Path("data/processed/phase17_paper_shadow_trading_plan.json")
STRESS_REVIEW_INPUT = Path("data/processed/phase17_stress_test_results_review.json")
PLAN_DIR = Path("data/processed/paper_shadow_plans")

PAPER_SHADOW_DAYS = 7
MIN_SHADOW_SIGNALS = 25
MAX_DAILY_PAPER_LOSS_BPS = 100
MAX_TOTAL_PAPER_DRAWDOWN_BPS = 300
MAX_PAPER_ORDERS_PER_DAY = 5

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

stress_review = load_json(STRESS_REVIEW_INPUT)
forward_candidates = stress_review.get("forward_candidates", [])

PLAN_DIR.mkdir(parents=True, exist_ok=True)

paper_shadow_plans = []

for idx, candidate in enumerate(forward_candidates, start=1):
    candidate_id = candidate.get("candidate_id", f"candidate_{idx}")
    symbol = candidate.get("symbol", "UNKNOWN")
    params = candidate.get("candidate_parameters", {})

    plan = {
        "paper_shadow_plan_id": f"{symbol}_paper_shadow_plan_{idx}",
        "source_candidate_id": candidate_id,
        "symbol": symbol,
        "candidate_parameters": params,
        "mode": "paper_shadow_only",
        "exchange_order_submission": False,
        "live_trading_enabled": False,
        "duration_days": PAPER_SHADOW_DAYS,
        "minimum_shadow_signals_required": MIN_SHADOW_SIGNALS,
        "shadow_controls": {
            "max_daily_paper_loss_bps": MAX_DAILY_PAPER_LOSS_BPS,
            "max_total_paper_drawdown_bps": MAX_TOTAL_PAPER_DRAWDOWN_BPS,
            "max_paper_orders_per_day": MAX_PAPER_ORDERS_PER_DAY,
            "kill_switch_required": True,
            "manual_review_required_after_shadow": True,
            "production_api_keys_required": False,
            "real_capital_allowed": False
        },
        "required_metrics": [
            "paper_signal_count",
            "paper_order_count",
            "paper_fill_count",
            "paper_pnl_bps",
            "paper_drawdown_bps",
            "paper_win_rate",
            "paper_profit_factor",
            "latency_ms",
            "spread_bps",
            "rejection_count",
            "kill_switch_events"
        ],
        "approval_status": "paper_shadow_plan_created_not_started_not_approved",
        "approved_for_micro_live_execution": False,
        "approved_for_real_live_trading": False
    }

    plan_path = PLAN_DIR / f"{plan['paper_shadow_plan_id'].lower()}.json"
    plan_path.write_text(json.dumps(plan, indent=2))
    plan["plan_path"] = str(plan_path)

    paper_shadow_plans.append(plan)

if paper_shadow_plans:
    decision = "PAPER_SHADOW_TRADING_PLAN_CREATED_NOT_STARTED_NOT_APPROVED_FOR_EXECUTION"
    next_phase = "Phase 17.18 — Paper Shadow Execution Harness"
else:
    decision = "PAPER_SHADOW_TRADING_PLAN_SKIPPED_NO_FORWARD_CANDIDATES_STRATEGY_REWORK_REQUIRED"
    next_phase = "Phase 17.18 — Paper Shadow Execution Harness or Strategy Redesign"

report = {
    "phase": "phase_17_17_paper_shadow_trading_plan",
    "generated_at_unix": int(time.time()),
    "scope": "paper_shadow_trading_plan_only",
    "safety_flags": flags,
    "safe_mode_active": safe_mode,
    "git_working_tree_clean": git_clean(),
    "stress_review_input_present": STRESS_REVIEW_INPUT.exists(),
    "forward_candidate_count": len(forward_candidates),
    "paper_shadow_plan_count": len(paper_shadow_plans),
    "paper_shadow_plans": paper_shadow_plans,
    "approved_for_micro_live_execution": False,
    "approved_for_real_live_trading": False,
    "decision": decision,
    "next_phase": next_phase,
    "safety_notes": [
        "This phase creates paper shadow trading plans only.",
        "This phase does not start paper shadow execution.",
        "This phase does not approve live trading.",
        "This phase does not approve micro-live execution.",
        "This phase does not submit Binance orders.",
        "Paper shadow must run with live trading flags disabled."
    ],
}

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(report, indent=2))

print(f"Report written to: {OUT}")
print(f"safe_mode_active={safe_mode}")
print(f"forward_candidate_count={len(forward_candidates)}")
print(f"paper_shadow_plan_count={len(paper_shadow_plans)}")
print("approved_for_micro_live_execution=False")
print("approved_for_real_live_trading=False")
print(f"decision={decision}")
