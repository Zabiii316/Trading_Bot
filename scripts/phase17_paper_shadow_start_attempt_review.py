import json, os, subprocess, time
from pathlib import Path

OUT = Path("data/processed/phase17_paper_shadow_start_attempt_review.json")
RUNTIME_OUT = Path("runtime/phase17_paper_shadow_start_attempt_review.json")
REVIEW_DIR = Path("data/processed/paper_shadow_start_attempt_review")

RECHECK_INPUT = Path("data/processed/phase17_paper_shadow_start_readiness_recheck.json")
RUNTIME_RECHECK = Path("runtime/phase17_paper_shadow_start_readiness_recheck.json")
SAFE_START_INPUT = Path("data/processed/phase17_paper_shadow_safe_start_stub.json")
RUNTIME_SAFE_START = Path("runtime/phase17_paper_shadow_safe_start_stub.json")
APPROVAL_UPDATE = Path("runtime/phase17_paper_shadow_manual_approval_update_gate.json")
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

recheck = load_json(RECHECK_INPUT)
runtime_recheck = load_json(RUNTIME_RECHECK)
safe_start = load_json(SAFE_START_INPUT)
runtime_safe_start = load_json(RUNTIME_SAFE_START)
approval_update = load_json(APPROVAL_UPDATE)
harness_state = load_json(HARNESS_STATE)

readiness_recheck_passed = (
    recheck.get("readiness_recheck_passed") is True
    or runtime_recheck.get("readiness_recheck_passed") is True
)

manual_approval_provided = (
    recheck.get("manual_approval_provided") is True
    or runtime_recheck.get("manual_approval_provided") is True
    or approval_update.get("manual_approval_provided") is True
)

approved_for_paper_shadow_start = (
    recheck.get("approved_for_paper_shadow_start") is True
    or runtime_recheck.get("approved_for_paper_shadow_start") is True
    or approval_update.get("approved_for_paper_shadow_start") is True
)

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

review_checks = {
    "safe_mode_active": safe_mode,
    "recheck_input_present": RECHECK_INPUT.exists(),
    "runtime_recheck_present": RUNTIME_RECHECK.exists(),
    "safe_start_input_present": SAFE_START_INPUT.exists(),
    "runtime_safe_start_present": RUNTIME_SAFE_START.exists(),
    "approval_update_present": APPROVAL_UPDATE.exists(),
    "harness_state_present": HARNESS_STATE.exists(),
    "readiness_recheck_passed": readiness_recheck_passed,
    "manual_approval_provided": manual_approval_provided,
    "approved_for_paper_shadow_start": approved_for_paper_shadow_start,
    "paper_shadow_not_started": paper_shadow_started is False,
    "exchange_order_submission_disabled": exchange_order_submission is False,
    "real_capital_disabled": real_capital_allowed is False,
    "live_trading_disabled": live_trading_enabled is False,
}

blockers = [k for k, v in review_checks.items() if v is not True]

start_attempt_allowed = all(review_checks.values())
start_attempt_blocked = not start_attempt_allowed

REVIEW_DIR.mkdir(parents=True, exist_ok=True)

review_detail = {
    "created_at_unix": int(time.time()),
    "review_checks": review_checks,
    "blockers": blockers,
    "readiness_recheck_passed": readiness_recheck_passed,
    "manual_approval_provided": manual_approval_provided,
    "approved_for_paper_shadow_start": approved_for_paper_shadow_start,
    "start_attempt_allowed": False,
    "start_attempt_blocked": start_attempt_blocked,
    "paper_shadow_started": False,
    "exchange_order_submission": False,
    "real_capital_allowed": False,
    "live_trading_enabled": False,
    "approved_for_micro_live_execution": False,
    "approved_for_real_live_trading": False,
}

detail_file = REVIEW_DIR / "paper_shadow_start_attempt_review_detail.json"
write_json(detail_file, review_detail)

if paper_shadow_started:
    decision = "PAPER_SHADOW_START_ATTEMPT_REVIEW_UNEXPECTED_STARTED_STATE_INVESTIGATION_REQUIRED"
    next_phase = "Phase 17.27 — Runtime State Investigation"
elif start_attempt_allowed:
    decision = "PAPER_SHADOW_START_ATTEMPT_REVIEW_READY_BUT_ACTUAL_START_NOT_EXECUTED"
    next_phase = "Phase 17.27 — Paper Shadow Approved Start Stub"
else:
    decision = "PAPER_SHADOW_START_ATTEMPT_REVIEW_COMPLETE_START_BLOCKED_APPROVAL_REQUIRED_NOT_STARTED"
    next_phase = "Phase 17.27 — Paper Shadow Approval Decision Point"

runtime_report = {
    "phase": "phase_17_26_paper_shadow_start_attempt_review_runtime",
    "updated_at_unix": int(time.time()),
    "start_attempt_allowed": False,
    "start_attempt_blocked": start_attempt_blocked,
    "paper_shadow_started": False,
    "exchange_order_submission": False,
    "real_capital_allowed": False,
    "live_trading_enabled": False,
    "approved_for_paper_shadow_start": False,
    "approved_for_micro_live_execution": False,
    "approved_for_real_live_trading": False,
    "blockers": blockers,
    "decision": decision,
}

write_json(RUNTIME_OUT, runtime_report)

report = {
    "phase": "phase_17_26_paper_shadow_start_attempt_review",
    "generated_at_unix": int(time.time()),
    "scope": "paper_shadow_start_attempt_review_only",
    "safety_flags": flags,
    "safe_mode_active": safe_mode,
    "git_working_tree_clean": git_clean(),
    "review_checks": review_checks,
    "blockers": blockers,
    "start_attempt_allowed": False,
    "start_attempt_blocked": start_attempt_blocked,
    "paper_shadow_started": False,
    "exchange_order_submission": False,
    "real_capital_allowed": False,
    "live_trading_enabled": False,
    "approved_for_paper_shadow_start": False,
    "approved_for_micro_live_execution": False,
    "approved_for_real_live_trading": False,
    "detail_file": str(detail_file),
    "runtime_review_file": str(RUNTIME_OUT),
    "decision": decision,
    "next_phase": next_phase,
    "safety_notes": [
        "This phase reviews the paper shadow start attempt only.",
        "This phase does not start paper shadow execution.",
        "This phase does not approve paper shadow start.",
        "This phase does not approve micro-live execution.",
        "This phase does not approve real live trading.",
        "This phase does not submit Binance orders."
    ],
}

write_json(OUT, report)

print(f"Report written to: {OUT}")
print(f"Runtime review written to: {RUNTIME_OUT}")
print(f"safe_mode_active={safe_mode}")
print(f"readiness_recheck_passed={readiness_recheck_passed}")
print(f"manual_approval_provided={manual_approval_provided}")
print(f"approved_for_paper_shadow_start={approved_for_paper_shadow_start}")
print("start_attempt_allowed=False")
print("paper_shadow_started=False")
print("exchange_order_submission=False")
print("approved_for_micro_live_execution=False")
print("approved_for_real_live_trading=False")
print(f"decision={decision}")
