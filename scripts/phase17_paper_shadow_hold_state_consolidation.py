import json, os, subprocess, time
from pathlib import Path

OUT = Path("data/processed/phase17_paper_shadow_hold_state_consolidation.json")
RUNTIME_OUT = Path("runtime/phase17_paper_shadow_hold_state.json")
HOLD_DIR = Path("data/processed/paper_shadow_hold_state")

DECISION_REVIEW = Path("data/processed/phase17_paper_shadow_approval_decision_review.json")
RUNTIME_DECISION_REVIEW = Path("runtime/phase17_paper_shadow_approval_decision_review.json")
DECISION_POINT = Path("data/processed/phase17_paper_shadow_approval_decision_point.json")
HARNESS_STATE = Path("runtime/phase17_paper_shadow_state.json")
SAFE_START_STUB = Path("runtime/phase17_paper_shadow_safe_start_stub.json")

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

decision_review = load_json(DECISION_REVIEW)
runtime_decision_review = load_json(RUNTIME_DECISION_REVIEW)
decision_point = load_json(DECISION_POINT)
harness_state = load_json(HARNESS_STATE)
safe_start_stub = load_json(SAFE_START_STUB)

decision_requested = (
    decision_review.get("decision_requested")
    or runtime_decision_review.get("decision_requested")
    or decision_point.get("decision_requested")
)

manual_approval_provided = (
    decision_review.get("manual_approval_provided") is True
    or runtime_decision_review.get("manual_approval_provided") is True
    or decision_point.get("manual_approval_provided") is True
)

approved_for_paper_shadow_start = (
    decision_review.get("approved_for_paper_shadow_start") is True
    or runtime_decision_review.get("approved_for_paper_shadow_start") is True
    or decision_point.get("approved_for_paper_shadow_start") is True
)

paper_shadow_started = (
    decision_review.get("paper_shadow_started") is True
    or runtime_decision_review.get("paper_shadow_started") is True
    or harness_state.get("paper_shadow_started") is True
    or safe_start_stub.get("paper_shadow_started") is True
)

exchange_order_submission = (
    decision_review.get("exchange_order_submission") is True
    or runtime_decision_review.get("exchange_order_submission") is True
    or harness_state.get("exchange_order_submission") is True
    or safe_start_stub.get("exchange_order_submission") is True
)

real_capital_allowed = (
    decision_review.get("real_capital_allowed") is True
    or runtime_decision_review.get("real_capital_allowed") is True
    or harness_state.get("real_capital_allowed") is True
    or safe_start_stub.get("real_capital_allowed") is True
)

live_trading_enabled = (
    decision_review.get("live_trading_enabled") is True
    or runtime_decision_review.get("live_trading_enabled") is True
    or harness_state.get("live_trading_enabled") is True
    or safe_start_stub.get("live_trading_enabled") is True
)

hold_checks = {
    "safe_mode_active": safe_mode,
    "decision_review_present": DECISION_REVIEW.exists(),
    "runtime_decision_review_present": RUNTIME_DECISION_REVIEW.exists(),
    "decision_point_present": DECISION_POINT.exists(),
    "harness_state_present": HARNESS_STATE.exists(),
    "safe_start_stub_present": SAFE_START_STUB.exists(),
    "decision_requested_hold": decision_requested == "hold",
    "manual_approval_not_provided": manual_approval_provided is False,
    "paper_shadow_start_not_approved": approved_for_paper_shadow_start is False,
    "paper_shadow_not_started": paper_shadow_started is False,
    "exchange_order_submission_disabled": exchange_order_submission is False,
    "real_capital_disabled": real_capital_allowed is False,
    "live_trading_disabled": live_trading_enabled is False,
}

blockers = [k for k, v in hold_checks.items() if v is not True]
hold_state_confirmed = all(hold_checks.values())

HOLD_DIR.mkdir(parents=True, exist_ok=True)

if hold_state_confirmed:
    decision = "PAPER_SHADOW_HOLD_STATE_CONSOLIDATED_NOT_APPROVED_NOT_STARTED"
    next_phase = "Phase 17.30 — Phase 17 Safety Closeout and Next Action Options"
elif approved_for_paper_shadow_start:
    decision = "PAPER_SHADOW_HOLD_STATE_CONSOLIDATION_APPROVAL_DETECTED_RECHECK_REQUIRED"
    next_phase = "Phase 17.30 — Paper Shadow Approval Recheck"
elif not safe_mode:
    decision = "PAPER_SHADOW_HOLD_STATE_CONSOLIDATION_FAILED_SAFE_MODE_REQUIRED"
    next_phase = "Phase 17.30 — Safety Flag Repair"
else:
    decision = "PAPER_SHADOW_HOLD_STATE_CONSOLIDATION_INCOMPLETE_REVIEW_REQUIRED"
    next_phase = "Phase 17.30 — Hold State Review"

hold_lock = {
    "phase": "phase_17_29_paper_shadow_hold_state_lock",
    "created_at_unix": int(time.time()),
    "hold_state_confirmed": hold_state_confirmed,
    "decision_requested": decision_requested,
    "manual_approval_provided": manual_approval_provided,
    "approved_for_paper_shadow_start": approved_for_paper_shadow_start,
    "paper_shadow_started": False,
    "paper_shadow_completed": False,
    "exchange_order_submission": False,
    "real_capital_allowed": False,
    "live_trading_enabled": False,
    "approved_for_micro_live_execution": False,
    "approved_for_real_live_trading": False,
    "hold_checks": hold_checks,
    "blockers": blockers,
    "decision": decision,
}

hold_lock_file = HOLD_DIR / "paper_shadow_hold_state_lock.json"
write_json(hold_lock_file, hold_lock)
write_json(RUNTIME_OUT, hold_lock)

report = {
    "phase": "phase_17_29_paper_shadow_hold_state_consolidation",
    "generated_at_unix": int(time.time()),
    "scope": "paper_shadow_hold_state_consolidation_only",
    "safety_flags": flags,
    "safe_mode_active": safe_mode,
    "git_working_tree_clean": git_clean(),
    "decision_requested": decision_requested,
    "manual_approval_provided": manual_approval_provided,
    "approved_for_paper_shadow_start": approved_for_paper_shadow_start,
    "hold_state_confirmed": hold_state_confirmed,
    "hold_checks": hold_checks,
    "blockers": blockers,
    "paper_shadow_started": False,
    "paper_shadow_completed": False,
    "exchange_order_submission": False,
    "real_capital_allowed": False,
    "live_trading_enabled": False,
    "approved_for_micro_live_execution": False,
    "approved_for_real_live_trading": False,
    "hold_lock_file": str(hold_lock_file),
    "runtime_hold_state_file": str(RUNTIME_OUT),
    "decision": decision,
    "next_phase": next_phase,
    "safety_notes": [
        "This phase consolidates hold state only.",
        "This phase does not start paper shadow execution.",
        "This phase does not approve paper shadow start.",
        "This phase does not approve micro-live execution.",
        "This phase does not approve real live trading.",
        "This phase does not submit Binance orders.",
        "Real capital and exchange order submission remain disabled."
    ],
}

write_json(OUT, report)

print(f"Report written to: {OUT}")
print(f"Runtime hold state written to: {RUNTIME_OUT}")
print(f"safe_mode_active={safe_mode}")
print(f"decision_requested={decision_requested}")
print(f"manual_approval_provided={manual_approval_provided}")
print(f"approved_for_paper_shadow_start={approved_for_paper_shadow_start}")
print(f"hold_state_confirmed={hold_state_confirmed}")
print("paper_shadow_started=False")
print("exchange_order_submission=False")
print("approved_for_micro_live_execution=False")
print("approved_for_real_live_trading=False")
print(f"decision={decision}")
