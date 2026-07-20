import json
import os
import subprocess
import time
from pathlib import Path

OUT = Path("data/processed/phase23_testnet_micro_execution_plan.json")
RUNTIME_OUT = Path("runtime/phase23_testnet_micro_execution_plan_state.json")
PLAN_FILE = Path("data/processed/phase23_reopening/testnet_micro_execution_plan.json")

RISK_REVIEW_FILES = [
    Path("data/processed/phase23_paper_shadow_risk_review.json"),
    Path("runtime/phase23_paper_shadow_risk_review_state.json"),
    Path("data/processed/phase23_reopening/paper_shadow_risk_review.json"),
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

def first_symbol(value):
    if not value:
        return "BTCUSDT"
    return value.split(",")[0].strip() or "BTCUSDT"

def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2))

head = git_value(["git", "rev-parse", "HEAD"])
branch = git_value(["git", "branch", "--show-current"])
remote = git_value(["git", "remote", "get-url", "origin"])
status_short = git_value(["git", "status", "--short"]) or ""
git_clean = status_short == ""

reviews = [load(path) for path in RISK_REVIEW_FILES]

risk_review_passed = (
    any_true(reviews, "paper_shadow_risk_review_passed")
    or any(
        "PHASE_23_PAPER_SHADOW_RISK_REVIEW_COMPLETE"
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

symbol = first_symbol(os.getenv("TRADING_SYMBOLS", "BTCUSDT"))
micro_notional = parse_positive(
    os.getenv("MICRO_TRADE_NOTIONAL_USDT", "")
)
max_order = parse_positive(
    os.getenv("MAX_ORDER_NOTIONAL_USDT", "")
)
max_daily_loss = parse_positive(
    os.getenv("MAX_DAILY_LOSS_USDT", "")
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

plan_checks = {
    "git_head_present": bool(head),
    "git_branch_present": bool(branch),
    "git_remote_origin_present": bool(remote),
    "git_working_tree_clean_before_outputs": git_clean,
    "phase23_17_risk_review_present": any(
        path.exists() for path in RISK_REVIEW_FILES
    ),
    "phase23_17_risk_review_passed": risk_review_passed,
    "safe_flags_active": safe_flags_active,
    "binance_testnet_true": flags["BINANCE_TESTNET"] == "true",
    "binance_use_testnet_true": flags["BINANCE_USE_TESTNET"] == "true",
    "live_trading_flag_false":
        flags["BINANCE_ENABLE_LIVE_TRADING"] == "false",
    "live_trading_allowed_false":
        flags["LIVE_TRADING_ALLOWED"] == "false",
    "kill_switch_enabled": kill_switch_enabled,
    "symbol_present": bool(symbol),
    "micro_trade_notional_defined": micro_notional is not None,
    "max_order_notional_defined": max_order is not None,
    "max_daily_loss_defined": max_daily_loss is not None,
    "max_position_size_defined": max_position is not None,
    "micro_notional_within_order_limit": micro_within_order,
    "order_limit_within_position_limit": order_within_position,
    "planning_only": True,
    "signed_endpoint_called_false": True,
    "account_endpoint_called_false": True,
    "order_endpoint_called_false": True,
    "exchange_order_submission_false": True,
}

blockers = [
    key for key, value in plan_checks.items()
    if value is not True
]

passed = not blockers

decision = (
    "PHASE_23_TESTNET_MICRO_EXECUTION_PLAN_CREATED_"
    "READY_FOR_APPROVAL_GATE_NOT_APPROVED_FOR_EXECUTION"
    if passed
    else
    "PHASE_23_TESTNET_MICRO_EXECUTION_PLAN_FAILED_"
    "REVIEW_REQUIRED_NOT_APPROVED_FOR_EXECUTION"
)

record = {
    "phase": "phase_23_18_testnet_micro_execution_plan",
    "generated_at_unix": int(time.time()),
    "git_head": head,
    "git_branch": branch,
    "git_remote_origin": remote,
    "git_working_tree_clean_before_outputs": git_clean,
    "current_transition_status":
        "testnet_micro_execution_plan_only_not_approved_for_execution",
    "testnet_micro_execution_plan_created": passed,
    "plan_checks": plan_checks,
    "blockers": blockers,
    "safe_flags": flags,
    "safe_flags_active": safe_flags_active,
    "kill_switch_enabled": kill_switch_enabled,
    "planned_testnet_micro_execution": {
        "symbol": symbol,
        "planned_notional_usdt": micro_notional,
        "max_order_notional_usdt": max_order,
        "max_daily_loss_usdt": max_daily_loss,
        "max_position_size_usdt": max_position,
        "planned_order_count": 1,
        "environment": "testnet",
        "requires_testnet_credentials": True,
        "requires_manual_approval_gate": True,
        "requires_pre_execution_kill_switch_check": True,
        "requires_post_execution_evidence_review": True,
        "order_submission_in_this_phase": False,
    },
    "execution_sequence_plan": [
        "Validate testnet-only credentials without printing secrets",
        "Confirm safe testnet endpoint",
        "Confirm kill switch is enabled before execution",
        "Confirm micro notional remains within configured limits",
        "Require Phase 23.19 approval gate",
        "Submit no order until a later explicitly approved testnet phase",
        "Capture response and immediately verify resulting testnet state",
    ],
    "testnet_micro_execution_started": False,
    "testnet_micro_execution_approved": False,
    "signed_endpoint_called": False,
    "account_endpoint_called": False,
    "order_endpoint_called": False,
    "network_call_made": False,
    "production_credentials_used": False,
    "paper_shadow_started": False,
    "monitoring_started": False,
    "execution_allowed": False,
    "approved_for_execution": False,
    "approved_for_live": False,
    "exchange_order_submission": False,
    "approved_for_micro_live_execution": False,
    "approved_for_real_live_trading": False,
    "production_api_key_usage": False,
    "real_capital_usage": False,
    "decision": decision,
    "next_phase": "Phase 23.19 — Testnet Micro-Execution Approval Gate",
}

write(OUT, record)
write(RUNTIME_OUT, record)
write(PLAN_FILE, record)

print(f"Report written to: {OUT}")
print(f"Runtime state written to: {RUNTIME_OUT}")
print(f"Plan file written to: {PLAN_FILE}")
print(f"testnet_micro_execution_plan_created={passed}")
print(f"safe_flags_active={safe_flags_active}")
print(f"kill_switch_enabled={kill_switch_enabled}")
print(f"symbol={symbol}")
print(f"planned_notional_usdt={micro_notional}")
print("testnet_micro_execution_started=False")
print("testnet_micro_execution_approved=False")
print("signed_endpoint_called=False")
print("account_endpoint_called=False")
print("order_endpoint_called=False")
print("network_call_made=False")
print("execution_allowed=False")
print("exchange_order_submission=False")
print("approved_for_micro_live_execution=False")
print("approved_for_real_live_trading=False")
print(f"decision={decision}")

if blockers:
    print("blockers=" + ",".join(blockers))
