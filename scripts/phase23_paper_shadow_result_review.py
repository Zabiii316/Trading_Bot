import json
import os
import subprocess
import time
from pathlib import Path

OUT = Path("data/processed/phase23_paper_shadow_result_review.json")
RUNTIME_OUT = Path("runtime/phase23_paper_shadow_result_review_state.json")
REVIEW_FILE = Path("data/processed/phase23_reopening/paper_shadow_result_review.json")

MONITORING_FILES = [
    Path("data/processed/phase23_paper_shadow_monitoring_validation.json"),
    Path("runtime/phase23_paper_shadow_monitoring_validation_state.json"),
    Path("data/processed/phase23_reopening/paper_shadow_monitoring_validation.json"),
]

START_GATE_FILES = [
    Path("data/processed/phase23_paper_shadow_start_gate.json"),
    Path("runtime/phase23_paper_shadow_start_gate_state.json"),
    Path("data/processed/phase23_reopening/paper_shadow_start_gate.json"),
]

FINAL_END_STATE = Path(
    "data/processed/phase22_project_final_end_state_record.json"
)

def run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True)

def git_value(cmd):
    result = run(cmd)
    return result.stdout.strip() if result.returncode == 0 else None

def load(path):
    try:
        return json.loads(path.read_text()) if path.exists() else {}
    except Exception:
        return {}

def any_true(items, key):
    return any(item.get(key) is True for item in items)

def any_false(items, key):
    return any(item.get(key) is False for item in items)

def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2))

head = git_value(["git", "rev-parse", "HEAD"])
branch = git_value(["git", "branch", "--show-current"])
remote = git_value(["git", "remote", "get-url", "origin"])
status_short = git_value(["git", "status", "--short"]) or ""
git_clean = status_short == ""

monitoring_records = [load(path) for path in MONITORING_FILES]
gate_records = [load(path) for path in START_GATE_FILES]
final_state = load(FINAL_END_STATE)

monitoring_validation_passed = (
    any_true(
        monitoring_records,
        "paper_shadow_monitoring_validation_passed",
    )
    or any(
        "PHASE_23_PAPER_SHADOW_MONITORING_VALIDATION_COMPLETE"
        in str(item.get("decision", ""))
        for item in monitoring_records
    )
)

start_gate_passed = (
    any_true(gate_records, "paper_shadow_start_gate_passed")
    or any(
        "PHASE_23_PAPER_SHADOW_START_GATE_CREATED"
        in str(item.get("decision", ""))
        for item in gate_records
    )
)

phase22_closed = (
    final_state.get("project_final_end_state_record_created") is True
    or "PHASE_22_PROJECT_FINAL_END_STATE_RECORD_CREATED"
    in str(final_state.get("decision", ""))
)

flags = {
    "BINANCE_TESTNET": os.getenv("BINANCE_TESTNET", ""),
    "BINANCE_USE_TESTNET": os.getenv("BINANCE_USE_TESTNET", ""),
    "BINANCE_ENABLE_LIVE_TRADING": os.getenv(
        "BINANCE_ENABLE_LIVE_TRADING", ""
    ),
    "LIVE_TRADING_ALLOWED": os.getenv("LIVE_TRADING_ALLOWED", ""),
    "KILL_SWITCH_ENABLED": os.getenv("KILL_SWITCH_ENABLED", ""),
}

safe_flags_active = (
    flags["BINANCE_TESTNET"] == "true"
    and flags["BINANCE_USE_TESTNET"] == "true"
    and flags["BINANCE_ENABLE_LIVE_TRADING"] == "false"
    and flags["LIVE_TRADING_ALLOWED"] == "false"
)

kill_switch_enabled = (
    flags["KILL_SWITCH_ENABLED"].lower()
    in {"true", "1", "yes", "enabled"}
)

checks = {
    "git_head_present": bool(head),
    "git_branch_present": bool(branch),
    "git_remote_origin_present": bool(remote),
    "git_working_tree_clean_before_outputs": git_clean,
    "phase22_final_end_state_present": FINAL_END_STATE.exists(),
    "phase22_closed_on_hold": phase22_closed,
    "phase23_14_start_gate_present": any(
        path.exists() for path in START_GATE_FILES
    ),
    "phase23_14_start_gate_passed": start_gate_passed,
    "phase23_15_monitoring_validation_present": any(
        path.exists() for path in MONITORING_FILES
    ),
    "phase23_15_monitoring_validation_passed":
        monitoring_validation_passed,
    "safe_flags_active": safe_flags_active,
    "kill_switch_enabled": kill_switch_enabled,
    "paper_shadow_not_started": any_false(
        monitoring_records, "paper_shadow_started"
    ),
    "monitoring_not_started": any_false(
        monitoring_records, "monitoring_started"
    ),
    "execution_allowed_false": any_false(
        monitoring_records, "execution_allowed"
    ),
    "exchange_order_submission_false": any_false(
        monitoring_records, "exchange_order_submission"
    ),
    "micro_live_approval_false": any_false(
        monitoring_records,
        "approved_for_micro_live_execution",
    ),
    "real_live_approval_false": any_false(
        monitoring_records,
        "approved_for_real_live_trading",
    ),
}

blockers = [
    key for key, value in checks.items()
    if value is not True
]

passed = not blockers

decision = (
    "PHASE_23_PAPER_SHADOW_RESULT_REVIEW_COMPLETE_"
    "NO_RUNTIME_RESULTS_YET_READY_FOR_RISK_REVIEW_"
    "NOT_APPROVED_FOR_EXECUTION"
    if passed
    else
    "PHASE_23_PAPER_SHADOW_RESULT_REVIEW_FAILED_"
    "REVIEW_REQUIRED_NOT_APPROVED_FOR_EXECUTION"
)

record = {
    "phase": "phase_23_16_paper_shadow_result_review",
    "generated_at_unix": int(time.time()),
    "git_head": head,
    "git_branch": branch,
    "git_remote_origin": remote,
    "git_working_tree_clean_before_outputs": git_clean,
    "current_transition_status":
        "paper_shadow_result_review_only_not_started_not_approved_for_execution",
    "paper_shadow_result_review_passed": passed,
    "runtime_results_available": False,
    "runtime_results_reviewed": False,
    "review_basis":
        "readiness_and_monitoring_validation_evidence_only",
    "review_checks": checks,
    "blockers": blockers,
    "safe_flags": flags,
    "safe_flags_active": safe_flags_active,
    "kill_switch_enabled": kill_switch_enabled,
    "paper_shadow_started": False,
    "paper_shadow_start_approved": False,
    "approved_for_paper_shadow_start": False,
    "approved_for_paper_shadow": False,
    "monitoring_started": False,
    "run_dry_run_now": False,
    "run_backtest_now": False,
    "signed_endpoint_called": False,
    "account_endpoint_called": False,
    "order_endpoint_called": False,
    "production_credentials_used": False,
    "execution_allowed": False,
    "approved_for_execution": False,
    "approved_for_live": False,
    "exchange_order_submission": False,
    "approved_for_micro_live_execution": False,
    "approved_for_real_live_trading": False,
    "production_api_key_usage": False,
    "real_capital_usage": False,
    "decision": decision,
    "next_phase": "Phase 23.17 — Paper Shadow Risk Review",
}

write(OUT, record)
write(RUNTIME_OUT, record)
write(REVIEW_FILE, record)

print(f"Report written to: {OUT}")
print(f"Runtime state written to: {RUNTIME_OUT}")
print(f"Review file written to: {REVIEW_FILE}")
print(f"paper_shadow_result_review_passed={passed}")
print("runtime_results_available=False")
print("runtime_results_reviewed=False")
print(f"safe_flags_active={safe_flags_active}")
print(f"kill_switch_enabled={kill_switch_enabled}")
print("paper_shadow_started=False")
print("monitoring_started=False")
print("execution_allowed=False")
print("exchange_order_submission=False")
print("approved_for_micro_live_execution=False")
print("approved_for_real_live_trading=False")
print(f"decision={decision}")

if blockers:
    print("blockers=" + ",".join(blockers))
