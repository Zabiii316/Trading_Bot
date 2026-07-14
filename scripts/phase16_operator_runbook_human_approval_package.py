import json, os, subprocess, time
from pathlib import Path

OUT = Path("data/processed/phase16_operator_runbook_human_approval_package.json")

INPUTS = {
    "final_readiness_review": "data/processed/phase16_final_micro_live_readiness_review.json",
    "emergency_stop_retest": "data/processed/phase16_emergency_stop_kill_switch_retest.json",
    "capital_limits": "data/processed/phase16_capital_limits_loss_limit_controls.json",
    "secrets_manager_controls": "data/processed/phase16_secrets_manager_key_handling_controls.json",
    "production_api_key_audit": "data/processed/phase16_production_api_key_permission_audit.json",
    "manual_approval_record": "data/processed/phase16_micro_live_manual_approval_record.json",
}

def git_clean():
    return subprocess.run(["git", "status", "--short"], capture_output=True, text=True).stdout.strip() == ""

def load(path):
    p = Path(path)
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text())
    except Exception:
        return {}

flags = {
    "BINANCE_TESTNET": os.getenv("BINANCE_TESTNET", ""),
    "BINANCE_USE_TESTNET": os.getenv("BINANCE_USE_TESTNET", ""),
    "BINANCE_ENABLE_LIVE_TRADING": os.getenv("BINANCE_ENABLE_LIVE_TRADING", ""),
    "LIVE_TRADING_ALLOWED": os.getenv("LIVE_TRADING_ALLOWED", ""),
}

safe_mode = flags["BINANCE_ENABLE_LIVE_TRADING"] == "false" and flags["LIVE_TRADING_ALLOWED"] == "false"
present = {k: Path(v).exists() for k, v in INPUTS.items()}

review = load(INPUTS["final_readiness_review"])
blockers = review.get("blockers", [])

runbook = {
    "before_any_future_micro_live": [
        "Confirm safe mode is active.",
        "Confirm Git working tree is clean.",
        "Confirm kill switch status is understood.",
        "Confirm all capital and loss limits are formally approved.",
        "Confirm production API key IP whitelist and withdrawal-disable checks.",
        "Confirm manual approval record is complete.",
        "Confirm emergency stop procedure is tested.",
    ],
    "do_not_proceed_if": [
        "Any blocker remains open.",
        "Live trading flags are already enabled.",
        "Kill switch behavior is not verified.",
        "Production API keys are not secured.",
        "Capital/loss limits are not approved.",
        "Manual approval is missing.",
    ],
    "emergency_commands": {
        "enable_safe_mode": "source runtime/safe_trading_flags.env",
        "activate_kill_switch": "touch runtime/KILL_SWITCH_ACTIVE",
        "check_git": "git status",
        "check_final_review": "cat data/processed/phase16_final_micro_live_readiness_review.json | python -m json.tool"
    }
}

report = {
    "phase": "phase_16_23_operator_runbook_human_approval_package",
    "generated_at_unix": int(time.time()),
    "scope": "operator_runbook_and_human_approval_package_only",
    "safety_flags": flags,
    "safe_mode_active": safe_mode,
    "inputs_present": present,
    "all_inputs_present": all(present.values()),
    "git_working_tree_clean": git_clean(),
    "previous_readiness_blockers": blockers,
    "runbook": runbook,
    "approved_for_micro_live_execution": False,
    "decision": "OPERATOR_RUNBOOK_HUMAN_APPROVAL_PACKAGE_CREATED_NOT_APPROVED_FOR_EXECUTION",
    "next_phase": "Phase 16.24 — Final Documentation and Repository Release Tag",
    "safety_notes": [
        "This package does not approve live trading.",
        "This package does not enable micro-live execution.",
        "Live trading flags must remain disabled.",
        "A separate signed approval gate is required before any real execution.",
    ],
}

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(report, indent=2))

print(f"Report written to: {OUT}")
print(f"safe_mode_active={safe_mode}")
print(f"all_inputs_present={report['all_inputs_present']}")
print(f"git_working_tree_clean={report['git_working_tree_clean']}")
print(f"previous_blockers={len(blockers)}")
print("approved_for_micro_live_execution=False")
print(f"decision={report['decision']}")
