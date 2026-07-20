import json
import os
import subprocess
import time
from pathlib import Path

OUT = Path(
    "data/processed/phase23_testnet_micro_execution_approval_gate.json"
)
RUNTIME_OUT = Path(
    "runtime/phase23_testnet_micro_execution_approval_gate_state.json"
)
GATE_FILE = Path(
    "data/processed/phase23_reopening/"
    "testnet_micro_execution_approval_gate.json"
)

PLAN_FILES = [
    Path("data/processed/phase23_testnet_micro_execution_plan.json"),
    Path("runtime/phase23_testnet_micro_execution_plan_state.json"),
    Path(
        "data/processed/phase23_reopening/"
        "testnet_micro_execution_plan.json"
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

def parse_positive(value):
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

plans = [load(path) for path in PLAN_FILES]

plan_created = (
    any_true(plans, "testnet_micro_execution_plan_created")
    or any(
        "PHASE_23_TESTNET_MICRO_EXECUTION_PLAN_CREATED"
        in str(item.get("decision", ""))
        for item in plans
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

micro_notional = parse_positive(
    os.getenv("MICRO_TRADE_NOTIONAL_USDT", "")
)
max_order = parse_positive(
    os.getenv("MAX_ORDER_NOTIONAL_USDT", "")
)
max_position = parse_positive(
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

manual_approval_env = os.getenv(
    "PHASE23_TESTNET_EXECUTION_APPROVED", ""
).lower()

manual_approval_present = manual_approval_env in {
    "true", "1", "yes", "approved"
}

checks = {
    "git_head_present": bool(head),
    "git_branch_present": bool(branch),
    "git_remote_origin_present": bool(remote),
    "git_working_tree_clean_before_outputs": git_clean,
    "phase23_18_plan_present": any(
        path.exists() for path in PLAN_FILES
    ),
    "phase23_18_plan_created": plan_created,
    "safe_flags_active": safe_flags_active,
    "binance_testnet_true":
        flags["BINANCE_TESTNET"] == "true",
    "binance_use_testnet_true":
        flags["BINANCE_USE_TESTNET"] == "true",
    "live_trading_flag_false":
        flags["BINANCE_ENABLE_LIVE_TRADING"] == "false",
    "live_trading_allowed_false":
        flags["LIVE_TRADING_ALLOWED"] == "false",
    "kill_switch_enabled": kill_switch_enabled,
    "micro_trade_notional_defined":
        micro_notional is not None,
    "max_order_notional_defined":
        max_order is not None,
    "max_position_size_defined":
        max_position is not None,
    "micro_notional_within_order_limit":
        micro_within_order,
    "order_limit_within_position_limit":
        order_within_position,
    "signed_endpoint_called_false": True,
    "account_endpoint_called_false": True,
    "order_endpoint_called_false": True,
    "exchange_order_submission_false": True,
}

blockers = [
    key for key, value in checks.items()
    if value is not True
]

gate_passed = not blockers

ready_for_manual_approval = gate_passed

testnet_execution_approved = (
    gate_passed and manual_approval_present
)

if testnet_execution_approved:
    decision = (
        "PHASE_23_TESTNET_MICRO_EXECUTION_APPROVAL_GATE_COMPLETE_"
        "MANUAL_TESTNET_APPROVAL_PRESENT_READY_FOR_CONTROLLED_TESTNET_RUN"
    )
elif gate_passed:
    decision = (
        "PHASE_23_TESTNET_MICRO_EXECUTION_APPROVAL_GATE_COMPLETE_"
        "READY_FOR_MANUAL_APPROVAL_NOT_APPROVED_FOR_EXECUTION"
    )
else:
    decision = (
        "PHASE_23_TESTNET_MICRO_EXECUTION_APPROVAL_GATE_FAILED_"
        "REVIEW_REQUIRED_NOT_APPROVED_FOR_EXECUTION"
    )

record = {
    "phase":
        "phase_23_19_testnet_micro_execution_approval_gate",
    "generated_at_unix": int(time.time()),
    "git_head": head,
    "git_branch": branch,
    "git_remote_origin": remote,
    "git_working_tree_clean_before_outputs": git_clean,
    "current_transition_status":
        "testnet_micro_execution_approval_gate",
    "testnet_micro_execution_approval_gate_passed":
        gate_passed,
    "ready_for_manual_testnet_approval":
        ready_for_manual_approval,
    "manual_testnet_approval_present":
        manual_approval_present,
    "testnet_micro_execution_approved":
        testnet_execution_approved,
    "approval_checks": checks,
    "blockers": blockers,
    "safe_flags": flags,
    "safe_flags_active": safe_flags_active,
    "kill_switch_enabled": kill_switch_enabled,
    "risk_limits": {
        "micro_trade_notional_usdt": micro_notional,
        "max_order_notional_usdt": max_order,
        "max_position_size_usdt": max_position,
        "micro_notional_within_order_limit":
            micro_within_order,
        "order_limit_within_position_limit":
            order_within_position,
    },
    "manual_approval_required": True,
    "testnet_micro_execution_started": False,
    "signed_endpoint_called": False,
    "account_endpoint_called": False,
    "order_endpoint_called": False,
    "network_call_made": False,
    "production_credentials_used": False,
    "exchange_order_submission": False,
    "real_capital_usage": False,
    "approved_for_micro_live_execution": False,
    "approved_for_real_live_trading": False,
    "production_api_key_usage": False,
    "decision": decision,
    "next_phase":
        "Phase 23.20 — Controlled Testnet Micro-Execution Run",
}

write(OUT, record)
write(RUNTIME_OUT, record)
write(GATE_FILE, record)

print(f"Report written to: {OUT}")
print(f"Runtime state written to: {RUNTIME_OUT}")
print(f"Gate file written to: {GATE_FILE}")
print(
    "testnet_micro_execution_approval_gate_passed="
    + str(gate_passed)
)
print(
    "ready_for_manual_testnet_approval="
    + str(ready_for_manual_approval)
)
print(
    "manual_testnet_approval_present="
    + str(manual_approval_present)
)
print(
    "testnet_micro_execution_approved="
    + str(testnet_execution_approved)
)
print(f"safe_flags_active={safe_flags_active}")
print(f"kill_switch_enabled={kill_switch_enabled}")
print("testnet_micro_execution_started=False")
print("exchange_order_submission=False")
print("approved_for_micro_live_execution=False")
print("approved_for_real_live_trading=False")
print(f"decision={decision}")

if blockers:
    print("blockers=" + ",".join(blockers))
