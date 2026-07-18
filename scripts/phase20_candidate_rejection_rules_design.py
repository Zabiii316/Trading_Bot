import json, os, subprocess, time
from pathlib import Path

OUT = Path("data/processed/phase20_candidate_rejection_rules_design.json")
RUNTIME_OUT = Path("runtime/phase20_candidate_rejection_rules_design_state.json")
PHASE20_DIR = Path("data/processed/phase20_strategy_rework")

QUALITY_GATE = Path("data/processed/phase20_strategy_quality_gate_v2_design.json")
QUALITY_GATE_RUNTIME = Path("runtime/phase20_strategy_quality_gate_v2_design_state.json")
BACKTEST_SPEC = Path("data/processed/phase20_offline_reworked_strategy_backtest_spec.json")
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

gate = load_json(QUALITY_GATE)
gate_runtime = load_json(QUALITY_GATE_RUNTIME)
spec = load_json(BACKTEST_SPEC)
experiment = load_json(EXPERIMENT_DESIGN)
hypothesis = load_json(HYPOTHESIS_PLAN)
failure = load_json(FAILURE_REVIEW)
readiness = load_json(READINESS)

strategy_quality_gate_v2_ready = (
    gate.get("strategy_quality_gate_v2_ready") is True
    or gate_runtime.get("strategy_quality_gate_v2_ready") is True
)

selected_option = gate.get("selected_option") or gate_runtime.get("selected_option")
selected_phase19_path = gate.get("selected_phase19_path") or gate_runtime.get("selected_phase19_path")
selected_next_action = gate.get("selected_next_action") or gate_runtime.get("selected_next_action")

offline_backtest_spec_ready = spec.get("offline_backtest_spec_ready") is True
experiment_design_ready = experiment.get("strategy_rework_experiment_design_ready") is True
hypothesis_plan_ready = hypothesis.get("strategy_rework_hypothesis_plan_ready") is True
strategy_failure_review_ready = failure.get("strategy_failure_review_ready") is True
research_only_ready = readiness.get("research_only_strategy_rework_ready") is True

candidate_rejection_rules_v2 = {
    "rule_set_id": "phase20_candidate_rejection_rules_v2",
    "mode": "research_only",
    "execution_allowed": False,
    "paper_shadow_allowed": False,
    "live_trading_allowed": False,
    "rules": [
        {
            "rule_id": "reject_negative_net_return",
            "severity": "hard_fail",
            "condition": "combined_net_return_bps <= 0",
            "reason": "Candidate has no positive net edge after fees and slippage."
        },
        {
            "rule_id": "reject_profit_factor_not_above_one",
            "severity": "hard_fail",
            "condition": "profit_factor <= 1.0",
            "reason": "Candidate does not show profitable payoff structure."
        },
        {
            "rule_id": "reject_drawdown_not_improved",
            "severity": "hard_fail",
            "condition": "max_drawdown_pct not improved versus Phase 17 baseline",
            "reason": "Candidate does not improve risk profile."
        },
        {
            "rule_id": "reject_single_symbol_dependency",
            "severity": "hard_fail",
            "condition": "candidate passes BTCUSDT only or ETHUSDT only",
            "reason": "Candidate may be symbol-specific or unstable."
        },
        {
            "rule_id": "reject_low_trade_count",
            "severity": "hard_fail",
            "condition": "trade_count_per_symbol < 10",
            "reason": "Candidate has insufficient sample size for review."
        },
        {
            "rule_id": "reject_fee_slippage_failure",
            "severity": "hard_fail",
            "condition": "candidate fails conservative fee/slippage scenarios",
            "reason": "Candidate edge is not robust to realistic costs."
        },
        {
            "rule_id": "reject_missing_required_metrics",
            "severity": "hard_fail",
            "condition": "required metrics missing from result payload",
            "reason": "Candidate cannot be reviewed safely without complete metrics."
        },
        {
            "rule_id": "reject_missing_symbol_level_results",
            "severity": "hard_fail",
            "condition": "symbol_level_results missing",
            "reason": "Candidate cannot prove robustness across symbols."
        },
        {
            "rule_id": "reject_parameter_overfit",
            "severity": "hard_fail",
            "condition": "candidate only works in one narrow parameter setting",
            "reason": "Candidate may be overfit."
        },
        {
            "rule_id": "reject_execution_flag_true",
            "severity": "safety_hard_fail",
            "condition": "approved_for_execution or approved_for_paper_shadow or approved_for_live is true",
            "reason": "Phase 20 is research-only and cannot approve execution."
        },
        {
            "rule_id": "reject_exchange_submission_enabled",
            "severity": "safety_hard_fail",
            "condition": "exchange_order_submission is true",
            "reason": "No exchange order submission is allowed."
        },
        {
            "rule_id": "reject_real_capital_enabled",
            "severity": "safety_hard_fail",
            "condition": "real_capital_allowed is true",
            "reason": "No real capital usage is allowed."
        }
    ],
    "required_candidate_payload_fields": [
        "candidate_id",
        "strategy_variant",
        "symbols_tested",
        "combined_results",
        "symbol_level_results",
        "net_return_bps",
        "profit_factor",
        "max_drawdown_pct",
        "trade_count",
        "win_rate",
        "expectancy_bps",
        "fee_slippage_sensitivity",
        "candidate_rejection_reasons",
        "approved_for_execution",
        "approved_for_paper_shadow",
        "approved_for_live",
        "exchange_order_submission"
    ],
    "final_candidate_state_options": [
        "rejected",
        "research_review_only",
        "quality_gate_review_required"
    ],
    "forbidden_candidate_states": [
        "approved_for_execution",
        "approved_for_paper_shadow",
        "approved_for_micro_live",
        "approved_for_real_live"
    ]
}

rule_checks = {
    "safe_mode_active": safe_mode,
    "quality_gate_present": QUALITY_GATE.exists(),
    "quality_gate_runtime_present": QUALITY_GATE_RUNTIME.exists(),
    "backtest_spec_present": BACKTEST_SPEC.exists(),
    "experiment_design_present": EXPERIMENT_DESIGN.exists(),
    "hypothesis_plan_present": HYPOTHESIS_PLAN.exists(),
    "failure_review_present": FAILURE_REVIEW.exists(),
    "readiness_present": READINESS.exists(),
    "strategy_quality_gate_v2_ready": strategy_quality_gate_v2_ready,
    "offline_backtest_spec_ready": offline_backtest_spec_ready,
    "experiment_design_ready": experiment_design_ready,
    "hypothesis_plan_ready": hypothesis_plan_ready,
    "strategy_failure_review_ready": strategy_failure_review_ready,
    "research_only_ready": research_only_ready,
    "selected_option_is_remain_on_hold": selected_option == "remain_on_hold",
    "selected_next_action_is_remain_on_hold": selected_next_action == "remain_on_hold",
    "candidate_rejection_rules_created": isinstance(candidate_rejection_rules_v2, dict),
    "rule_count_sufficient": len(candidate_rejection_rules_v2["rules"]) >= 10,
    "required_payload_fields_created": len(candidate_rejection_rules_v2["required_candidate_payload_fields"]) >= 12,
    "execution_allowed_false": candidate_rejection_rules_v2["execution_allowed"] is False,
    "paper_shadow_allowed_false": candidate_rejection_rules_v2["paper_shadow_allowed"] is False,
    "live_trading_allowed_false": candidate_rejection_rules_v2["live_trading_allowed"] is False,
    "run_backtest_now_false": spec.get("run_backtest_now") is False,
    "approved_for_execution_false": gate.get("approved_for_execution") is False,
    "approved_for_paper_shadow_false": gate.get("approved_for_paper_shadow") is False,
    "approved_for_live_false": gate.get("approved_for_live") is False,
    "paper_shadow_not_started": gate.get("paper_shadow_started") is False,
    "paper_shadow_start_not_approved": gate.get("approved_for_paper_shadow_start") is False,
    "exchange_order_submission_disabled": gate.get("exchange_order_submission") is False,
    "micro_live_not_approved": gate.get("approved_for_micro_live_execution") is False,
    "real_live_not_approved": gate.get("approved_for_real_live_trading") is False,
}

blockers = [k for k, v in rule_checks.items() if v is not True]
candidate_rejection_rules_ready = all(rule_checks.values())

if candidate_rejection_rules_ready:
    decision = "PHASE_20_CANDIDATE_REJECTION_RULES_DESIGNED_RESEARCH_ONLY_NOT_APPROVED_FOR_EXECUTION"
    next_phase = "Phase 20.8 — Offline Reworked Strategy Runner Design"
else:
    decision = "PHASE_20_CANDIDATE_REJECTION_RULES_DESIGN_BLOCKED_REVIEW_REQUIRED"
    next_phase = "Phase 20.8 — Candidate Rejection Rules Fix"

record = {
    "phase": "phase_20_7_candidate_rejection_rules_design_record",
    "created_at_unix": int(time.time()),
    "git_head": current_git_head,
    "system_state": "HOLD_RESEARCH_ONLY",
    "selected_option": selected_option,
    "selected_phase19_path": selected_phase19_path,
    "selected_next_action": selected_next_action,
    "candidate_rejection_rules_ready": candidate_rejection_rules_ready,
    "rule_checks": rule_checks,
    "blockers": blockers,
    "candidate_rejection_rules_v2": candidate_rejection_rules_v2,
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

record_file = PHASE20_DIR / "candidate_rejection_rules_design.json"

write_json(record_file, record)
write_json(RUNTIME_OUT, record)

report = {
    "phase": "phase_20_7_candidate_rejection_rules_design",
    "generated_at_unix": int(time.time()),
    "scope": "candidate_rejection_rules_design_only_no_backtest_no_execution",
    "git_head": current_git_head,
    "safety_flags": flags,
    "safe_mode_active": safe_mode,
    "git_working_tree_clean": git_clean_before_outputs,
    "candidate_rejection_rules_ready": candidate_rejection_rules_ready,
    "selected_option": selected_option,
    "selected_phase19_path": selected_phase19_path,
    "selected_next_action": selected_next_action,
    "rule_count": len(candidate_rejection_rules_v2["rules"]),
    "required_payload_field_count": len(candidate_rejection_rules_v2["required_candidate_payload_fields"]),
    "rule_checks": rule_checks,
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
        "This phase designs candidate rejection rules only.",
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
print(f"candidate_rejection_rules_ready={candidate_rejection_rules_ready}")
print(f"rule_count={len(candidate_rejection_rules_v2['rules'])}")
print(f"required_payload_field_count={len(candidate_rejection_rules_v2['required_candidate_payload_fields'])}")
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
