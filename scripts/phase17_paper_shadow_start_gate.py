import json, os, subprocess, time
from pathlib import Path

OUT = Path("data/processed/phase17_paper_shadow_start_gate.json")
GATE_DIR = Path("data/processed/paper_shadow_start_gate")
RUNTIME_GATE = Path("runtime/phase17_paper_shadow_start_gate.json")
HARNESS_INPUT = Path("data/processed/phase17_paper_shadow_execution_harness.json")
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

harness_report = load_json(HARNESS_INPUT)
harness_state = load_json(HARNESS_STATE)

harness_sessions = harness_report.get("harness_sessions", [])
harness_session_count = len(harness_sessions)

manual_approval_record = {
    "manual_approval_required": True,
    "manual_approval_provided": False,
    "approver_name": None,
    "approver_role": None,
    "approval_timestamp_utc": None,
    "approval_scope": "paper_shadow_only",
    "real_capital_allowed": False,
    "exchange_order_submission_allowed": False,
    "live_trading_allowed": False,
    "micro_live_execution_allowed": False,
    "required_confirmation_text": "I approve PAPER SHADOW ONLY with real capital disabled and exchange order submission disabled.",
    "confirmation_text_provided": None
}

gate_checks = {
    "safe_mode_active": safe_mode,
    "harness_input_present": HARNESS_INPUT.exists(),
    "harness_state_present": HARNESS_STATE.exists(),
    "harness_sessions_available": harness_session_count > 0,
    "paper_shadow_not_already_started": harness_state.get("paper_shadow_started") is not True,
    "exchange_order_submission_disabled": harness_state.get("exchange_order_submission") is False,
    "live_trading_disabled": harness_state.get("live_trading_enabled") is False,
    "real_capital_disabled": harness_state.get("real_capital_allowed") is False,
    "manual_approval_provided": False
}

start_gate_passed = all(gate_checks.values())

GATE_DIR.mkdir(parents=True, exist_ok=True)

gate_template = {
    "phase": "phase_17_19_paper_shadow_start_gate_template",
    "created_at_unix": int(time.time()),
    "purpose": "Manual approval template for paper shadow only. Not valid for micro-live or real live trading.",
    "manual_approval_record": manual_approval_record,
    "gate_checks": gate_checks,
    "start_gate_passed": False,
    "paper_shadow_started": False,
    "approved_for_paper_shadow_start": False,
    "approved_for_micro_live_execution": False,
    "approved_for_real_live_trading": False
}

template_path = GATE_DIR / "paper_shadow_manual_start_gate_template.json"
write_json(template_path, gate_template)

if harness_session_count > 0:
    decision = "PAPER_SHADOW_START_GATE_CREATED_MANUAL_APPROVAL_REQUIRED_NOT_STARTED"
    next_phase = "Phase 17.20 — Paper Shadow Manual Approval Record"
else:
    decision = "PAPER_SHADOW_START_GATE_SKIPPED_NO_HARNESS_SESSIONS_STRATEGY_REWORK_REQUIRED"
    next_phase = "Phase 17.20 — Paper Shadow Manual Approval Record or Strategy Redesign"

runtime_gate = {
    "phase": "phase_17_19_paper_shadow_start_gate_runtime",
    "updated_at_unix": int(time.time()),
    "start_gate_passed": False,
    "paper_shadow_started": False,
    "paper_shadow_completed": False,
    "approved_for_paper_shadow_start": False,
    "approved_for_micro_live_execution": False,
    "approved_for_real_live_trading": False,
    "decision": decision
}

write_json(RUNTIME_GATE, runtime_gate)

report = {
    "phase": "phase_17_19_paper_shadow_start_gate",
    "generated_at_unix": int(time.time()),
    "scope": "paper_shadow_start_gate_only",
    "safety_flags": flags,
    "safe_mode_active": safe_mode,
    "git_working_tree_clean": git_clean(),
    "harness_input_present": HARNESS_INPUT.exists(),
    "harness_state_present": HARNESS_STATE.exists(),
    "harness_session_count": harness_session_count,
    "gate_checks": gate_checks,
    "manual_approval_record": manual_approval_record,
    "manual_gate_template": str(template_path),
    "runtime_gate": str(RUNTIME_GATE),
    "start_gate_passed": False,
    "paper_shadow_started": False,
    "paper_shadow_completed": False,
    "exchange_order_submission": False,
    "real_capital_allowed": False,
    "live_trading_enabled": False,
    "approved_for_paper_shadow_start": False,
    "approved_for_micro_live_execution": False,
    "approved_for_real_live_trading": False,
    "decision": decision,
    "next_phase": next_phase,
    "safety_notes": [
        "This phase creates the paper shadow start gate only.",
        "This phase does not start paper shadow execution.",
        "This phase does not approve micro-live execution.",
        "This phase does not approve real live trading.",
        "This phase does not submit Binance orders.",
        "Manual approval is required in a later phase before paper shadow can start."
    ]
}

write_json(OUT, report)

print(f"Report written to: {OUT}")
print(f"Runtime gate written to: {RUNTIME_GATE}")
print(f"safe_mode_active={safe_mode}")
print(f"harness_session_count={harness_session_count}")
print("start_gate_passed=False")
print("paper_shadow_started=False")
print("exchange_order_submission=False")
print("approved_for_paper_shadow_start=False")
print("approved_for_micro_live_execution=False")
print("approved_for_real_live_trading=False")
print(f"decision={decision}")
