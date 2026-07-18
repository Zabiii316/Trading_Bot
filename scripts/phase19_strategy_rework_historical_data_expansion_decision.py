import json, os, subprocess, time
from pathlib import Path

OUT = Path("data/processed/phase19_strategy_rework_historical_data_expansion_decision.json")
RUNTIME_OUT = Path("runtime/phase19_strategy_rework_historical_data_expansion_decision_state.json")
DECISION_DIR = Path("data/processed/phase19_strategy_rework")

PHASE18_CLOSEOUT = Path("data/processed/phase18_final_safety_closeout.json")
PHASE17_QUALITY_GATE = Path("data/processed/phase17_backtest_results_review_quality_gate.json")
PHASE17_DATA_AUDIT = Path("data/processed/phase17_historical_data_coverage_audit.json")
PHASE17_DATASET_BUILDER = Path("data/processed/phase17_historical_backtest_dataset_builder.json")
PHASE17_FINAL_CANDIDATES = Path("data/processed/phase17_final_strategy_candidate_review.json")

def run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True)

def git_clean():
    return run(["git", "status", "--short"]).stdout.strip() == ""

def git_head():
    result = run(["git", "rev-parse", "HEAD"])
    return result.stdout.strip() if result.returncode == 0 else None

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
git_clean_before_outputs = git_clean()
current_git_head = git_head()

phase18 = load_json(PHASE18_CLOSEOUT)
quality_gate = load_json(PHASE17_QUALITY_GATE)
data_audit = load_json(PHASE17_DATA_AUDIT)
dataset_builder = load_json(PHASE17_DATASET_BUILDER)
final_candidates = load_json(PHASE17_FINAL_CANDIDATES)

phase18_closed_safely = phase18.get("phase18_closed_safely") is True
selected_option = phase18.get("selected_option", "remain_on_hold")

failed_symbols = (
    quality_gate.get("failed_symbols")
    or quality_gate.get("symbols_failed")
    or quality_gate.get("failed_backtest_symbols")
    or []
)

strategy_rework_required = True
historical_data_expansion_required = True

dataset_notes = {
    "phase17_quality_gate_present": PHASE17_QUALITY_GATE.exists(),
    "phase17_data_audit_present": PHASE17_DATA_AUDIT.exists(),
    "phase17_dataset_builder_present": PHASE17_DATASET_BUILDER.exists(),
    "phase17_final_candidates_present": PHASE17_FINAL_CANDIDATES.exists(),
    "failed_symbols": failed_symbols,
    "data_audit_decision": data_audit.get("decision"),
    "dataset_builder_decision": dataset_builder.get("decision"),
    "candidate_review_decision": final_candidates.get("decision"),
}

decision_checks = {
    "safe_mode_active": safe_mode,
    "phase18_closeout_present": PHASE18_CLOSEOUT.exists(),
    "phase18_closed_safely": phase18_closed_safely,
    "selected_option_is_remain_on_hold": selected_option == "remain_on_hold",
    "strategy_rework_required": strategy_rework_required,
    "historical_data_expansion_required": historical_data_expansion_required,
    "paper_shadow_not_started": phase18.get("paper_shadow_started") is False,
    "paper_shadow_start_not_approved": phase18.get("approved_for_paper_shadow_start") is False,
    "exchange_order_submission_disabled": phase18.get("exchange_order_submission") is False,
    "micro_live_not_approved": phase18.get("approved_for_micro_live_execution") is False,
    "real_live_not_approved": phase18.get("approved_for_real_live_trading") is False,
}

blockers = [k for k, v in decision_checks.items() if v is not True]
phase19_decision_ready = all(decision_checks.values())

DECISION_DIR.mkdir(parents=True, exist_ok=True)

if phase19_decision_ready:
    decision = "PHASE_19_STRATEGY_REWORK_AND_DATA_EXPANSION_DECISION_CREATED_NOT_APPROVED_FOR_EXECUTION"
    next_phase = "Phase 19.2 — Historical Data Expansion Plan"
else:
    decision = "PHASE_19_STRATEGY_REWORK_AND_DATA_EXPANSION_DECISION_BLOCKED_REVIEW_REQUIRED"
    next_phase = "Phase 19.2 — Phase 19 Decision Review"

decision_record = {
    "phase": "phase_19_1_strategy_rework_historical_data_expansion_decision_record",
    "created_at_unix": int(time.time()),
    "git_head": current_git_head,
    "system_state": "HOLD",
    "selected_option": selected_option,
    "phase19_decision_ready": phase19_decision_ready,
    "decision_checks": decision_checks,
    "blockers": blockers,
    "strategy_rework_required": strategy_rework_required,
    "historical_data_expansion_required": historical_data_expansion_required,
    "selected_phase19_path": "historical_data_expansion_first_then_strategy_rework",
    "dataset_notes": dataset_notes,
    "allowed_actions": [
        "historical_data_expansion_plan_only",
        "offline_dataset_building_only",
        "offline_strategy_rework_only",
        "offline_backtest_design_only",
        "documentation_only"
    ],
    "blocked_actions": [
        "paper_shadow_start",
        "micro_live_execution",
        "real_live_trading",
        "exchange_order_submission",
        "real_capital_usage",
        "production_api_key_usage"
    ],
    "status_summary": {
        "paper_shadow_started": False,
        "approved_for_paper_shadow_start": False,
        "exchange_order_submission": False,
        "real_capital_allowed": False,
        "live_trading_enabled": False,
        "approved_for_micro_live_execution": False,
        "approved_for_real_live_trading": False
    },
    "decision": decision,
    "next_phase": next_phase
}

decision_file = DECISION_DIR / "strategy_rework_historical_data_expansion_decision.json"
write_json(decision_file, decision_record)
write_json(RUNTIME_OUT, decision_record)

report = {
    "phase": "phase_19_1_strategy_rework_historical_data_expansion_decision",
    "generated_at_unix": int(time.time()),
    "scope": "decision_only_no_execution",
    "git_head": current_git_head,
    "safety_flags": flags,
    "safe_mode_active": safe_mode,
    "git_working_tree_clean": git_clean_before_outputs,
    "selected_option": selected_option,
    "phase19_decision_ready": phase19_decision_ready,
    "decision_checks": decision_checks,
    "blockers": blockers,
    "strategy_rework_required": strategy_rework_required,
    "historical_data_expansion_required": historical_data_expansion_required,
    "selected_phase19_path": "historical_data_expansion_first_then_strategy_rework",
    "decision_file": str(decision_file),
    "runtime_decision_file": str(RUNTIME_OUT),
    "paper_shadow_started": False,
    "approved_for_paper_shadow_start": False,
    "exchange_order_submission": False,
    "real_capital_allowed": False,
    "live_trading_enabled": False,
    "approved_for_micro_live_execution": False,
    "approved_for_real_live_trading": False,
    "decision": decision,
    "next_phase": next_phase,
    "safety_notes": [
        "This phase only selects the Phase 19 research path.",
        "This phase does not start paper shadow execution.",
        "This phase does not approve micro-live execution.",
        "This phase does not approve real live trading.",
        "This phase does not submit Binance orders.",
        "Real capital and exchange order submission remain disabled."
    ]
}

write_json(OUT, report)

print(f"Report written to: {OUT}")
print(f"Runtime decision written to: {RUNTIME_OUT}")
print(f"Decision file written to: {decision_file}")
print(f"safe_mode_active={safe_mode}")
print(f"selected_option={selected_option}")
print(f"phase19_decision_ready={phase19_decision_ready}")
print(f"selected_phase19_path=historical_data_expansion_first_then_strategy_rework")
print("paper_shadow_started=False")
print("approved_for_paper_shadow_start=False")
print("exchange_order_submission=False")
print("approved_for_micro_live_execution=False")
print("approved_for_real_live_trading=False")
print(f"decision={decision}")
