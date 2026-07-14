import json, os, subprocess, time
from pathlib import Path

OUT = Path("data/processed/phase16_final_micro_live_readiness_review.json")
KILL = Path("runtime/KILL_SWITCH_ACTIVE")

INPUTS = {
    "soak_execution": "data/processed/phase16_testnet_soak_execution_report.json",
    "post_soak_review": "data/processed/phase16_post_soak_review_micro_live_gap.json",
    "final_go_no_go_gate": "data/processed/phase16_final_micro_live_go_no_go_gate_spec.json",
    "manual_approval_record": "data/processed/phase16_micro_live_manual_approval_record.json",
    "production_api_key_audit": "data/processed/phase16_production_api_key_permission_audit.json",
    "secrets_manager_controls": "data/processed/phase16_secrets_manager_key_handling_controls.json",
    "capital_limits": "data/processed/phase16_capital_limits_loss_limit_controls.json",
    "emergency_stop_retest": "data/processed/phase16_emergency_stop_kill_switch_retest.json",
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

soak = load(INPUTS["soak_execution"])
capital = load(INPUTS["capital_limits"])
secrets = load(INPUTS["secrets_manager_controls"])
emergency = load(INPUTS["emergency_stop_retest"])
manual = load(INPUTS["manual_approval_record"])

checks = {
    "all_inputs_present": all(present.values()),
    "safe_mode_active": safe_mode,
    "git_working_tree_clean": git_clean(),
    "kill_switch_active": KILL.exists(),
    "soak_passed": soak.get("passed") is True,
    "capital_limits_defined": capital.get("all_numeric_limits_defined") is True,
    "secrets_scan_clean": secrets.get("secrets_controls", {}).get("tracked_secret_scan_clean") is True,
    "emergency_stop_retest_passed": emergency.get("emergency_stop_retest_passed") is True,
    "manual_approval_complete": manual.get("approved_for_micro_live_execution") is True,
}

blockers = [k for k, v in checks.items() if v is not True]

report = {
    "phase": "phase_16_22_final_micro_live_readiness_review",
    "generated_at_unix": int(time.time()),
    "scope": "final_micro_live_readiness_review_only",
    "safety_flags": flags,
    "inputs_present": present,
    "readiness_checks": checks,
    "blockers": blockers,
    "approved_for_micro_live_execution": False,
    "decision": "FINAL_MICRO_LIVE_READINESS_REVIEW_COMPLETE_NOT_APPROVED_GAPS_REMAIN",
    "next_phase": "Phase 16.23 — Operator Runbook and Human Approval Package",
}

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(report, indent=2))

print(f"Report written to: {OUT}")
print(f"safe_mode_active={safe_mode}")
print(f"kill_switch_active={checks['kill_switch_active']}")
print(f"blockers={len(blockers)}")
print("approved_for_micro_live_execution=False")
print(f"decision={report['decision']}")
