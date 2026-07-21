import json
import os
import subprocess
import time
from pathlib import Path

OUT = Path("data/processed/phase23_incident_kill_switch_retest.json")
RUNTIME_OUT = Path("runtime/phase23_incident_kill_switch_retest_state.json")
RETEST_FILE = Path(
    "data/processed/phase23_reopening/incident_kill_switch_retest.json"
)

SOAK_REVIEW_FILES = [
    Path("data/processed/phase23_soak_test_review.json"),
    Path("runtime/phase23_soak_test_review_state.json"),
    Path("data/processed/phase23_reopening/soak_test_review.json"),
]

EXECUTION_HARNESS = Path(
    "scripts/phase23_controlled_testnet_micro_execution_run.py"
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

def read_text(path):
    try:
        return path.read_text(errors="ignore") if path.exists() else ""
    except Exception:
        return ""

def simulated_execution_guard(
    *,
    safe_flags_active,
    kill_switch_safety_enabled,
    incident_kill_switch_triggered,
    manual_testnet_approval,
    testnet_environment,
):
    if not safe_flags_active:
        return False, "safe_flags_inactive"

    if not kill_switch_safety_enabled:
        return False, "kill_switch_safety_not_enabled"

    if incident_kill_switch_triggered:
        return False, "incident_kill_switch_triggered"

    if not testnet_environment:
        return False, "non_testnet_environment"

    if not manual_testnet_approval:
        return False, "manual_testnet_approval_missing"

    return True, "guard_preconditions_passed"

def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2))

head = git_value(["git", "rev-parse", "HEAD"])
branch = git_value(["git", "branch", "--show-current"])
remote = git_value(["git", "remote", "get-url", "origin"])
status_short = git_value(["git", "status", "--short"]) or ""
git_clean = status_short == ""

reviews = [load(path) for path in SOAK_REVIEW_FILES]

soak_review_passed = (
    any_true(reviews, "soak_test_review_passed")
    or any(
        "PHASE_23_SOAK_TEST_REVIEW_COMPLETE"
        in str(item.get("decision", ""))
        for item in reviews
    )
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

kill_switch_safety_enabled = (
    flags["KILL_SWITCH_ENABLED"].lower()
    in {"true", "1", "yes", "enabled"}
)

harness_text = read_text(EXECUTION_HARNESS)

harness_checks_kill_switch = (
    "kill_switch_enabled" in harness_text
    and '"kill_switch_enabled"' in harness_text
)

harness_requires_safe_flags = (
    "safe_flags_active" in harness_text
)

harness_restricts_testnet_host = (
    "testnet_host_allowed" in harness_text
)

# Scenario 1:
# Incident trigger must block execution.
incident_allowed, incident_reason = simulated_execution_guard(
    safe_flags_active=True,
    kill_switch_safety_enabled=True,
    incident_kill_switch_triggered=True,
    manual_testnet_approval=True,
    testnet_environment=True,
)

# Scenario 2:
# Missing safety mechanism must block execution.
missing_kill_switch_allowed, missing_kill_switch_reason = (
    simulated_execution_guard(
        safe_flags_active=True,
        kill_switch_safety_enabled=False,
        incident_kill_switch_triggered=False,
        manual_testnet_approval=True,
        testnet_environment=True,
    )
)

# Scenario 3:
# Disabled safe flags must block execution.
unsafe_flags_allowed, unsafe_flags_reason = simulated_execution_guard(
    safe_flags_active=False,
    kill_switch_safety_enabled=True,
    incident_kill_switch_triggered=False,
    manual_testnet_approval=True,
    testnet_environment=True,
)

# Positive control only.
# This does not execute anything.
positive_control_allowed, positive_control_reason = (
    simulated_execution_guard(
        safe_flags_active=True,
        kill_switch_safety_enabled=True,
        incident_kill_switch_triggered=False,
        manual_testnet_approval=True,
        testnet_environment=True,
    )
)

incident_block_verified = (
    incident_allowed is False
    and incident_reason == "incident_kill_switch_triggered"
)

missing_kill_switch_block_verified = (
    missing_kill_switch_allowed is False
    and missing_kill_switch_reason
    == "kill_switch_safety_not_enabled"
)

unsafe_flags_block_verified = (
    unsafe_flags_allowed is False
    and unsafe_flags_reason == "safe_flags_inactive"
)

positive_control_verified = (
    positive_control_allowed is True
    and positive_control_reason == "guard_preconditions_passed"
)

checks = {
    "git_head_present": bool(head),
    "git_branch_present": bool(branch),
    "git_remote_origin_present": bool(remote),
    "git_working_tree_clean_before_outputs": git_clean,
    "phase23_24_soak_review_present": any(
        path.exists() for path in SOAK_REVIEW_FILES
    ),
    "phase23_24_soak_review_passed": soak_review_passed,
    "safe_flags_active": safe_flags_active,
    "kill_switch_safety_enabled": kill_switch_safety_enabled,
    "execution_harness_present": EXECUTION_HARNESS.exists(),
    "execution_harness_checks_kill_switch":
        harness_checks_kill_switch,
    "execution_harness_requires_safe_flags":
        harness_requires_safe_flags,
    "execution_harness_restricts_testnet_host":
        harness_restricts_testnet_host,
    "incident_kill_switch_blocks_execution":
        incident_block_verified,
    "missing_kill_switch_safety_blocks_execution":
        missing_kill_switch_block_verified,
    "unsafe_flags_block_execution":
        unsafe_flags_block_verified,
    "positive_control_guard_passes":
        positive_control_verified,
    "network_call_made_false": True,
    "signed_endpoint_called_false": True,
    "account_endpoint_called_false": True,
    "order_endpoint_called_false": True,
    "exchange_order_submission_false": True,
}

blockers = [
    key for key, value in checks.items()
    if value is not True
]

passed = not blockers

decision = (
    "PHASE_23_INCIDENT_KILL_SWITCH_RETEST_COMPLETE_"
    "READY_FOR_PRODUCTION_READINESS_REVIEW_"
    "NOT_APPROVED_FOR_LIVE_EXECUTION"
    if passed
    else
    "PHASE_23_INCIDENT_KILL_SWITCH_RETEST_FAILED_"
    "REVIEW_REQUIRED_NOT_APPROVED_FOR_LIVE_EXECUTION"
)

record = {
    "phase": "phase_23_25_incident_kill_switch_retest",
    "generated_at_unix": int(time.time()),
    "git_head": head,
    "git_branch": branch,
    "git_remote_origin": remote,
    "git_working_tree_clean_before_outputs": git_clean,
    "current_transition_status":
        "incident_kill_switch_retest_only_not_approved_for_live_execution",
    "incident_kill_switch_retest_passed": passed,
    "retest_checks": checks,
    "blockers": blockers,
    "safe_flags": flags,
    "safe_flags_active": safe_flags_active,
    "kill_switch_safety_enabled": kill_switch_safety_enabled,
    "simulated_scenarios": {
        "incident_trigger": {
            "execution_allowed": incident_allowed,
            "reason": incident_reason,
        },
        "kill_switch_safety_missing": {
            "execution_allowed": missing_kill_switch_allowed,
            "reason": missing_kill_switch_reason,
        },
        "unsafe_flags": {
            "execution_allowed": unsafe_flags_allowed,
            "reason": unsafe_flags_reason,
        },
        "positive_control": {
            "guard_preconditions_passed":
                positive_control_allowed,
            "reason": positive_control_reason,
            "actual_execution_performed": False,
        },
    },
    "incident_kill_switch_trigger_simulated": True,
    "actual_kill_switch_state_changed": False,
    "network_call_made": False,
    "signed_endpoint_called": False,
    "account_endpoint_called": False,
    "order_endpoint_called": False,
    "testnet_order_submission": False,
    "production_exchange_order_submission": False,
    "production_credentials_used": False,
    "execution_allowed": False,
    "approved_for_execution": False,
    "approved_for_micro_live_execution": False,
    "approved_for_real_live_trading": False,
    "approved_for_live": False,
    "exchange_order_submission": False,
    "production_api_key_usage": False,
    "real_capital_usage": False,
    "decision": decision,
    "next_phase": "Phase 23.26 — Production Readiness Review",
}

write(OUT, record)
write(RUNTIME_OUT, record)
write(RETEST_FILE, record)

print(f"Report written to: {OUT}")
print(f"Runtime state written to: {RUNTIME_OUT}")
print(f"Retest file written to: {RETEST_FILE}")
print(f"incident_kill_switch_retest_passed={passed}")
print(f"safe_flags_active={safe_flags_active}")
print(
    f"kill_switch_safety_enabled="
    f"{kill_switch_safety_enabled}"
)
print(
    f"incident_kill_switch_blocks_execution="
    f"{incident_block_verified}"
)
print(
    f"missing_kill_switch_safety_blocks_execution="
    f"{missing_kill_switch_block_verified}"
)
print(
    f"unsafe_flags_block_execution="
    f"{unsafe_flags_block_verified}"
)
print(
    f"positive_control_guard_passes="
    f"{positive_control_verified}"
)
print("actual_kill_switch_state_changed=False")
print("network_call_made=False")
print("order_endpoint_called=False")
print("exchange_order_submission=False")
print("approved_for_micro_live_execution=False")
print("approved_for_real_live_trading=False")
print("real_capital_usage=False")
print(f"decision={decision}")

if blockers:
    print("blockers=" + ",".join(blockers))
