import json, os, subprocess, time
from pathlib import Path

OUT = Path("data/processed/phase17_paper_shadow_blocked_start_review.json")
REVIEW_DIR = Path("data/processed/paper_shadow_blocked_start_review")

SAFE_START_INPUT = Path("data/processed/phase17_paper_shadow_safe_start_stub.json")
RUNTIME_SAFE_START = Path("runtime/phase17_paper_shadow_safe_start_stub.json")
READINESS_INPUT = Path("data/processed/phase17_paper_shadow_start_readiness_check.json")
RUNTIME_READINESS = Path("runtime/phase17_paper_shadow_start_readiness_check.json")
MANUAL_APPROVAL_INPUT = Path("data/processed/phase17_paper_shadow_manual_approval_record.json")
RUNTIME_MANUAL_APPROVAL = Path("runtime/phase17_paper_shadow_manual_approval_record.json")
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

safe_start = load_json(SAFE_START_INPUT)
runtime_safe_start = load_json(RUNTIME_SAFE_START)
readiness = load_json(READINESS_INPUT)
runtime_readiness = load_json(RUNTIME_READINESS)
manual_approval = load_json(MANUAL_APPROVAL_INPUT)
runtime_manual_approval = load_json(RUNTIME_MANUAL_APPROVAL)
harness_state = load_json(HARNESS_STATE)

start_checks = safe_start.get("start_checks", {})
runtime_start_checks = runtime_safe_start.get("start_checks", {})

blockers = safe_start.get("blockers", [])
runtime_blockers = runtime_safe_start.get("blockers", [])

combined_blockers = sorted(set(blockers + runtime_blockers))

paper_shadow_started = (
    safe_start.get("paper_shadow_started") is True
    or runtime_safe_start.get("paper_shadow_started") is True
    or harness_state.get("paper_shadow_started") is True
)

exchange_order_submission = (
    safe_start.get("exchange_order_submission") is True
    or runtime_safe_start.get("exchange_order_submission") is True
    or harness_state.get("exchange_order_submission") is True
)

real_capital_allowed = (
    safe_start.get("real_capital_allowed") is True
    or runtime_safe_start.get("real_capital_allowed") is True
    or harness_state.get("real_capital_allowed") is True
)

live_trading_enabled = (
    safe_start.get("live_trading_enabled") is True
    or runtime_safe_start.get("live_trading_enabled") is True
    or harness_state.get("live_trading_enabled") is True
)

manual_approval_record = manual_approval.get("approval_record", {})

manual_approval_provided = (
    manual_approval_record.get("manual_approval_provided") is True
    or manual_approval.get("manual_approval_provided") is True
    or runtime_manual_approval.get("manual_approval_provided") is True
)

approved_for_paper_shadow_start = (
    manual_approval.get("approved_for_paper_shadow_start") is True
    or runtime_manual_approval.get("approved_for_paper_shadow_start") is True
)

readiness_passed = (
    readiness.get("readiness_passed") is True
    or runtime_readiness.get("readiness_passed") is True
)

blocked_start_review = {
    "safe_start_input_present": SAFE_START_INPUT.exists(),
    "runtime_safe_start_present": RUNTIME_SAFE_START.exists(),
    "readiness_input_present": READINESS_INPUT.exists(),
    "runtime_readiness_present": RUNTIME_READINESS.exists(),
    "manual_approval_input_present": MANUAL_APPROVAL_INPUT.exists(),
    "runtime_manual_approval_present": RUNTIME_MANUAL_APPROVAL.exists(),
    "harness_state_present": HARNESS_STATE.exists(),
    "safe_mode_active": safe_mode,
    "paper_shadow_started": paper_shadow_started,
    "exchange_order_submission": exchange_order_submission,
    "real_capital_allowed": real_capital_allowed,
    "live_trading_enabled": live_trading_enabled,
    "manual_approval_provided": manual_approval_provided,
    "approved_for_paper_shadow_start": approved_for_paper_shadow_start,
    "readiness_passed": readiness_passed,
    "blocked_start_confirmed": paper_shadow_started is False and approved_for_paper_shadow_start is False,
}

blocker_categories = {
    "manual_approval_missing": (
        "manual_approval_provided" in combined_blockers
        or "approved_for_paper_shadow_start" in combined_blockers
        or manual_approval_provided is False
        or approved_for_paper_shadow_start is False
    ),
    "readiness_not_passed": (
        "readiness_passed" in combined_blockers
        or readiness_passed is False
    ),
    "safety_flags_not_safe": safe_mode is False,
    "paper_shadow_already_started": paper_shadow_started is True,
    "exchange_order_submission_enabled": exchange_order_submission is True,
    "real_capital_enabled": real_capital_allowed is True,
    "live_trading_enabled": live_trading_enabled is True,
}

REVIEW_DIR.mkdir(parents=True, exist_ok=True)

blocked_review_file = REVIEW_DIR / "paper_shadow_blocked_start_review_detail.json"

review_detail = {
    "created_at_unix": int(time.time()),
    "start_checks": start_checks,
    "runtime_start_checks": runtime_start_checks,
    "combined_blockers": combined_blockers,
    "blocker_categories": blocker_categories,
    "blocked_start_review": blocked_start_review,
    "recommended_next_action": "Create a paper-shadow-only manual approval update if you want to proceed to paper shadow testing. Do not enable real capital or exchange order submission.",
    "approved_for_paper_shadow_start": False,
    "approved_for_micro_live_execution": False,
    "approved_for_real_live_trading": False,
}

write_json(blocked_review_file, review_detail)

if blocker_categories["manual_approval_missing"]:
    decision = "PAPER_SHADOW_BLOCKED_START_REVIEW_COMPLETE_MANUAL_APPROVAL_REQUIRED_NOT_STARTED"
    next_phase = "Phase 17.24 — Paper Shadow Manual Approval Update Gate"
elif blocker_categories["safety_flags_not_safe"]:
    decision = "PAPER_SHADOW_BLOCKED_START_REVIEW_FAILED_SAFE_MODE_REQUIRED_NOT_STARTED"
    next_phase = "Phase 17.24 — Safety Flag Repair or Manual Approval Update Gate"
elif paper_shadow_started:
    decision = "PAPER_SHADOW_BLOCKED_START_REVIEW_UNEXPECTED_STARTED_STATE_DETECTED_INVESTIGATION_REQUIRED"
    next_phase = "Phase 17.24 — Runtime State Investigation"
else:
    decision = "PAPER_SHADOW_BLOCKED_START_REVIEW_COMPLETE_NO_APPROVAL_FOR_START_NOT_STARTED"
    next_phase = "Phase 17.24 — Paper Shadow Manual Approval Update Gate"

report = {
    "phase": "phase_17_23_paper_shadow_blocked_start_review",
    "generated_at_unix": int(time.time()),
    "scope": "paper_shadow_blocked_start_review_only",
    "safety_flags": flags,
    "safe_mode_active": safe_mode,
    "git_working_tree_clean": git_clean(),
    "blocked_start_review": blocked_start_review,
    "combined_blockers": combined_blockers,
    "blocker_categories": blocker_categories,
    "review_detail_file": str(blocked_review_file),
    "paper_shadow_started": False,
    "exchange_order_submission": False,
    "real_capital_allowed": False,
    "live_trading_enabled": False,
    "approved_for_paper_shadow_start": False,
    "approved_for_micro_live_execution": False,
    "approved_for_real_live_trading": False,
    "decision": decision,
    "next_phase": next_phase,
    "safety_notes": [
        "This phase reviews the blocked paper shadow start only.",
        "This phase does not approve paper shadow start.",
        "This phase does not start paper shadow execution.",
        "This phase does not approve micro-live execution.",
        "This phase does not approve real live trading.",
        "This phase does not submit Binance orders."
    ]
}

write_json(OUT, report)

print(f"Report written to: {OUT}")
print(f"Review detail written to: {blocked_review_file}")
print(f"safe_mode_active={safe_mode}")
print(f"manual_approval_provided={manual_approval_provided}")
print(f"approved_for_paper_shadow_start={approved_for_paper_shadow_start}")
print(f"readiness_passed={readiness_passed}")
print("paper_shadow_started=False")
print("exchange_order_submission=False")
print("approved_for_micro_live_execution=False")
print("approved_for_real_live_trading=False")
print(f"decision={decision}")
