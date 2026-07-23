import json
import os
import subprocess
import time
from pathlib import Path

OUT = Path("data/processed/phase23_capital_limit_approval_record.json")
RUNTIME_OUT = Path("runtime/phase23_capital_limit_approval_record_state.json")
RECORD_FILE = Path(
    "data/processed/phase23_reopening/capital_limit_approval_record.json"
)

READINESS_FILES = [
    Path("data/processed/phase23_production_readiness_review.json"),
    Path("runtime/phase23_production_readiness_review_state.json"),
    Path(
        "data/processed/phase23_reopening/"
        "production_readiness_review.json"
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

readiness_records = [load(path) for path in READINESS_FILES]

production_readiness_passed = (
    any_true(
        readiness_records,
        "production_readiness_review_passed",
    )
    or any(
        "PHASE_23_PRODUCTION_READINESS_REVIEW_COMPLETE"
        in str(item.get("decision", ""))
        for item in readiness_records
    )
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

micro_trade_notional = positive_number(
    os.getenv("MICRO_TRADE_NOTIONAL_USDT", "")
)

max_order_notional = positive_number(
    os.getenv("MAX_ORDER_NOTIONAL_USDT", "")
)

max_daily_loss = positive_number(
    os.getenv("MAX_DAILY_LOSS_USDT", "")
)

max_position_size = positive_number(
    os.getenv("MAX_POSITION_SIZE_USDT", "")
)

micro_within_order = (
    micro_trade_notional is not None
    and max_order_notional is not None
    and micro_trade_notional <= max_order_notional
)

order_within_position = (
    max_order_notional is not None
    and max_position_size is not None
    and max_order_notional <= max_position_size
)

production_credentials_absent = (
    not os.getenv("BINANCE_API_KEY")
    and not os.getenv("BINANCE_API_SECRET")
)

checks = {
    "git_head_present": bool(head),
    "git_branch_present": bool(branch),
    "git_remote_origin_present": bool(remote),
    "git_working_tree_clean_before_outputs": git_clean,

    "phase23_26_readiness_present":
        any(path.exists() for path in READINESS_FILES),

    "phase23_26_readiness_passed":
        production_readiness_passed,

    "safe_flags_active":
        safe_flags_active,

    "kill_switch_enabled":
        kill_switch_enabled,

    "production_credentials_absent":
        production_credentials_absent,

    "micro_trade_notional_defined":
        micro_trade_notional is not None,

    "max_order_notional_defined":
        max_order_notional is not None,

    "max_daily_loss_defined":
        max_daily_loss is not None,

    "max_position_size_defined":
        max_position_size is not None,

    "micro_notional_within_order_limit":
        micro_within_order,

    "order_limit_within_position_limit":
        order_within_position,

    "production_execution_disabled":
        flags["BINANCE_ENABLE_LIVE_TRADING"] == "false",

    "live_trading_not_allowed":
        flags["LIVE_TRADING_ALLOWED"] == "false",
}

blockers = [
    key
    for key, value in checks.items()
    if value is not True
]

passed = not blockers

decision = (
    "PHASE_23_CAPITAL_LIMIT_APPROVAL_RECORD_CREATED_"
    "READY_FOR_MANUAL_OWNER_APPROVAL_RECORD_"
    "NOT_APPROVED_FOR_LIVE_EXECUTION"
    if passed
    else
    "PHASE_23_CAPITAL_LIMIT_APPROVAL_RECORD_FAILED_"
    "REVIEW_REQUIRED_NOT_APPROVED_FOR_LIVE_EXECUTION"
)

record = {
    "phase": "phase_23_27_capital_limit_approval_record",
    "generated_at_unix": int(time.time()),

    "git_head": head,
    "git_branch": branch,
    "git_remote_origin": remote,
    "git_working_tree_clean_before_outputs": git_clean,

    "current_transition_status":
        "capital_limit_record_only_not_approved_for_live_execution",

    "capital_limit_approval_record_created":
        passed,

    "capital_limits_technically_valid":
        passed,

    "capital_limits_approved_for_next_review":
        passed,

    "capital_limits_approved_for_live_use":
        False,

    "approval_checks":
        checks,

    "blockers":
        blockers,

    "safe_flags":
        flags,

    "safe_flags_active":
        safe_flags_active,

    "kill_switch_enabled":
        kill_switch_enabled,

    "capital_limit_record": {
        "micro_trade_notional_usdt":
            micro_trade_notional,

        "maximum_single_order_notional_usdt":
            max_order_notional,

        "maximum_daily_loss_usdt":
            max_daily_loss,

        "maximum_position_size_usdt":
            max_position_size,

        "micro_notional_within_order_limit":
            micro_within_order,

        "order_limit_within_position_limit":
            order_within_position,

        "hard_limit_enforcement_required":
            True,

        "kill_switch_required":
            True,

        "manual_owner_approval_required":
            True,

        "final_go_no_go_required":
            True,
    },

    "manual_owner_live_approval_present":
        False,

    "final_go_no_go_completed":
        False,

    "production_credentials_present":
        False,

    "production_credentials_used":
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
        "Phase 23.28 — Manual Owner Approval Record",
}

write(OUT, record)
write(RUNTIME_OUT, record)
write(RECORD_FILE, record)

print(f"Report written to: {OUT}")
print(f"Runtime state written to: {RUNTIME_OUT}")
print(f"Record file written to: {RECORD_FILE}")

print(
    "capital_limit_approval_record_created="
    + str(passed)
)

print(
    "capital_limits_technically_valid="
    + str(passed)
)

print(
    "capital_limits_approved_for_next_review="
    + str(passed)
)

print("capital_limits_approved_for_live_use=False")

print(
    f"micro_trade_notional_usdt="
    f"{micro_trade_notional}"
)

print(
    f"maximum_single_order_notional_usdt="
    f"{max_order_notional}"
)

print(
    f"maximum_daily_loss_usdt="
    f"{max_daily_loss}"
)

print(
    f"maximum_position_size_usdt="
    f"{max_position_size}"
)

print("manual_owner_live_approval_present=False")
print("production_execution_started=False")
print("execution_allowed=False")
print("approved_for_micro_live_execution=False")
print("approved_for_real_live_trading=False")
print("production_exchange_order_submission=False")
print("real_capital_usage=False")
print(f"decision={decision}")

if blockers:
    print("blockers=" + ",".join(blockers))
