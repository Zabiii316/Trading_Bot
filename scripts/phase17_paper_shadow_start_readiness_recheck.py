import json, os, subprocess, time
from pathlib import Path

OUT = Path("data/processed/phase17_paper_shadow_start_readiness_recheck.json")
RUNTIME_OUT = Path("runtime/phase17_paper_shadow_start_readiness_recheck.json")
RECHECK_DIR = Path("data/processed/paper_shadow_readiness_recheck")

HARNESS_STATE = Path("runtime/phase17_paper_shadow_state.json")
HARNESS_INPUT = Path("data/processed/phase17_paper_shadow_execution_harness.json")
ORIGINAL_READINESS = Path("data/processed/phase17_paper_shadow_start_readiness_check.json")
SAFE_START_STUB = Path("data/processed/phase17_paper_shadow_safe_start_stub.json")
BLOCKED_REVIEW = Path("data/processed/phase17_paper_shadow_blocked_start_review.json")
APPROVAL_UPDATE = Path("data/processed/phase17_paper_shadow_manual_approval_update_gate.json")
RUNTIME_APPROVAL_UPDATE = Path("runtime/phase17_paper_shadow_manual_approval_update_gate.json")

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

harness_state = load_json(HARNESS_STATE)
harness_input = load_json(HARNESS_INPUT)
original_readiness = load_json(ORIGINAL_READINESS)
safe_start_stub = load_json(SAFE_START_STUB)
blocked_review = load_json(BLOCKED_REVIEW)
approval_update = load_json(APPROVAL_UPDATE)
runtime_approval_update = load_json(RUNTIME_APPROVAL_UPDATE)

harness_session_count = int(harness_input.get("harness_session_count", 0) or 0)

manual_approval_provided = (
    approval_update.get("manual_approval_provided") is True
    or runtime_approval_update.get("manual_approval_provided") is True
)

approved_for_paper_shadow_start = (
    approval_update.get("approved_for_paper_shadow_start") is True
    or runtime_approval_update.get("approved_for_paper_shadow_start") is True
)

recheck_checks = {
    "safe_mode_active": safe_mode,
    "harness_state_present": HARNESS_STATE.exists(),
    "harness_input_present": HARNESS_INPUT.exists(),
    "original_readiness_present": ORIGINAL_READINESS.exists(),
    "safe_start_stub_present": SAFE_START_STUB.exists(),
    "blocked_review_present": BLOCKED_REVIEW.exists(),
    "approval_update_present": APPROVAL_UPDATE.exists(),
    "runtime_approval_update_present": RUNTIME_APPROVAL_UPDATE.exists(),
    "harness_sessions_available": harness_session_count > 0,
    "paper_shadow_not_started": harness_state.get("paper_shadow_started") is not True,
    "paper_shadow_not_completed": harness_state.get("paper_shadow_completed") is not True,
    "exchange_order_submission_disabled": harness_state.get("exchange_order_submission") is False,
    "real_capital_disabled": harness_state.get("real_capital_allowed") is False,
    "live_trading_disabled": harness_state.get("live_trading_enabled") is False,
    "manual_approval_provided": manual_approval_provided,
    "approved_for_paper_shadow_start": approved_for_paper_shadow_start,
    "micro_live_not_approved": approval_update.get("approved_for_micro_live_execution") is False,
    "real_live_not_approved": approval_update.get("approved_for_real_live_trading") is False,
}

blockers = [k for k, v in recheck_checks.items() if v is not True]
readiness_recheck_passed = all(recheck_checks.values())

RECHECK_DIR.mkdir(parents=True, exist_ok=True)

recheck_detail = {
    "created_at_unix": int(time.time()),
    "recheck_checks": recheck_checks,
    "blockers": blockers,
    "manual_approval_provided": manual_approval_provided,
    "approved_for_paper_shadow_start": approved_for_paper_shadow_start,
    "readiness_recheck_passed": readiness_recheck_passed,
    "paper_shadow_started": False,
    "exchange_order_submission": False,
    "real_capital_allowed": False,
    "live_trading_enabled": False,
    "approved_for_micro_live_execution": False,
    "approved_for_real_live_trading": False,
}

detail_file = RECHECK_DIR / "paper_shadow_start_readiness_recheck_detail.json"
write_json(detail_file, recheck_detail)

if harness_session_count <= 0:
    decision = "PAPER_SHADOW_START_READINESS_RECHECK_SKIPPED_NO_HARNESS_SESSIONS_STRATEGY_REWORK_REQUIRED"
    next_phase = "Phase 17.26 — Paper Shadow Start Attempt Review or Strategy Redesign"
elif readiness_recheck_passed:
    decision = "PAPER_SHADOW_START_READINESS_RECHECK_PASSED_SAFE_START_ACTION_REQUIRED_NOT_STARTED"
    next_phase = "Phase 17.26 — Paper Shadow Approved Safe Start Stub"
else:
    decision = "PAPER_SHADOW_START_READINESS_RECHECK_FAILED_APPROVAL_REQUIRED_NOT_STARTED"
    next_phase = "Phase 17.26 — Paper Shadow Start Attempt Review"

runtime_report = {
    "phase": "phase_17_25_paper_shadow_start_readiness_recheck_runtime",
    "updated_at_unix": int(time.time()),
    "readiness_recheck_passed": readiness_recheck_passed,
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
    "phase": "phase_17_25_paper_shadow_start_readiness_recheck",
    "generated_at_unix": int(time.time()),
    "scope": "paper_shadow_start_readiness_recheck_only",
    "safety_flags": flags,
    "safe_mode_active": safe_mode,
    "git_working_tree_clean": git_clean(),
    "harness_session_count": harness_session_count,
    "manual_approval_provided": manual_approval_provided,
    "approved_for_paper_shadow_start": approved_for_paper_shadow_start,
    "readiness_recheck_passed": readiness_recheck_passed,
    "recheck_checks": recheck_checks,
    "blockers": blockers,
    "detail_file": str(detail_file),
    "runtime_recheck_file": str(RUNTIME_OUT),
    "paper_shadow_started": False,
    "exchange_order_submission": False,
    "real_capital_allowed": False,
    "live_trading_enabled": False,
    "approved_for_micro_live_execution": False,
    "approved_for_real_live_trading": False,
    "decision": decision,
    "next_phase": next_phase,
    "safety_notes": [
        "This phase rechecks paper shadow start readiness only.",
        "This phase does not start paper shadow execution.",
        "This phase does not approve micro-live execution.",
        "This phase does not approve real live trading.",
        "This phase does not submit Binance orders.",
        "Paper shadow remains blocked unless paper-shadow-only approval is present."
    ],
}

write_json(OUT, report)

print(f"Report written to: {OUT}")
print(f"Runtime recheck written to: {RUNTIME_OUT}")
print(f"safe_mode_active={safe_mode}")
print(f"harness_session_count={harness_session_count}")
print(f"manual_approval_provided={manual_approval_provided}")
print(f"approved_for_paper_shadow_start={approved_for_paper_shadow_start}")
print(f"readiness_recheck_passed={readiness_recheck_passed}")
print("paper_shadow_started=False")
print("exchange_order_submission=False")
print("approved_for_micro_live_execution=False")
print("approved_for_real_live_trading=False")
print(f"decision={decision}")
