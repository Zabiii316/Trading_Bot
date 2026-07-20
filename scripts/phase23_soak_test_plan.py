import json
import os
import subprocess
import time
from pathlib import Path

OUT = Path("data/processed/phase23_soak_test_plan.json")
RUNTIME_OUT = Path("runtime/phase23_soak_test_plan_state.json")
PLAN_FILE = Path("data/processed/phase23_reopening/soak_test_plan.json")

REVIEW_FILES = [
    Path("data/processed/phase23_testnet_micro_execution_review.json"),
    Path("runtime/phase23_testnet_micro_execution_review_state.json"),
    Path(
        "data/processed/phase23_reopening/"
        "testnet_micro_execution_review.json"
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

def positive_int(value, default):
    try:
        number = int(value)
        return number if number > 0 else default
    except Exception:
        return default

def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2))

head = git_value(["git", "rev-parse", "HEAD"])
branch = git_value(["git", "branch", "--show-current"])
remote = git_value(["git", "remote", "get-url", "origin"])
status_short = git_value(["git", "status", "--short"]) or ""
git_clean = status_short == ""

reviews = [load(path) for path in REVIEW_FILES]

execution_review_passed = (
    any_true(reviews, "testnet_micro_execution_review_passed")
    or any(
        "PHASE_23_TESTNET_MICRO_EXECUTION_REVIEW_COMPLETE"
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

kill_switch_enabled = (
    flags["KILL_SWITCH_ENABLED"].lower()
    in {"true", "1", "yes", "enabled"}
)

duration_minutes = positive_int(
    os.getenv("SOAK_TEST_DURATION_MINUTES", "120"),
    120,
)

sample_interval_seconds = positive_int(
    os.getenv("SOAK_TEST_SAMPLE_INTERVAL_SECONDS", "60"),
    60,
)

max_consecutive_errors = positive_int(
    os.getenv("SOAK_TEST_MAX_CONSECUTIVE_ERRORS", "3"),
    3,
)

checks = {
    "git_head_present": bool(head),
    "git_branch_present": bool(branch),
    "git_remote_origin_present": bool(remote),
    "git_working_tree_clean_before_outputs": git_clean,
    "phase23_21_review_present": any(
        path.exists() for path in REVIEW_FILES
    ),
    "phase23_21_review_passed": execution_review_passed,
    "safe_flags_active": safe_flags_active,
    "binance_testnet_true": flags["BINANCE_TESTNET"] == "true",
    "binance_use_testnet_true": flags["BINANCE_USE_TESTNET"] == "true",
    "live_trading_flag_false":
        flags["BINANCE_ENABLE_LIVE_TRADING"] == "false",
    "live_trading_allowed_false":
        flags["LIVE_TRADING_ALLOWED"] == "false",
    "kill_switch_enabled": kill_switch_enabled,
    "duration_positive": duration_minutes > 0,
    "sample_interval_positive": sample_interval_seconds > 0,
    "max_consecutive_errors_positive": max_consecutive_errors > 0,
    "planning_only": True,
    "testnet_order_submission_false": True,
    "production_order_submission_false": True,
    "micro_live_approval_false": True,
    "real_live_approval_false": True,
}

blockers = [
    key for key, value in checks.items()
    if value is not True
]

passed = not blockers

decision = (
    "PHASE_23_SOAK_TEST_PLAN_CREATED_"
    "READY_FOR_SOAK_TEST_EXECUTION_NOT_APPROVED_FOR_LIVE_EXECUTION"
    if passed
    else
    "PHASE_23_SOAK_TEST_PLAN_FAILED_"
    "REVIEW_REQUIRED_NOT_APPROVED_FOR_LIVE_EXECUTION"
)

record = {
    "phase": "phase_23_22_soak_test_plan",
    "generated_at_unix": int(time.time()),
    "git_head": head,
    "git_branch": branch,
    "git_remote_origin": remote,
    "git_working_tree_clean_before_outputs": git_clean,
    "current_transition_status":
        "soak_test_plan_only_not_started_not_approved_for_live_execution",
    "soak_test_plan_created": passed,
    "plan_checks": checks,
    "blockers": blockers,
    "safe_flags": flags,
    "safe_flags_active": safe_flags_active,
    "kill_switch_enabled": kill_switch_enabled,
    "soak_test_plan": {
        "environment": "binance_spot_testnet",
        "duration_minutes": duration_minutes,
        "sample_interval_seconds": sample_interval_seconds,
        "max_consecutive_errors": max_consecutive_errors,
        "order_submission_during_soak": False,
        "production_credentials_allowed": False,
        "production_endpoint_allowed": False,
        "real_capital_allowed": False,
        "metrics_to_capture": [
            "heartbeat_status",
            "public_testnet_connectivity",
            "latency_ms",
            "error_count",
            "consecutive_error_count",
            "safe_flag_state",
            "kill_switch_state",
        ],
        "abort_conditions": [
            "safe trading flag changes unexpectedly",
            "kill switch becomes disabled",
            "production endpoint is detected",
            "production credentials are detected",
            "consecutive errors exceed configured threshold",
            "unexpected order submission is detected",
        ],
        "rate_limit_policy": {
            "retry_on_429_immediately": False,
            "respect_retry_after": True,
            "backoff_required": True,
        },
    },
    "soak_test_started": False,
    "soak_test_completed": False,
    "monitoring_started": False,
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
    "next_phase": "Phase 23.23 — Soak Test Execution",
}

write(OUT, record)
write(RUNTIME_OUT, record)
write(PLAN_FILE, record)

print(f"Report written to: {OUT}")
print(f"Runtime state written to: {RUNTIME_OUT}")
print(f"Plan file written to: {PLAN_FILE}")
print(f"soak_test_plan_created={passed}")
print(f"safe_flags_active={safe_flags_active}")
print(f"kill_switch_enabled={kill_switch_enabled}")
print(f"duration_minutes={duration_minutes}")
print(f"sample_interval_seconds={sample_interval_seconds}")
print(f"max_consecutive_errors={max_consecutive_errors}")
print("soak_test_started=False")
print("soak_test_completed=False")
print("testnet_order_submission=False")
print("production_exchange_order_submission=False")
print("approved_for_micro_live_execution=False")
print("approved_for_real_live_trading=False")
print("real_capital_usage=False")
print(f"decision={decision}")

if blockers:
    print("blockers=" + ",".join(blockers))
