import json, os, subprocess, time
from pathlib import Path

OUT = Path("data/processed/phase20_strategy_rework_hypothesis_plan.json")
RUNTIME_OUT = Path("runtime/phase20_strategy_rework_hypothesis_plan_state.json")
PHASE20_DIR = Path("data/processed/phase20_strategy_rework")

FAILURE_REVIEW = Path("data/processed/phase20_strategy_failure_review.json")
FAILURE_RUNTIME = Path("runtime/phase20_strategy_failure_review_state.json")
READINESS = Path("data/processed/phase20_strategy_rework_readiness_review.json")
PHASE19_CLOSEOUT = Path("data/processed/phase19_historical_data_expansion_safety_closeout.json")

def run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True)

def git_clean():
    return run(["git", "status", "--short"]).stdout.strip() == ""

def git_head():
    r = run(["git", "rev-parse", "HEAD"])
    return r.stdout.strip() if r.returncode == 0 else None

def load_json(path):
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except Exception:
        return {}

def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2))

flags = {
    "BINANCE_TESTNET": os.getenv("BINANCE_TESTNET", ""),
    "BINANCE_USE_TESTNET": os.getenv("BINANCE_USE_TESTNET", ""),
    "BINANCE_ENABLE_LIVE_TRADING": os.getenv("BINANCE_ENABLE_LIVE_TRADING", ""),
    "LIVE_TRADING_ALLOWED": os.getenv("LIVE_TRADING_ALLOWED", ""),
}

safe_mode = flags["BINANCE_ENABLE_LIVE_TRADING"] == "false" and flags["LIVE_TRADING_ALLOWED"] == "false"
current_git_head = git_head()
git_clean_before_outputs = git_clean()

failure = load_json(FAILURE_REVIEW)
failure_runtime = load_json(FAILURE_RUNTIME)
readiness = load_json(READINESS)
phase19 = load_json(PHASE19_CLOSEOUT)

strategy_failure_review_ready = (
    failure.get("strategy_failure_review_ready") is True
    or failure_runtime.get("strategy_failure_review_ready") is True
)

selected_option = (
    failure.get("selected_option")
    or failure_runtime.get("selected_option")
    or readiness.get("selected_option")
    or phase19.get("selected_option")
)

selected_phase19_path = (
    failure.get("selected_phase19_path")
    or failure_runtime.get("selected_phase19_path")
    or readiness.get("selected_phase19_path")
    or phase19.get("selected_phase19_path")
)

selected_next_action = (
    failure.get("selected_next_action")
    or failure_runtime.get("selected_next_action")
    or readiness.get("selected_next_action")
    or phase19.get("selected_next_action")
)

failure_findings = failure.get("failure_findings", [])
failure_hypotheses = failure.get("failure_hypotheses", [])

hypothesis_plan = [
    {
        "hypothesis_id": "regime_filter_rework",
        "problem": "Baseline strategy may enter during poor market regimes.",
        "planned_fix": "Add trend/range/volatility regime classification before signal approval.",
        "test_method": "Offline backtest only using existing BTC/ETH datasets.",
        "success_criteria": [
            "Lower drawdown than Phase 17 baseline",
            "Positive net return after fees and slippage",
            "No single-symbol-only dependency"
        ],
        "execution_allowed": False
    },
    {
        "hypothesis_id": "multi_timeframe_confirmation",
        "problem": "Signal direction may be too weak on a single timeframe.",
        "planned_fix": "Require higher-timeframe alignment before approving entries.",
        "test_method": "Offline simulation only.",
        "success_criteria": [
            "Reduced false entries",
            "Improved win rate",
            "Improved expected net return"
        ],
        "execution_allowed": False
    },
    {
        "hypothesis_id": "volatility_aware_exit_logic",
        "problem": "Exit logic may not control losses well enough.",
        "planned_fix": "Test ATR stop, trailing stop, time stop, and invalidation stop combinations.",
        "test_method": "Offline backtest only.",
        "success_criteria": [
            "Max drawdown reduced",
            "Loss tail reduced",
            "Average loss controlled"
        ],
        "execution_allowed": False
    },
    {
        "hypothesis_id": "fee_slippage_edge_filter",
        "problem": "Gross edge may disappear after fees and slippage.",
        "planned_fix": "Reject signals unless expected edge exceeds fee and slippage buffer.",
        "test_method": "Offline scoring and backtest only.",
        "success_criteria": [
            "Net return remains positive after conservative slippage",
            "Low-quality signals rejected",
            "Trade count remains sufficient for review"
        ],
        "execution_allowed": False
    },
    {
        "hypothesis_id": "robustness_filter",
        "problem": "Parameter candidates may be unstable or overfit.",
        "planned_fix": "Require candidate stability across symbols, parameter neighborhoods, and time windows.",
        "test_method": "Offline robustness review only.",
        "success_criteria": [
            "Candidate does not depend on one narrow parameter set",
            "Candidate survives BTC and ETH review",
            "Candidate passes strict quality gate before any future execution review"
        ],
        "execution_allowed": False
    }
]

planned_outputs = [
    "strategy_rework_experiment_design",
    "offline_reworked_strategy_backtest_spec",
    "strategy_quality_gate_v2",
    "candidate_rejection_rules",
    "research_only_result_review"
]

plan_checks = {
    "safe_mode_active": safe_mode,
    "failure_review_present": FAILURE_REVIEW.exists(),
    "failure_runtime_present": FAILURE_RUNTIME.exists(),
    "readiness_present": READINESS.exists(),
    "phase19_closeout_present": PHASE19_CLOSEOUT.exists(),
    "strategy_failure_review_ready": strategy_failure_review_ready,
    "selected_option_is_remain_on_hold": selected_option == "remain_on_hold",
    "selected_next_action_is_remain_on_hold": selected_next_action == "remain_on_hold",
    "failure_findings_present": len(failure_findings) > 0,
    "failure_hypotheses_present": len(failure_hypotheses) > 0,
    "hypothesis_plan_created": len(hypothesis_plan) >= 5,
    "approved_for_execution_false": failure.get("approved_for_execution") is False,
    "approved_for_paper_shadow_false": failure.get("approved_for_paper_shadow") is False,
    "approved_for_live_false": failure.get("approved_for_live") is False,
    "paper_shadow_not_started": failure.get("paper_shadow_started") is False,
    "paper_shadow_start_not_approved": failure.get("approved_for_paper_shadow_start") is False,
    "exchange_order_submission_disabled": failure.get("exchange_order_submission") is False,
    "micro_live_not_approved": failure.get("approved_for_micro_live_execution") is False,
    "real_live_not_approved": failure.get("approved_for_real_live_trading") is False,
}

blockers = [k for k, v in plan_checks.items() if v is not True]
strategy_rework_hypothesis_plan_ready = all(plan_checks.values())

if strategy_rework_hypothesis_plan_ready:
    decision = "PHASE_20_STRATEGY_REWORK_HYPOTHESIS_PLAN_CREATED_RESEARCH_ONLY_NOT_APPROVED_FOR_EXECUTION"
    next_phase = "Phase 20.4 — Strategy Rework Experiment Design"
else:
    decision = "PHASE_20_STRATEGY_REWORK_HYPOTHESIS_PLAN_BLOCKED_REVIEW_REQUIRED"
    next_phase = "Phase 20.4 — Strategy Rework Hypothesis Plan Fix"

record = {
    "phase": "phase_20_3_strategy_rework_hypothesis_plan_record",
    "created_at_unix": int(time.time()),
    "git_head": current_git_head,
    "system_state": "HOLD_RESEARCH_ONLY",
    "selected_option": selected_option,
    "selected_phase19_path": selected_phase19_path,
    "selected_next_action": selected_next_action,
    "strategy_rework_hypothesis_plan_ready": strategy_rework_hypothesis_plan_ready,
    "plan_checks": plan_checks,
    "blockers": blockers,
    "failure_findings": failure_findings,
    "source_failure_hypotheses": failure_hypotheses,
    "hypothesis_plan": hypothesis_plan,
    "planned_outputs": planned_outputs,
    "approved_for_execution": False,
    "approved_for_paper_shadow": False,
    "approved_for_live": False,
    "paper_shadow_started": False,
    "approved_for_paper_shadow_start": False,
    "exchange_order_submission": False,
    "approved_for_micro_live_execution": False,
    "approved_for_real_live_trading": False,
    "decision": decision,
    "next_phase": next_phase
}

record_file = PHASE20_DIR / "strategy_rework_hypothesis_plan.json"

write_json(record_file, record)
write_json(RUNTIME_OUT, record)

report = {
    "phase": "phase_20_3_strategy_rework_hypothesis_plan",
    "generated_at_unix": int(time.time()),
    "scope": "research_only_hypothesis_plan_no_execution",
    "git_head": current_git_head,
    "safety_flags": flags,
    "safe_mode_active": safe_mode,
    "git_working_tree_clean": git_clean_before_outputs,
    "strategy_rework_hypothesis_plan_ready": strategy_rework_hypothesis_plan_ready,
    "selected_option": selected_option,
    "selected_phase19_path": selected_phase19_path,
    "selected_next_action": selected_next_action,
    "plan_checks": plan_checks,
    "blockers": blockers,
    "hypothesis_count": len(hypothesis_plan),
    "planned_outputs": planned_outputs,
    "record_file": str(record_file),
    "runtime_record_file": str(RUNTIME_OUT),
    "approved_for_execution": False,
    "approved_for_paper_shadow": False,
    "approved_for_live": False,
    "paper_shadow_started": False,
    "approved_for_paper_shadow_start": False,
    "exchange_order_submission": False,
    "approved_for_micro_live_execution": False,
    "approved_for_real_live_trading": False,
    "decision": decision,
    "next_phase": next_phase,
    "safety_notes": [
        "This phase creates a research-only strategy rework hypothesis plan.",
        "This phase does not run a backtest.",
        "This phase does not start paper shadow execution.",
        "This phase does not approve micro-live execution.",
        "This phase does not approve real live trading.",
        "This phase does not submit Binance orders."
    ]
}

write_json(OUT, report)

print(f"Report written to: {OUT}")
print(f"Runtime record written to: {RUNTIME_OUT}")
print(f"Record file written to: {record_file}")
print(f"safe_mode_active={safe_mode}")
print(f"strategy_rework_hypothesis_plan_ready={strategy_rework_hypothesis_plan_ready}")
print(f"hypothesis_count={len(hypothesis_plan)}")
print("approved_for_execution=False")
print("approved_for_paper_shadow=False")
print("approved_for_live=False")
print("paper_shadow_started=False")
print("approved_for_paper_shadow_start=False")
print("exchange_order_submission=False")
print("approved_for_micro_live_execution=False")
print("approved_for_real_live_trading=False")
print(f"decision={decision}")
