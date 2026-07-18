import json, os, subprocess, time
from pathlib import Path

OUT = Path("data/processed/phase20_strategy_quality_gate_v2_design.json")
RUNTIME_OUT = Path("runtime/phase20_strategy_quality_gate_v2_design_state.json")
PHASE20_DIR = Path("data/processed/phase20_strategy_rework")

BACKTEST_SPEC = Path("data/processed/phase20_offline_reworked_strategy_backtest_spec.json")
BACKTEST_SPEC_RUNTIME = Path("runtime/phase20_offline_reworked_strategy_backtest_spec_state.json")
EXPERIMENT_DESIGN = Path("data/processed/phase20_strategy_rework_experiment_design.json")
HYPOTHESIS_PLAN = Path("data/processed/phase20_strategy_rework_hypothesis_plan.json")
FAILURE_REVIEW = Path("data/processed/phase20_strategy_failure_review.json")
READINESS = Path("data/processed/phase20_strategy_rework_readiness_review.json")

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

spec = load_json(BACKTEST_SPEC)
spec_runtime = load_json(BACKTEST_SPEC_RUNTIME)
experiment = load_json(EXPERIMENT_DESIGN)
hypothesis = load_json(HYPOTHESIS_PLAN)
failure = load_json(FAILURE_REVIEW)
readiness = load_json(READINESS)

offline_backtest_spec_ready = (
    spec.get("offline_backtest_spec_ready") is True
    or spec_runtime.get("offline_backtest_spec_ready") is True
)

selected_option = spec.get("selected_option") or spec_runtime.get("selected_option")
selected_phase19_path = spec.get("selected_phase19_path") or spec_runtime.get("selected_phase19_path")
selected_next_action = spec.get("selected_next_action") or spec_runtime.get("selected_next_action")

quality_gate_v2 = {
    "gate_id": "phase20_strategy_quality_gate_v2",
    "mode": "research_only",
    "execution_allowed": False,
    "paper_shadow_allowed": False,
    "live_trading_allowed": False,
    "required_before_any_future_execution_review": True,
    "hard_fail_rules": [
        "fail_if_net_return_bps_less_or_equal_zero",
        "fail_if_profit_factor_less_than_or_equal_one",
        "fail_if_max_drawdown_not_improved_vs_phase17_baseline",
        "fail_if_candidate_passes_only_one_symbol",
        "fail_if_trade_count_too_low",
        "fail_if_fee_slippage_sensitivity_fails",
        "fail_if_results_missing_fees_or_slippage",
        "fail_if_any_execution_approval_flag_true"
    ],
    "minimum_thresholds": {
        "combined_net_return_bps": "> 0",
        "profit_factor": "> 1.0",
        "minimum_symbols_required": 2,
        "required_symbols": ["BTCUSDT", "ETHUSDT"],
        "minimum_trade_count_per_symbol": 10,
        "max_drawdown_must_improve_vs_phase17": True,
        "fee_slippage_scenarios_required": [2, 4, 6, 8, 10],
        "must_include_symbol_level_results": True,
        "must_include_combined_results": True,
        "must_include_candidate_rejection_reasons": True
    },
    "robustness_requirements": {
        "must_pass_btc": True,
        "must_pass_eth": True,
        "must_not_depend_on_single_parameter": True,
        "must_not_depend_on_single_symbol": True,
        "must_pass_conservative_slippage": True,
        "must_report_losing_variants": True
    },
    "approval_limits": {
        "approved_for_execution": False,
        "approved_for_paper_shadow": False,
        "approved_for_live": False,
        "exchange_order_submission": False,
        "real_capital_allowed": False
    }
}

gate_checks = {
    "safe_mode_active": safe_mode,
    "backtest_spec_present": BACKTEST_SPEC.exists(),
    "backtest_spec_runtime_present": BACKTEST_SPEC_RUNTIME.exists(),
    "experiment_design_present": EXPERIMENT_DESIGN.exists(),
    "hypothesis_plan_present": HYPOTHESIS_PLAN.exists(),
    "failure_review_present": FAILURE_REVIEW.exists(),
    "readiness_present": READINESS.exists(),
    "offline_backtest_spec_ready": offline_backtest_spec_ready,
    "selected_option_is_remain_on_hold": selected_option == "remain_on_hold",
    "selected_next_action_is_remain_on_hold": selected_next_action == "remain_on_hold",
    "quality_gate_created": isinstance(quality_gate_v2, dict),
    "hard_fail_rules_created": len(quality_gate_v2["hard_fail_rules"]) >= 8,
    "minimum_thresholds_created": isinstance(quality_gate_v2["minimum_thresholds"], dict),
    "robustness_requirements_created": isinstance(quality_gate_v2["robustness_requirements"], dict),
    "execution_allowed_false": quality_gate_v2["execution_allowed"] is False,
    "paper_shadow_allowed_false": quality_gate_v2["paper_shadow_allowed"] is False,
    "live_trading_allowed_false": quality_gate_v2["live_trading_allowed"] is False,
    "run_backtest_now_false": spec.get("run_backtest_now") is False,
    "approved_for_execution_false": spec.get("approved_for_execution") is False,
    "approved_for_paper_shadow_false": spec.get("approved_for_paper_shadow") is False,
    "approved_for_live_false": spec.get("approved_for_live") is False,
    "paper_shadow_not_started": spec.get("paper_shadow_started") is False,
    "paper_shadow_start_not_approved": spec.get("approved_for_paper_shadow_start") is False,
    "exchange_order_submission_disabled": spec.get("exchange_order_submission") is False,
    "micro_live_not_approved": spec.get("approved_for_micro_live_execution") is False,
    "real_live_not_approved": spec.get("approved_for_real_live_trading") is False,
}

blockers = [k for k, v in gate_checks.items() if v is not True]
strategy_quality_gate_v2_ready = all(gate_checks.values())

if strategy_quality_gate_v2_ready:
    decision = "PHASE_20_STRATEGY_QUALITY_GATE_V2_DESIGNED_RESEARCH_ONLY_NOT_APPROVED_FOR_EXECUTION"
    next_phase = "Phase 20.7 — Candidate Rejection Rules Design"
else:
    decision = "PHASE_20_STRATEGY_QUALITY_GATE_V2_DESIGN_BLOCKED_REVIEW_REQUIRED"
    next_phase = "Phase 20.7 — Strategy Quality Gate V2 Fix"

record = {
    "phase": "phase_20_6_strategy_quality_gate_v2_design_record",
    "created_at_unix": int(time.time()),
    "git_head": current_git_head,
    "system_state": "HOLD_RESEARCH_ONLY",
    "selected_option": selected_option,
    "selected_phase19_path": selected_phase19_path,
    "selected_next_action": selected_next_action,
    "strategy_quality_gate_v2_ready": strategy_quality_gate_v2_ready,
    "gate_checks": gate_checks,
    "blockers": blockers,
    "quality_gate_v2": quality_gate_v2,
    "run_backtest_now": False,
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

record_file = PHASE20_DIR / "strategy_quality_gate_v2_design.json"

write_json(record_file, record)
write_json(RUNTIME_OUT, record)

report = {
    "phase": "phase_20_6_strategy_quality_gate_v2_design",
    "generated_at_unix": int(time.time()),
    "scope": "quality_gate_design_only_no_backtest_no_execution",
    "git_head": current_git_head,
    "safety_flags": flags,
    "safe_mode_active": safe_mode,
    "git_working_tree_clean": git_clean_before_outputs,
    "strategy_quality_gate_v2_ready": strategy_quality_gate_v2_ready,
    "selected_option": selected_option,
    "selected_phase19_path": selected_phase19_path,
    "selected_next_action": selected_next_action,
    "hard_fail_rule_count": len(quality_gate_v2["hard_fail_rules"]),
    "gate_checks": gate_checks,
    "blockers": blockers,
    "record_file": str(record_file),
    "runtime_record_file": str(RUNTIME_OUT),
    "run_backtest_now": False,
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
        "This phase designs Strategy Quality Gate V2 only.",
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
print(f"strategy_quality_gate_v2_ready={strategy_quality_gate_v2_ready}")
print(f"hard_fail_rule_count={len(quality_gate_v2['hard_fail_rules'])}")
print("run_backtest_now=False")
print("approved_for_execution=False")
print("approved_for_paper_shadow=False")
print("approved_for_live=False")
print("paper_shadow_started=False")
print("approved_for_paper_shadow_start=False")
print("exchange_order_submission=False")
print("approved_for_micro_live_execution=False")
print("approved_for_real_live_trading=False")
print(f"decision={decision}")
