import json, os, subprocess, time
from pathlib import Path

OUT = Path("data/processed/phase17_safety_closeout_next_action_options.json")
RUNTIME_OUT = Path("runtime/phase17_safety_closeout_state.json")
CLOSEOUT_DIR = Path("data/processed/phase17_closeout")

HOLD_STATE = Path("data/processed/phase17_paper_shadow_hold_state_consolidation.json")
RUNTIME_HOLD_STATE = Path("runtime/phase17_paper_shadow_hold_state.json")
DECISION_REVIEW = Path("data/processed/phase17_paper_shadow_approval_decision_review.json")
FINAL_CANDIDATE_REVIEW = Path("data/processed/phase17_final_strategy_candidate_review.json")
STRESS_REVIEW = Path("data/processed/phase17_stress_test_results_review.json")
OOS_REVIEW = Path("data/processed/phase17_oos_results_review_overfitting_check.json")

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

def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2))

def bool_any_true(*values):
    return any(v is True for v in values)

flags = {
    "BINANCE_TESTNET": os.getenv("BINANCE_TESTNET", ""),
    "BINANCE_USE_TESTNET": os.getenv("BINANCE_USE_TESTNET", ""),
    "BINANCE_ENABLE_LIVE_TRADING": os.getenv("BINANCE_ENABLE_LIVE_TRADING", ""),
    "LIVE_TRADING_ALLOWED": os.getenv("LIVE_TRADING_ALLOWED", ""),
}

safe_mode = flags["BINANCE_ENABLE_LIVE_TRADING"] == "false" and flags["LIVE_TRADING_ALLOWED"] == "false"

hold = load_json(HOLD_STATE)
runtime_hold = load_json(RUNTIME_HOLD_STATE)
decision_review = load_json(DECISION_REVIEW)
final_candidate_review = load_json(FINAL_CANDIDATE_REVIEW)
stress_review = load_json(STRESS_REVIEW)
oos_review = load_json(OOS_REVIEW)

phase17_evidence_files = sorted(str(p) for p in Path("data/processed").glob("phase17_*.json"))

hold_state_confirmed = (
    hold.get("hold_state_confirmed") is True
    or runtime_hold.get("hold_state_confirmed") is True
)

paper_shadow_started = bool_any_true(
    hold.get("paper_shadow_started"),
    runtime_hold.get("paper_shadow_started"),
    decision_review.get("paper_shadow_started")
)

approved_for_paper_shadow_start = bool_any_true(
    hold.get("approved_for_paper_shadow_start"),
    runtime_hold.get("approved_for_paper_shadow_start"),
    decision_review.get("approved_for_paper_shadow_start")
)

approved_for_micro_live_execution = bool_any_true(
    hold.get("approved_for_micro_live_execution"),
    runtime_hold.get("approved_for_micro_live_execution"),
    decision_review.get("approved_for_micro_live_execution")
)

approved_for_real_live_trading = bool_any_true(
    hold.get("approved_for_real_live_trading"),
    runtime_hold.get("approved_for_real_live_trading"),
    decision_review.get("approved_for_real_live_trading")
)

exchange_order_submission = bool_any_true(
    hold.get("exchange_order_submission"),
    runtime_hold.get("exchange_order_submission"),
    decision_review.get("exchange_order_submission")
)

real_capital_allowed = bool_any_true(
    hold.get("real_capital_allowed"),
    runtime_hold.get("real_capital_allowed"),
    decision_review.get("real_capital_allowed")
)

live_trading_enabled = bool_any_true(
    hold.get("live_trading_enabled"),
    runtime_hold.get("live_trading_enabled"),
    decision_review.get("live_trading_enabled")
)

final_candidate_count = int(final_candidate_review.get("final_candidate_count", 0) or 0)
stress_forward_count = int(stress_review.get("forward_candidate_count", 0) or 0)
oos_forward_count = int(oos_review.get("forward_candidate_count", 0) or 0)

closeout_checks = {
    "safe_mode_active": safe_mode,
    "hold_state_input_present": HOLD_STATE.exists(),
    "runtime_hold_state_present": RUNTIME_HOLD_STATE.exists(),
    "hold_state_confirmed": hold_state_confirmed,
    "paper_shadow_not_started": paper_shadow_started is False,
    "paper_shadow_start_not_approved": approved_for_paper_shadow_start is False,
    "micro_live_not_approved": approved_for_micro_live_execution is False,
    "real_live_not_approved": approved_for_real_live_trading is False,
    "exchange_order_submission_disabled": exchange_order_submission is False,
    "real_capital_disabled": real_capital_allowed is False,
    "live_trading_disabled": live_trading_enabled is False,
}

blockers = [k for k, v in closeout_checks.items() if v is not True]
phase17_closed_safely = all(closeout_checks.values())

next_action_options = [
    {
        "option": "remain_on_hold",
        "description": "Keep the system in hold state. No paper shadow, no micro-live, no real live trading.",
        "requires_manual_approval": False,
        "execution_allowed": False
    },
    {
        "option": "paper_shadow_only_approval_path",
        "description": "Use a separate paper-shadow-only manual approval flow, with real capital and exchange order submission still disabled.",
        "requires_manual_approval": True,
        "execution_allowed": False
    },
    {
        "option": "strategy_rework_path",
        "description": "Return to strategy rework, parameter sweep, OOS validation, and stress testing before any future paper shadow decision.",
        "requires_manual_approval": False,
        "execution_allowed": False
    },
    {
        "option": "expand_historical_data_path",
        "description": "Add more historical symbols and longer datasets before repeating Phase 17 strategy validation.",
        "requires_manual_approval": False,
        "execution_allowed": False
    },
    {
        "option": "monitoring_dashboard_review",
        "description": "Review dashboards and monitoring health while keeping trading disabled.",
        "requires_manual_approval": False,
        "execution_allowed": False
    }
]

CLOSEOUT_DIR.mkdir(parents=True, exist_ok=True)

closeout_summary = {
    "created_at_unix": int(time.time()),
    "phase17_closed_safely": phase17_closed_safely,
    "safe_mode_active": safe_mode,
    "hold_state_confirmed": hold_state_confirmed,
    "paper_shadow_started": False,
    "approved_for_paper_shadow_start": False,
    "approved_for_micro_live_execution": False,
    "approved_for_real_live_trading": False,
    "exchange_order_submission": False,
    "real_capital_allowed": False,
    "live_trading_enabled": False,
    "final_candidate_count": final_candidate_count,
    "oos_forward_candidate_count": oos_forward_count,
    "stress_forward_candidate_count": stress_forward_count,
    "phase17_evidence_file_count": len(phase17_evidence_files),
    "phase17_evidence_files": phase17_evidence_files,
    "next_action_options": next_action_options,
    "blockers": blockers,
}

summary_file = CLOSEOUT_DIR / "phase17_safety_closeout_summary.json"
write_json(summary_file, closeout_summary)
write_json(RUNTIME_OUT, closeout_summary)

if phase17_closed_safely:
    decision = "PHASE_17_SAFETY_CLOSEOUT_COMPLETE_HOLD_STATE_NOT_APPROVED_NOT_STARTED"
    next_phase = "Phase 18.1 — Next Action Selection"
else:
    decision = "PHASE_17_SAFETY_CLOSEOUT_INCOMPLETE_REVIEW_REQUIRED"
    next_phase = "Phase 18.1 — Safety Closeout Review"

report = {
    "phase": "phase_17_30_safety_closeout_next_action_options",
    "generated_at_unix": int(time.time()),
    "scope": "phase_17_safety_closeout_and_next_action_options_only",
    "safety_flags": flags,
    "safe_mode_active": safe_mode,
    "git_working_tree_clean": git_clean(),
    "closeout_checks": closeout_checks,
    "blockers": blockers,
    "phase17_closed_safely": phase17_closed_safely,
    "hold_state_confirmed": hold_state_confirmed,
    "paper_shadow_started": False,
    "paper_shadow_completed": False,
    "approved_for_paper_shadow_start": False,
    "approved_for_micro_live_execution": False,
    "approved_for_real_live_trading": False,
    "exchange_order_submission": False,
    "real_capital_allowed": False,
    "live_trading_enabled": False,
    "final_candidate_count": final_candidate_count,
    "oos_forward_candidate_count": oos_forward_count,
    "stress_forward_candidate_count": stress_forward_count,
    "phase17_evidence_file_count": len(phase17_evidence_files),
    "summary_file": str(summary_file),
    "runtime_closeout_file": str(RUNTIME_OUT),
    "next_action_options": next_action_options,
    "decision": decision,
    "next_phase": next_phase,
    "safety_notes": [
        "This phase closes Phase 17 in a safe hold state.",
        "This phase does not approve paper shadow start.",
        "This phase does not approve micro-live execution.",
        "This phase does not approve real live trading.",
        "This phase does not submit Binance orders.",
        "Real capital and exchange order submission remain disabled."
    ],
}

write_json(OUT, report)

print(f"Report written to: {OUT}")
print(f"Runtime closeout written to: {RUNTIME_OUT}")
print(f"Summary written to: {summary_file}")
print(f"safe_mode_active={safe_mode}")
print(f"hold_state_confirmed={hold_state_confirmed}")
print(f"phase17_closed_safely={phase17_closed_safely}")
print("paper_shadow_started=False")
print("approved_for_paper_shadow_start=False")
print("exchange_order_submission=False")
print("approved_for_micro_live_execution=False")
print("approved_for_real_live_trading=False")
print(f"decision={decision}")
