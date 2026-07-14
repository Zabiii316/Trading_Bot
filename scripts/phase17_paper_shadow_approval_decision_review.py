import json, os, subprocess, time
from pathlib import Path

OUT = Path("data/processed/phase17_paper_shadow_approval_decision_review.json")
RUNTIME_OUT = Path("runtime/phase17_paper_shadow_approval_decision_review.json")
REVIEW_DIR = Path("data/processed/paper_shadow_approval_decision_review")

DECISION_INPUT = Path("data/processed/phase17_paper_shadow_approval_decision_point.json")
RUNTIME_DECISION = Path("runtime/phase17_paper_shadow_approval_decision_point.json")
START_ATTEMPT_REVIEW = Path("data/processed/phase17_paper_shadow_start_attempt_review.json")
HARNESS_STATE = Path("runtime/phase17_paper_shadow_state.json")

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

flags = {
    "BINANCE_TESTNET": os.getenv("BINANCE_TESTNET", ""),
    "BINANCE_USE_TESTNET": os.getenv("BINANCE_USE_TESTNET", ""),
    "BINANCE_ENABLE_LIVE_TRADING": os.getenv("BINANCE_ENABLE_LIVE_TRADING", ""),
    "LIVE_TRADING_ALLOWED": os.getenv("LIVE_TRADING_ALLOWED", ""),
}

safe_mode = flags["BINANCE_ENABLE_LIVE_TRADING"] == "false" and flags["LIVE_TRADING_ALLOWED"] == "false"

decision_report = load_json(DECISION_INPUT)
runtime_decision = load_json(RUNTIME_DECISION)
start_attempt = load_json(START_ATTEMPT_REVIEW)
harness_state = load_json(HARNESS_STATE)

decision_requested = decision_report.get("decision_requested") or runtime_decision.get("decision_requested")
manual_decision_status = decision_report.get("manual_decision_status") or runtime_decision.get("manual_decision_status")

manual_approval_provided = (
    decision_report.get("manual_approval_provided") is True
    or runtime_decision.get("manual_approval_provided") is True
)

approved_for_paper_shadow_start = (
    decision_report.get("approved_for_paper_shadow_start") is True
    or runtime_decision.get("approved_for_paper_shadow_start") is True
)

paper_shadow_started = (
    decision_report.get("paper_shadow_started") is True
    or runtime_decision.get("paper_shadow_started") is True
    or start_attempt.get("paper_shadow_started") is True
    or harness_state.get("paper_shadow_started") is True
)

exchange_order_submission = (
    decision_report.get("exchange_order_submission") is True
    or runtime_decision.get("exchange_order_submission") is True
    or start_attempt.get("exchange_order_submission") is True
    or harness_state.get("exchange_order_submission") is True
)

real_capital_allowed = (
    decision_report.get("real_capital_allowed") is True
    or runtime_decision.get("real_capital_allowed") is True
    or start_attempt.get("real_capital_allowed") is True
    or harness_state.get("real_capital_allowed") is True
)

live_trading_enabled = (
    decision_report.get("live_trading_enabled") is True
    or runtime_decision.get("live_trading_enabled") is True
    or start_attempt.get("live_trading_enabled") is True
    or harness_state.get("live_trading_enabled") is True
)

review_checks = {
    "safe_mode_active": safe_mode,
    "decision_input_present": DECISION_INPUT.exists(),
    "runtime_decision_present": RUNTIME_DECISION.exists(),
    "start_attempt_review_present": START_ATTEMPT_REVIEW.exists(),
    "harness_state_present": HARNESS_STATE.exists(),
    "paper_shadow_not_started": paper_shadow_started is False,
    "exchange_order_submission_disabled": exchange_order_submission is False,
    "real_capital_disabled": real_capital_allowed is False,
    "live_trading_disabled": live_trading_enabled is False,
    "micro_live_not_approved": decision_report.get("approved_for_micro_live_execution") is False,
    "real_live_not_approved": decision_report.get("approved_for_real_live_trading") is False,
}

blockers = [k for k, v in review_checks.items() if v is not True]

REVIEW_DIR.mkdir(parents=True, exist_ok=True)

if paper_shadow_started:
    decision = "PAPER_SHADOW_APPROVAL_DECISION_REVIEW_UNEXPECTED_STARTED_STATE_INVESTIGATION_REQUIRED"
    next_phase = "Phase 17.29 — Runtime State Investigation"
elif approved_for_paper_shadow_start:
    decision = "PAPER_SHADOW_APPROVAL_DECISION_REVIEW_COMPLETE_APPROVED_PAPER_SHADOW_ONLY_RECHECK_REQUIRED_NOT_STARTED"
    next_phase = "Phase 17.29 — Paper Shadow Safe Start Approval Recheck"
elif decision_requested == "reject":
    decision = "PAPER_SHADOW_APPROVAL_DECISION_REVIEW_COMPLETE_REJECTED_NOT_STARTED"
    next_phase = "Phase 17.29 — Paper Shadow Rejection Closeout"
else:
    decision = "PAPER_SHADOW_APPROVAL_DECISION_REVIEW_COMPLETE_HOLD_NOT_APPROVED_NOT_STARTED"
    next_phase = "Phase 17.29 — Paper Shadow Hold State Consolidation"

review_detail = {
    "created_at_unix": int(time.time()),
    "decision_requested": decision_requested,
    "manual_decision_status": manual_decision_status,
    "manual_approval_provided": manual_approval_provided,
    "approved_for_paper_shadow_start": approved_for_paper_shadow_start,
    "paper_shadow_started": False,
    "exchange_order_submission": False,
    "real_capital_allowed": False,
    "live_trading_enabled": False,
    "approved_for_micro_live_execution": False,
    "approved_for_real_live_trading": False,
    "review_checks": review_checks,
    "blockers": blockers,
    "decision": decision,
}

detail_file = REVIEW_DIR / "paper_shadow_approval_decision_review_detail.json"
write_json(detail_file, review_detail)

runtime_report = {
    "phase": "phase_17_28_paper_shadow_approval_decision_review_runtime",
    "updated_at_unix": int(time.time()),
    "decision_requested": decision_requested,
    "manual_approval_provided": manual_approval_provided,
    "approved_for_paper_shadow_start": approved_for_paper_shadow_start,
    "paper_shadow_started": False,
    "exchange_order_submission": False,
    "real_capital_allowed": False,
    "live_trading_enabled": False,
    "approved_for_micro_live_execution": False,
    "approved_for_real_live_trading": False,
    "blockers": blockers,
    "decision": decision,
}

write_json(RUNTIME_OUT, runtime_report)

report = {
    "phase": "phase_17_28_paper_shadow_approval_decision_review",
    "generated_at_unix": int(time.time()),
    "scope": "paper_shadow_approval_decision_review_only",
    "safety_flags": flags,
    "safe_mode_active": safe_mode,
    "git_working_tree_clean": git_clean(),
    "decision_requested": decision_requested,
    "manual_decision_status": manual_decision_status,
    "manual_approval_provided": manual_approval_provided,
    "approved_for_paper_shadow_start": approved_for_paper_shadow_start,
    "paper_shadow_started": False,
    "paper_shadow_completed": False,
    "exchange_order_submission": False,
    "real_capital_allowed": False,
    "live_trading_enabled": False,
    "approved_for_micro_live_execution": False,
    "approved_for_real_live_trading": False,
    "review_checks": review_checks,
    "blockers": blockers,
    "detail_file": str(detail_file),
    "runtime_review_file": str(RUNTIME_OUT),
    "decision": decision,
    "next_phase": next_phase,
    "safety_notes": [
        "This phase reviews the paper shadow approval decision only.",
        "This phase does not start paper shadow execution.",
        "This phase does not approve micro-live execution.",
        "This phase does not approve real live trading.",
        "This phase does not submit Binance orders.",
        "Real capital and exchange order submission remain disabled."
    ],
}

write_json(OUT, report)

print(f"Report written to: {OUT}")
print(f"Runtime review written to: {RUNTIME_OUT}")
print(f"safe_mode_active={safe_mode}")
print(f"decision_requested={decision_requested}")
print(f"manual_approval_provided={manual_approval_provided}")
print(f"approved_for_paper_shadow_start={approved_for_paper_shadow_start}")
print("paper_shadow_started=False")
print("exchange_order_submission=False")
print("approved_for_micro_live_execution=False")
print("approved_for_real_live_trading=False")
print(f"decision={decision}")
