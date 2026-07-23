import json
import os
import subprocess
import time
import urllib.parse
from pathlib import Path

OUT = Path("data/processed/phase23_production_readiness_review.json")
RUNTIME_OUT = Path("runtime/phase23_production_readiness_review_state.json")
REVIEW_FILE = Path(
    "data/processed/phase23_reopening/production_readiness_review.json"
)

TESTNET_RUN_FILES = [
    Path("data/processed/phase23_controlled_testnet_micro_execution_run.json"),
    Path("runtime/phase23_controlled_testnet_micro_execution_run_state.json"),
]

TESTNET_REVIEW_FILES = [
    Path("data/processed/phase23_testnet_micro_execution_review.json"),
    Path("runtime/phase23_testnet_micro_execution_review_state.json"),
]

SOAK_EXECUTION_FILES = [
    Path("data/processed/phase23_soak_test_execution.json"),
    Path("runtime/phase23_soak_test_execution_state.json"),
]

SOAK_REVIEW_FILES = [
    Path("data/processed/phase23_soak_test_review.json"),
    Path("runtime/phase23_soak_test_review_state.json"),
]

KILL_SWITCH_FILES = [
    Path("data/processed/phase23_incident_kill_switch_retest.json"),
    Path("runtime/phase23_incident_kill_switch_retest_state.json"),
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

def load_all(paths):
    return [load(path) for path in paths]

def any_true(items, key):
    return any(item.get(key) is True for item in items)

def first_value(items, key, default=None):
    for item in items:
        value = item.get(key)
        if value not in (None, ""):
            return value
    return default

def positive_number(value):
    try:
        number = float(value)
        return number if number > 0 else None
    except Exception:
        return None

def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2))

head = git_value(["git", "rev-parse", "HEAD"])
branch = git_value(["git", "branch", "--show-current"])
remote = git_value(["git", "remote", "get-url", "origin"])
status_short = git_value(["git", "status", "--short"]) or ""
git_clean = status_short == ""

testnet_runs = load_all(TESTNET_RUN_FILES)
testnet_reviews = load_all(TESTNET_REVIEW_FILES)
soak_executions = load_all(SOAK_EXECUTION_FILES)
soak_reviews = load_all(SOAK_REVIEW_FILES)
kill_switch_reviews = load_all(KILL_SWITCH_FILES)

testnet_execution_completed = any_true(
    testnet_runs,
    "testnet_micro_execution_completed",
)

testnet_order_succeeded = any_true(
    testnet_runs,
    "testnet_order_submission_succeeded",
)

testnet_review_passed = any_true(
    testnet_reviews,
    "testnet_micro_execution_review_passed",
)

soak_execution_passed = any_true(
    soak_executions,
    "soak_test_execution_passed",
)

soak_review_passed = any_true(
    soak_reviews,
    "soak_test_review_passed",
)

kill_switch_retest_passed = any_true(
    kill_switch_reviews,
    "incident_kill_switch_retest_passed",
)

flags = {
    "BINANCE_TESTNET": os.getenv("BINANCE_TESTNET", ""),
    "BINANCE_USE_TESTNET": os.getenv("BINANCE_USE_TESTNET", ""),
    "BINANCE_ENABLE_LIVE_TRADING":
        os.getenv("BINANCE_ENABLE_LIVE_TRADING", ""),
    "LIVE_TRADING_ALLOWED":
        os.getenv("LIVE_TRADING_ALLOWED", ""),
    "KILL_SWITCH_ENABLED":
        os.getenv("KILL_SWITCH_ENABLED", ""),
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

micro_notional = positive_number(
    os.getenv("MICRO_TRADE_NOTIONAL_USDT", "")
)

max_order = positive_number(
    os.getenv("MAX_ORDER_NOTIONAL_USDT", "")
)

max_daily_loss = positive_number(
    os.getenv("MAX_DAILY_LOSS_USDT", "")
)

max_position = positive_number(
    os.getenv("MAX_POSITION_SIZE_USDT", "")
)

micro_within_order = (
    micro_notional is not None
    and max_order is not None
    and micro_notional <= max_order
)

order_within_position = (
    max_order is not None
    and max_position is not None
    and max_order <= max_position
)

production_credentials_absent = (
    not os.getenv("BINANCE_API_KEY")
    and not os.getenv("BINANCE_API_SECRET")
)

testnet_base_url = os.getenv(
    "BINANCE_TESTNET_BASE_URL",
    "https://testnet.binance.vision",
)

testnet_hostname = (
    urllib.parse.urlparse(testnet_base_url).hostname
    or ""
).lower()

testnet_endpoint_confirmed = (
    testnet_hostname == "testnet.binance.vision"
)

soak_samples = (
    first_value(
        soak_executions,
        "samples_collected",
        0,
    )
    or 0
)

soak_failed_samples = (
    first_value(
        soak_executions,
        "failed_samples",
        0,
    )
    or 0
)

soak_abort_reason = first_value(
    soak_executions,
    "abort_reason",
    None,
)

readiness_checks = {
    "git_head_present": bool(head),
    "git_branch_present": bool(branch),
    "git_remote_origin_present": bool(remote),
    "git_working_tree_clean_before_outputs": git_clean,

    "phase23_20_testnet_run_present":
        any(path.exists() for path in TESTNET_RUN_FILES),

    "phase23_20_testnet_execution_completed":
        testnet_execution_completed,

    "phase23_20_testnet_order_succeeded":
        testnet_order_succeeded,

    "phase23_21_testnet_review_present":
        any(path.exists() for path in TESTNET_REVIEW_FILES),

    "phase23_21_testnet_review_passed":
        testnet_review_passed,

    "phase23_23_soak_execution_present":
        any(path.exists() for path in SOAK_EXECUTION_FILES),

    "phase23_23_soak_execution_passed":
        soak_execution_passed,

    "phase23_24_soak_review_present":
        any(path.exists() for path in SOAK_REVIEW_FILES),

    "phase23_24_soak_review_passed":
        soak_review_passed,

    "phase23_25_kill_switch_retest_present":
        any(path.exists() for path in KILL_SWITCH_FILES),

    "phase23_25_kill_switch_retest_passed":
        kill_switch_retest_passed,

    "safe_flags_active":
        safe_flags_active,

    "kill_switch_enabled":
        kill_switch_enabled,

    "testnet_endpoint_confirmed":
        testnet_endpoint_confirmed,

    "production_credentials_absent":
        production_credentials_absent,

    "micro_trade_notional_defined":
        micro_notional is not None,

    "max_order_notional_defined":
        max_order is not None,

    "max_daily_loss_defined":
        max_daily_loss is not None,

    "max_position_size_defined":
        max_position is not None,

    "micro_notional_within_order_limit":
        micro_within_order,

    "order_limit_within_position_limit":
        order_within_position,

    "soak_samples_positive":
        soak_samples > 0,

    "soak_failed_samples_zero":
        soak_failed_samples == 0,

    "soak_abort_reason_none":
        soak_abort_reason is None,

    "production_execution_still_disabled":
        flags["BINANCE_ENABLE_LIVE_TRADING"] == "false",

    "live_trading_still_not_allowed":
        flags["LIVE_TRADING_ALLOWED"] == "false",
}

blockers = [
    key
    for key, value in readiness_checks.items()
    if value is not True
]

review_passed = not blockers

if review_passed:
    decision = (
        "PHASE_23_PRODUCTION_READINESS_REVIEW_COMPLETE_"
        "TECHNICALLY_READY_FOR_CAPITAL_LIMIT_APPROVAL_PROCESS_"
        "NOT_APPROVED_FOR_LIVE_EXECUTION"
    )
else:
    decision = (
        "PHASE_23_PRODUCTION_READINESS_REVIEW_FAILED_"
        "REMEDIATION_REQUIRED_NOT_APPROVED_FOR_LIVE_EXECUTION"
    )

record = {
    "phase":
        "phase_23_26_production_readiness_review",

    "generated_at_unix":
        int(time.time()),

    "git_head":
        head,

    "git_branch":
        branch,

    "git_remote_origin":
        remote,

    "git_working_tree_clean_before_outputs":
        git_clean,

    "current_transition_status":
        "production_readiness_review_only_not_approved_for_live_execution",

    "production_readiness_review_passed":
        review_passed,

    "technical_readiness_for_next_approval_steps":
        review_passed,

    "readiness_checks":
        readiness_checks,

    "blockers":
        blockers,

    "safe_flags":
        flags,

    "safe_flags_active":
        safe_flags_active,

    "kill_switch_enabled":
        kill_switch_enabled,

    "risk_limits": {
        "micro_trade_notional_usdt":
            micro_notional,

        "max_order_notional_usdt":
            max_order,

        "max_daily_loss_usdt":
            max_daily_loss,

        "max_position_size_usdt":
            max_position,

        "micro_notional_within_order_limit":
            micro_within_order,

        "order_limit_within_position_limit":
            order_within_position,
    },

    "validated_testnet_lifecycle": {
        "controlled_testnet_execution_completed":
            testnet_execution_completed,

        "controlled_testnet_order_succeeded":
            testnet_order_succeeded,

        "testnet_execution_review_passed":
            testnet_review_passed,

        "soak_test_execution_passed":
            soak_execution_passed,

        "soak_test_review_passed":
            soak_review_passed,

        "kill_switch_retest_passed":
            kill_switch_retest_passed,

        "soak_samples_collected":
            soak_samples,

        "soak_failed_samples":
            soak_failed_samples,
    },

    "production_credentials_present":
        not production_credentials_absent,

    "production_credentials_used":
        False,

    "production_credentials_required_now":
        False,

    "capital_limit_approval_record_created":
        False,

    "manual_owner_live_approval_present":
        False,

    "final_go_no_go_completed":
        False,

    "micro_live_deployment_started":
        False,

    "production_execution_started":
        False,

    "execution_allowed":
        False,

    "approved_for_execution":
        False,

    "approved_for_micro_live_execution":
        False,

    "approved_for_real_live_trading":
        False,

    "approved_for_live":
        False,

    "exchange_order_submission":
        False,

    "production_exchange_order_submission":
        False,

    "production_api_key_usage":
        False,

    "real_capital_usage":
        False,

    "decision":
        decision,

    "next_phase":
        "Phase 23.27 — Capital Limit Approval Record",
}

write(OUT, record)
write(RUNTIME_OUT, record)
write(REVIEW_FILE, record)

print(f"Report written to: {OUT}")
print(f"Runtime state written to: {RUNTIME_OUT}")
print(f"Review file written to: {REVIEW_FILE}")

print(
    "production_readiness_review_passed="
    + str(review_passed)
)

print(
    "technical_readiness_for_next_approval_steps="
    + str(review_passed)
)

print(
    f"testnet_execution_completed="
    f"{testnet_execution_completed}"
)

print(
    f"soak_test_execution_passed="
    f"{soak_execution_passed}"
)

print(
    f"soak_test_review_passed="
    f"{soak_review_passed}"
)

print(
    f"kill_switch_retest_passed="
    f"{kill_switch_retest_passed}"
)

print(
    f"safe_flags_active="
    f"{safe_flags_active}"
)

print(
    f"production_credentials_absent="
    f"{production_credentials_absent}"
)

print("production_execution_started=False")
print("execution_allowed=False")
print("approved_for_micro_live_execution=False")
print("approved_for_real_live_trading=False")
print("production_exchange_order_submission=False")
print("real_capital_usage=False")
print(f"decision={decision}")

if blockers:
    print("blockers=" + ",".join(blockers))
