import json, os, subprocess, time
from pathlib import Path

OUT = Path("data/processed/phase16_final_documentation_repository_release.json")

INPUTS = {
    "operator_runbook": "data/processed/phase16_operator_runbook_human_approval_package.json",
    "final_readiness_review": "data/processed/phase16_final_micro_live_readiness_review.json",
    "emergency_stop_retest": "data/processed/phase16_emergency_stop_kill_switch_retest.json",
    "capital_limits": "data/processed/phase16_capital_limits_loss_limit_controls.json",
    "secrets_manager_controls": "data/processed/phase16_secrets_manager_key_handling_controls.json",
    "production_api_key_audit": "data/processed/phase16_production_api_key_permission_audit.json",
    "manual_approval_record": "data/processed/phase16_micro_live_manual_approval_record.json",
    "soak_execution": "data/processed/phase16_testnet_soak_execution_report.json",
}

def run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True)

def git_clean():
    return run(["git", "status", "--short"]).stdout.strip() == ""

def git_commit():
    r = run(["git", "rev-parse", "HEAD"])
    return r.stdout.strip() if r.returncode == 0 else ""

def git_branch():
    r = run(["git", "branch", "--show-current"])
    return r.stdout.strip() if r.returncode == 0 else ""

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
runbook = load(INPUTS["operator_runbook"])

release_checks = {
    "all_phase16_evidence_present": all(present.values()),
    "safe_mode_active": safe_mode,
    "git_working_tree_clean": git_clean(),
    "operator_runbook_present": Path(INPUTS["operator_runbook"]).exists(),
    "final_readiness_review_present": Path(INPUTS["final_readiness_review"]).exists(),
    "micro_live_not_approved": review.get("approved_for_micro_live_execution") is False,
    "operator_package_not_approved": runbook.get("approved_for_micro_live_execution") is False,
}

blockers = [k for k, v in release_checks.items() if v is not True]

report = {
    "phase": "phase_16_24_final_documentation_repository_release",
    "generated_at_unix": int(time.time()),
    "scope": "final_documentation_and_repository_release_tag_only",
    "git": {
        "branch": git_branch(),
        "commit": git_commit(),
        "release_tag_to_create": "phase16-controlled-testnet-review-v1",
    },
    "safety_flags": flags,
    "inputs_present": present,
    "release_checks": release_checks,
    "release_blockers": blockers,
    "approved_for_micro_live_execution": False,
    "approved_for_real_live_trading": False,
    "decision": "PHASE_16_DOCUMENTATION_RELEASE_READY_NOT_APPROVED_FOR_EXECUTION",
    "next_phase": "Phase 17 — Strategy Hardening, Backtesting Expansion, and Production Readiness Planning",
    "safety_notes": [
        "This release tag documents controlled testnet readiness only.",
        "This release does not approve micro-live execution.",
        "This release does not approve real live trading.",
        "Live trading flags must remain disabled.",
        "Production Binance keys must not be committed.",
    ],
}

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(report, indent=2))

print(f"Report written to: {OUT}")
print(f"safe_mode_active={safe_mode}")
print(f"git_working_tree_clean={release_checks['git_working_tree_clean']}")
print(f"all_phase16_evidence_present={release_checks['all_phase16_evidence_present']}")
print(f"release_blockers={len(blockers)}")
print("approved_for_micro_live_execution=False")
print("approved_for_real_live_trading=False")
print(f"decision={report['decision']}")
