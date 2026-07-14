import json, os, subprocess, time
from pathlib import Path

OUT = Path("data/processed/phase17_paper_shadow_manual_approval_record.json")
APPROVAL_DIR = Path("data/processed/paper_shadow_manual_approval")
RUNTIME_APPROVAL = Path("runtime/phase17_paper_shadow_manual_approval_record.json")

START_GATE_INPUT = Path("data/processed/phase17_paper_shadow_start_gate.json")
RUNTIME_GATE = Path("runtime/phase17_paper_shadow_start_gate.json")
HARNESS_STATE = Path("runtime/phase17_paper_shadow_state.json")

REQUIRED_CONFIRMATION_TEXT = "I approve PAPER SHADOW ONLY with real capital disabled and exchange order submission disabled."

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

start_gate = load_json(START_GATE_INPUT)
runtime_gate = load_json(RUNTIME_GATE)
harness_state = load_json(HARNESS_STATE)

approval_record = {
    "manual_approval_required": True,
    "manual_approval_provided": False,
    "approver_name": None,
    "approver_role": None,
    "approval_timestamp_utc": None,
    "approval_scope": "paper_shadow_only",
    "confirmation_text_required": REQUIRED_CONFIRMATION_TEXT,
    "confirmation_text_provided": None,
    "confirmation_text_matches": False,
    "real_capital_allowed": False,
    "exchange_order_submission_allowed": False,
    "live_trading_allowed": False,
    "micro_live_execution_allowed": False,
    "paper_shadow_start_allowed": False,
    "approval_status": "MANUAL_APPROVAL_RECORD_CREATED_NOT_APPROVED"
}

approval_checks = {
    "safe_mode_active": safe_mode,
    "start_gate_input_present": START_GATE_INPUT.exists(),
    "runtime_gate_present": RUNTIME_GATE.exists(),
    "harness_state_present": HARNESS_STATE.exists(),
    "start_gate_created": start_gate.get("phase") == "phase_17_19_paper_shadow_start_gate",
    "paper_shadow_not_started": harness_state.get("paper_shadow_started") is not True,
    "exchange_order_submission_disabled": harness_state.get("exchange_order_submission") is False,
    "real_capital_disabled": harness_state.get("real_capital_allowed") is False,
    "live_trading_disabled": harness_state.get("live_trading_enabled") is False,
    "manual_approval_provided": False,
    "confirmation_text_matches": False
}

approved_for_paper_shadow_start = False

APPROVAL_DIR.mkdir(parents=True, exist_ok=True)

approval_template = {
    "phase": "phase_17_20_paper_shadow_manual_approval_template",
    "created_at_unix": int(time.time()),
    "instructions": [
        "This template is for PAPER SHADOW ONLY.",
        "Do not use this template for micro-live execution.",
        "Do not use this template for real live trading.",
        "Real capital must remain disabled.",
        "Exchange order submission must remain disabled."
    ],
    "required_confirmation_text": REQUIRED_CONFIRMATION_TEXT,
    "approval_record": approval_record
}

template_path = APPROVAL_DIR / "paper_shadow_manual_approval_template.json"
write_json(template_path, approval_template)

runtime_approval = {
    "phase": "phase_17_20_paper_shadow_manual_approval_runtime",
    "updated_at_unix": int(time.time()),
    "manual_approval_provided": False,
    "approved_for_paper_shadow_start": False,
    "paper_shadow_started": False,
    "approved_for_micro_live_execution": False,
    "approved_for_real_live_trading": False,
    "decision": "PAPER_SHADOW_MANUAL_APPROVAL_RECORD_CREATED_NOT_APPROVED_NOT_STARTED"
}

write_json(RUNTIME_APPROVAL, runtime_approval)

decision = "PAPER_SHADOW_MANUAL_APPROVAL_RECORD_CREATED_NOT_APPROVED_NOT_STARTED"
next_phase = "Phase 17.21 — Paper Shadow Start Readiness Check"

report = {
    "phase": "phase_17_20_paper_shadow_manual_approval_record",
    "generated_at_unix": int(time.time()),
    "scope": "paper_shadow_manual_approval_record_only",
    "safety_flags": flags,
    "safe_mode_active": safe_mode,
    "git_working_tree_clean": git_clean(),
    "inputs_present": {
        "start_gate_input": START_GATE_INPUT.exists(),
        "runtime_gate": RUNTIME_GATE.exists(),
        "harness_state": HARNESS_STATE.exists()
    },
    "approval_checks": approval_checks,
    "approval_record": approval_record,
    "approval_template": str(template_path),
    "runtime_approval_record": str(RUNTIME_APPROVAL),
    "manual_approval_provided": False,
    "approved_for_paper_shadow_start": approved_for_paper_shadow_start,
    "paper_shadow_started": False,
    "exchange_order_submission": False,
    "real_capital_allowed": False,
    "live_trading_enabled": False,
    "approved_for_micro_live_execution": False,
    "approved_for_real_live_trading": False,
    "decision": decision,
    "next_phase": next_phase,
    "safety_notes": [
        "This phase creates a manual approval record only.",
        "This phase does not approve paper shadow start.",
        "This phase does not start paper shadow execution.",
        "This phase does not approve micro-live execution.",
        "This phase does not approve real live trading.",
        "This phase does not submit Binance orders."
    ]
}

write_json(OUT, report)

print(f"Report written to: {OUT}")
print(f"Runtime approval written to: {RUNTIME_APPROVAL}")
print(f"safe_mode_active={safe_mode}")
print("manual_approval_provided=False")
print("approved_for_paper_shadow_start=False")
print("paper_shadow_started=False")
print("exchange_order_submission=False")
print("approved_for_micro_live_execution=False")
print("approved_for_real_live_trading=False")
print(f"decision={decision}")
