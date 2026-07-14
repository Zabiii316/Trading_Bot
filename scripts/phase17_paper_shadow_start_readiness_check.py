import json, os, subprocess, time
from pathlib import Path

OUT = Path("data/processed/phase17_paper_shadow_start_readiness_check.json")
RUNTIME_OUT = Path("runtime/phase17_paper_shadow_start_readiness_check.json")
READINESS_DIR = Path("data/processed/paper_shadow_readiness")

HARNESS_INPUT = Path("data/processed/phase17_paper_shadow_execution_harness.json")
HARNESS_STATE = Path("runtime/phase17_paper_shadow_state.json")
START_GATE_INPUT = Path("data/processed/phase17_paper_shadow_start_gate.json")
RUNTIME_GATE = Path("runtime/phase17_paper_shadow_start_gate.json")
MANUAL_APPROVAL_INPUT = Path("data/processed/phase17_paper_shadow_manual_approval_record.json")
RUNTIME_APPROVAL = Path("runtime/phase17_paper_shadow_manual_approval_record.json")

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

harness = load_json(HARNESS_INPUT)
harness_state = load_json(HARNESS_STATE)
start_gate = load_json(START_GATE_INPUT)
runtime_gate = load_json(RUNTIME_GATE)
approval = load_json(MANUAL_APPROVAL_INPUT)
runtime_approval = load_json(RUNTIME_APPROVAL)

harness_session_count = int(harness.get("harness_session_count", 0) or 0)

approval_record = approval.get("approval_record", {})
runtime_manual_approval = runtime_approval.get("manual_approval_provided") is True
runtime_paper_shadow_approved = runtime_approval.get("approved_for_paper_shadow_start") is True

readiness_checks = {
    "safe_mode_active": safe_mode,
    "harness_input_present": HARNESS_INPUT.exists(),
    "harness_state_present": HARNESS_STATE.exists(),
    "start_gate_input_present": START_GATE_INPUT.exists(),
    "runtime_gate_present": RUNTIME_GATE.exists(),
    "manual_approval_input_present": MANUAL_APPROVAL_INPUT.exists(),
    "runtime_approval_present": RUNTIME_APPROVAL.exists(),
    "harness_sessions_available": harness_session_count > 0,
    "paper_shadow_not_started": harness_state.get("paper_shadow_started") is not True,
    "paper_shadow_not_completed": harness_state.get("paper_shadow_completed") is not True,
    "exchange_order_submission_disabled": harness_state.get("exchange_order_submission") is False,
    "real_capital_disabled": harness_state.get("real_capital_allowed") is False,
    "live_trading_disabled": harness_state.get("live_trading_enabled") is False,
    "micro_live_not_approved": approval.get("approved_for_micro_live_execution") is False,
    "real_live_not_approved": approval.get("approved_for_real_live_trading") is False,
    "manual_approval_provided": approval_record.get("manual_approval_provided") is True or runtime_manual_approval,
    "approved_for_paper_shadow_start": approval.get("approved_for_paper_shadow_start") is True or runtime_paper_shadow_approved,
}

readiness_passed = all(readiness_checks.values())

blockers = []
for key, value in readiness_checks.items():
    if value is not True:
        blockers.append(key)

READINESS_DIR.mkdir(parents=True, exist_ok=True)

if harness_session_count <= 0:
    decision = "PAPER_SHADOW_START_READINESS_CHECK_SKIPPED_NO_HARNESS_SESSIONS_STRATEGY_REWORK_REQUIRED"
    next_phase = "Phase 17.22 — Paper Shadow Start Stub or Strategy Redesign"
elif readiness_passed:
    decision = "PAPER_SHADOW_START_READINESS_CHECK_PASSED_MANUAL_START_ACTION_REQUIRED_NOT_STARTED"
    next_phase = "Phase 17.22 — Paper Shadow Safe Start Stub"
else:
    decision = "PAPER_SHADOW_START_READINESS_CHECK_FAILED_MANUAL_APPROVAL_REQUIRED_NOT_STARTED"
    next_phase = "Phase 17.22 — Paper Shadow Safe Start Stub or Manual Approval Update"

runtime_report = {
    "phase": "phase_17_21_paper_shadow_start_readiness_runtime",
    "updated_at_unix": int(time.time()),
    "readiness_passed": readiness_passed,
    "paper_shadow_started": False,
    "approved_for_paper_shadow_start": False,
    "approved_for_micro_live_execution": False,
    "approved_for_real_live_trading": False,
    "blockers": blockers,
    "decision": decision
}

write_json(RUNTIME_OUT, runtime_report)

report = {
    "phase": "phase_17_21_paper_shadow_start_readiness_check",
    "generated_at_unix": int(time.time()),
    "scope": "paper_shadow_start_readiness_check_only",
    "safety_flags": flags,
    "safe_mode_active": safe_mode,
    "git_working_tree_clean": git_clean(),
    "inputs_present": {
        "harness_input": HARNESS_INPUT.exists(),
        "harness_state": HARNESS_STATE.exists(),
        "start_gate_input": START_GATE_INPUT.exists(),
        "runtime_gate": RUNTIME_GATE.exists(),
        "manual_approval_input": MANUAL_APPROVAL_INPUT.exists(),
        "runtime_approval": RUNTIME_APPROVAL.exists()
    },
    "harness_session_count": harness_session_count,
    "readiness_checks": readiness_checks,
    "blockers": blockers,
    "readiness_passed": readiness_passed,
    "paper_shadow_started": False,
    "exchange_order_submission": False,
    "real_capital_allowed": False,
    "live_trading_enabled": False,
    "approved_for_paper_shadow_start": False,
    "approved_for_micro_live_execution": False,
    "approved_for_real_live_trading": False,
    "runtime_readiness_file": str(RUNTIME_OUT),
    "decision": decision,
    "next_phase": next_phase,
    "safety_notes": [
        "This phase checks paper shadow readiness only.",
        "This phase does not start paper shadow execution.",
        "This phase does not approve micro-live execution.",
        "This phase does not approve real live trading.",
        "This phase does not submit Binance orders.",
        "Manual approval remains required before any future paper shadow start."
    ]
}

write_json(OUT, report)

print(f"Report written to: {OUT}")
print(f"Runtime readiness written to: {RUNTIME_OUT}")
print(f"safe_mode_active={safe_mode}")
print(f"harness_session_count={harness_session_count}")
print(f"readiness_passed={readiness_passed}")
print("paper_shadow_started=False")
print("exchange_order_submission=False")
print("approved_for_paper_shadow_start=False")
print("approved_for_micro_live_execution=False")
print("approved_for_real_live_trading=False")
print(f"decision={decision}")
