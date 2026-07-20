import json
import os
import subprocess
import time
from pathlib import Path

OUT = Path("data/processed/phase23_testnet_micro_execution_review.json")
RUNTIME_OUT = Path("runtime/phase23_testnet_micro_execution_review_state.json")
REVIEW_FILE = Path(
    "data/processed/phase23_reopening/testnet_micro_execution_review.json"
)

RUN_FILES = [
    Path("data/processed/phase23_controlled_testnet_micro_execution_run.json"),
    Path("runtime/phase23_controlled_testnet_micro_execution_run_state.json"),
    Path(
        "data/processed/phase23_reopening/"
        "controlled_testnet_micro_execution_run.json"
    ),
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

records = [load(path) for path in RUN_FILES]

preflight_passed = any_true(records, "preflight_passed")
submission_attempted = any_true(
    records,
    "testnet_order_submission_attempted"
)
submission_succeeded = any_true(
    records,
    "testnet_order_submission_succeeded"
)
execution_completed = any_true(
    records,
    "testnet_micro_execution_completed"
)

signed_endpoint_called = any_true(
    records,
    "signed_endpoint_called"
)
order_endpoint_called = any_true(
    records,
    "order_endpoint_called"
)

account_endpoint_not_called = any_false(
    records,
    "account_endpoint_called"
)
production_credentials_not_used = any_false(
    records,
    "production_credentials_used"
)
production_order_not_submitted = any_false(
    records,
    "production_exchange_order_submission"
)
real_capital_not_used = any_false(
    records,
    "real_capital_usage"
)
micro_live_not_approved = any_false(
    records,
    "approved_for_micro_live_execution"
)
real_live_not_approved = any_false(
    records,
    "approved_for_real_live_trading"
)

testnet_environment = first_value(
    records,
    "testnet_environment",
    {}
) or {}

testnet_host_allowed = (
    testnet_environment.get("testnet_host_allowed") is True
)

order_response = first_value(
    records,
    "testnet_order_response",
    {}
) or {}

order_id_present = order_response.get("orderId") is not None

review_checks = {
    "git_head_present": bool(head),
    "git_branch_present": bool(branch),
    "git_remote_origin_present": bool(remote),
    "git_working_tree_clean_before_outputs": git_clean,
    "phase23_20_evidence_present": any(
        path.exists() for path in RUN_FILES
    ),
    "phase23_20_preflight_passed": preflight_passed,
    "testnet_order_submission_attempted": submission_attempted,
    "testnet_order_submission_succeeded": submission_succeeded,
    "testnet_micro_execution_completed": execution_completed,
    "testnet_host_allowed": testnet_host_allowed,
    "signed_endpoint_called_as_expected": signed_endpoint_called,
    "order_endpoint_called_as_expected": order_endpoint_called,
    "account_endpoint_not_called": account_endpoint_not_called,
    "order_id_present": order_id_present,
    "production_credentials_not_used": production_credentials_not_used,
    "production_order_not_submitted": production_order_not_submitted,
    "real_capital_not_used": real_capital_not_used,
    "micro_live_not_approved": micro_live_not_approved,
    "real_live_not_approved": real_live_not_approved,
}

blockers = [
    key
    for key, value in review_checks.items()
    if value is not True
]

passed = not blockers

decision = (
    "PHASE_23_TESTNET_MICRO_EXECUTION_REVIEW_COMPLETE_"
    "READY_FOR_SOAK_TEST_PLAN_NOT_APPROVED_FOR_LIVE_EXECUTION"
    if passed
    else
    "PHASE_23_TESTNET_MICRO_EXECUTION_REVIEW_FAILED_"
    "REVIEW_REQUIRED_NOT_APPROVED_FOR_LIVE_EXECUTION"
)

record = {
    "phase": "phase_23_21_testnet_micro_execution_review",
    "generated_at_unix": int(time.time()),
    "git_head": head,
    "git_branch": branch,
    "git_remote_origin": remote,
    "git_working_tree_clean_before_outputs": git_clean,
    "current_transition_status":
        "testnet_micro_execution_review_only_not_approved_for_live_execution",
    "testnet_micro_execution_review_passed": passed,
    "review_checks": review_checks,
    "blockers": blockers,
    "reviewed_testnet_result": {
        "testnet_order_submission_attempted": submission_attempted,
        "testnet_order_submission_succeeded": submission_succeeded,
        "testnet_micro_execution_completed": execution_completed,
        "testnet_hostname": testnet_environment.get("hostname"),
        "order_id_present": order_id_present,
        "order_status": order_response.get("status"),
        "executed_quantity": order_response.get("executedQty"),
        "cumulative_quote_quantity":
            order_response.get("cummulativeQuoteQty"),
    },
    "testnet_execution_validated": passed,
    "production_credentials_used": False,
    "production_exchange_order_submission": False,
    "real_capital_usage": False,
    "micro_live_deployment_started": False,
    "approved_for_micro_live_execution": False,
    "approved_for_real_live_trading": False,
    "approved_for_live": False,
    "production_api_key_usage": False,
    "execution_allowed": False,
    "exchange_order_submission": False,
    "decision": decision,
    "next_phase": "Phase 23.22 — Soak Test Plan",
}

write(OUT, record)
write(RUNTIME_OUT, record)
write(REVIEW_FILE, record)

print(f"Report written to: {OUT}")
print(f"Runtime state written to: {RUNTIME_OUT}")
print(f"Review file written to: {REVIEW_FILE}")
print(f"testnet_micro_execution_review_passed={passed}")
print(f"testnet_order_submission_succeeded={submission_succeeded}")
print(f"testnet_micro_execution_completed={execution_completed}")
print(f"order_id_present={order_id_present}")
print("production_credentials_used=False")
print("production_exchange_order_submission=False")
print("real_capital_usage=False")
print("approved_for_micro_live_execution=False")
print("approved_for_real_live_trading=False")
print(f"decision={decision}")

if blockers:
    print("blockers=" + ",".join(blockers))
