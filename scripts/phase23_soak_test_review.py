import json
import subprocess
import time
from pathlib import Path

OUT = Path("data/processed/phase23_soak_test_review.json")
RUNTIME_OUT = Path("runtime/phase23_soak_test_review_state.json")
REVIEW_FILE = Path("data/processed/phase23_reopening/soak_test_review.json")

SOAK_FILES = [
    Path("data/processed/phase23_soak_test_execution.json"),
    Path("runtime/phase23_soak_test_execution_state.json"),
    Path("data/processed/phase23_reopening/soak_test_execution.json"),
]

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

def first_value(items, key, default=None):
    for item in items:
        value = item.get(key)
        if value not in (None, ""):
            return value
    return default

def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2))

head = git_value(["git", "rev-parse", "HEAD"])
branch = git_value(["git", "branch", "--show-current"])
remote = git_value(["git", "remote", "get-url", "origin"])
status_short = git_value(["git", "status", "--short"]) or ""
git_clean = status_short == ""

records = [load(path) for path in SOAK_FILES]

preflight_passed = any_true(records, "preflight_passed")
soak_started = any_true(records, "soak_test_started")
soak_completed = any_true(records, "soak_test_completed")
soak_execution_passed = any_true(records, "soak_test_execution_passed")

samples_collected = first_value(records, "samples_collected", 0) or 0
successful_samples = first_value(records, "successful_samples", 0) or 0
failed_samples = first_value(records, "failed_samples", 0) or 0
success_rate = first_value(records, "success_rate", 0.0) or 0.0
average_latency_ms = first_value(records, "average_latency_ms", None)
maximum_latency_ms = first_value(records, "maximum_latency_ms", None)
max_consecutive_errors_seen = (
    first_value(records, "maximum_consecutive_errors_seen", 0) or 0
)
abort_reason = first_value(records, "abort_reason", None)

public_endpoints_only = any_true(records, "public_endpoints_only")

signed_endpoint_not_called = any_false(
    records,
    "signed_endpoint_called",
)

account_endpoint_not_called = any_false(
    records,
    "account_endpoint_called",
)

order_endpoint_not_called = any_false(
    records,
    "order_endpoint_called",
)

testnet_order_not_submitted = any_false(
    records,
    "testnet_order_submission",
)

production_order_not_submitted = any_false(
    records,
    "production_exchange_order_submission",
)

production_credentials_not_used = any_false(
    records,
    "production_credentials_used",
)

micro_live_not_approved = any_false(
    records,
    "approved_for_micro_live_execution",
)

real_live_not_approved = any_false(
    records,
    "approved_for_real_live_trading",
)

real_capital_not_used = any_false(
    records,
    "real_capital_usage",
)

review_checks = {
    "git_head_present": bool(head),
    "git_branch_present": bool(branch),
    "git_remote_origin_present": bool(remote),
    "git_working_tree_clean_before_outputs": git_clean,
    "phase23_23_evidence_present": any(
        path.exists() for path in SOAK_FILES
    ),
    "phase23_23_preflight_passed": preflight_passed,
    "soak_test_started": soak_started,
    "soak_test_completed": soak_completed,
    "soak_test_execution_passed": soak_execution_passed,
    "samples_collected_positive": samples_collected > 0,
    "all_samples_successful":
        successful_samples == samples_collected,
    "failed_samples_zero": failed_samples == 0,
    "success_rate_complete": success_rate == 1.0,
    "maximum_consecutive_errors_zero":
        max_consecutive_errors_seen == 0,
    "abort_reason_none": abort_reason is None,
    "public_endpoints_only": public_endpoints_only,
    "signed_endpoint_not_called": signed_endpoint_not_called,
    "account_endpoint_not_called": account_endpoint_not_called,
    "order_endpoint_not_called": order_endpoint_not_called,
    "testnet_order_not_submitted": testnet_order_not_submitted,
    "production_order_not_submitted": production_order_not_submitted,
    "production_credentials_not_used":
        production_credentials_not_used,
    "micro_live_not_approved": micro_live_not_approved,
    "real_live_not_approved": real_live_not_approved,
    "real_capital_not_used": real_capital_not_used,
}

blockers = [
    key
    for key, value in review_checks.items()
    if value is not True
]

passed = not blockers

decision = (
    "PHASE_23_SOAK_TEST_REVIEW_COMPLETE_"
    "READY_FOR_INCIDENT_KILL_SWITCH_RETEST_"
    "NOT_APPROVED_FOR_LIVE_EXECUTION"
    if passed
    else
    "PHASE_23_SOAK_TEST_REVIEW_FAILED_"
    "REVIEW_REQUIRED_NOT_APPROVED_FOR_LIVE_EXECUTION"
)

record = {
    "phase": "phase_23_24_soak_test_review",
    "generated_at_unix": int(time.time()),
    "git_head": head,
    "git_branch": branch,
    "git_remote_origin": remote,
    "git_working_tree_clean_before_outputs": git_clean,
    "current_transition_status":
        "soak_test_review_only_not_approved_for_live_execution",
    "soak_test_review_passed": passed,
    "review_checks": review_checks,
    "blockers": blockers,
    "reviewed_soak_metrics": {
        "samples_collected": samples_collected,
        "successful_samples": successful_samples,
        "failed_samples": failed_samples,
        "success_rate": success_rate,
        "average_latency_ms": average_latency_ms,
        "maximum_latency_ms": maximum_latency_ms,
        "maximum_consecutive_errors_seen":
            max_consecutive_errors_seen,
        "abort_reason": abort_reason,
    },
    "soak_test_validated": passed,
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
    "next_phase": "Phase 23.25 — Incident / Kill Switch Retest",
}

write(OUT, record)
write(RUNTIME_OUT, record)
write(REVIEW_FILE, record)

print(f"Report written to: {OUT}")
print(f"Runtime state written to: {RUNTIME_OUT}")
print(f"Review file written to: {REVIEW_FILE}")
print(f"soak_test_review_passed={passed}")
print(f"samples_collected={samples_collected}")
print(f"successful_samples={successful_samples}")
print(f"failed_samples={failed_samples}")
print(f"success_rate={success_rate}")
print(f"average_latency_ms={average_latency_ms}")
print(f"maximum_consecutive_errors_seen={max_consecutive_errors_seen}")
print(f"abort_reason={abort_reason}")
print("testnet_order_submission=False")
print("production_exchange_order_submission=False")
print("approved_for_micro_live_execution=False")
print("approved_for_real_live_trading=False")
print("real_capital_usage=False")
print(f"decision={decision}")

if blockers:
    print("blockers=" + ",".join(blockers))
