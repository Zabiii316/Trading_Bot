import json
import os
import subprocess
import time
from pathlib import Path

OUT = Path("data/processed/phase23_paper_shadow_risk_review.json")
RUNTIME_OUT = Path("runtime/phase23_paper_shadow_risk_review_state.json")
REVIEW_FILE = Path("data/processed/phase23_reopening/paper_shadow_risk_review.json")

RESULT_REVIEW_FILES = [
    Path("data/processed/phase23_paper_shadow_result_review.json"),
    Path("runtime/phase23_paper_shadow_result_review_state.json"),
    Path("data/processed/phase23_reopening/paper_shadow_result_review.json"),
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

reviews = [load(path) for path in RESULT_REVIEW_FILES]

result_review_passed = (
    any_true(reviews, "paper_shadow_result_review_passed")
    or any(
        "PHASE_23_PAPER_SHADOW_RESULT_REVIEW_COMPLETE"
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

risk_checks = {
    "git_head_present": bool(head),
    "git_branch_present": bool(branch),
    "git_remote_origin_present": bool(remote),
    "git_working_tree_clean_before_outputs": git_clean,
    "phase23_16_result_review_present": any(
        path.exists() for path in RESULT_REVIEW_FILES
    ),
    "phase23_16_result_review_passed": result_review_passed,
    "safe_flags_active": safe_flags_active,
    "kill_switch_enabled": kill_switch_enabled,
    "micro_trade_notional_defined": micro_notional is not None,
    "max_order_notional_defined": max_order is not None,
    "max_daily_loss_defined": max_daily_loss is not None,
    "max_position_size_defined": max_position is not None,
    "micro_notional_within_order_limit": micro_within_order,
    "order_limit_within_position_limit": order_within_position,
    "paper_shadow_not_started": True,
    "monitoring_not_started": True,
    "execution_allowed_false": True,
    "exchange_order_submission_false": True,
    "micro_live_approval_false": True,
    "real_live_approval_false": True,
}

blockers = [
    key for key, value in risk_checks.items()
    if value is not True
]

passed = not blockers

decision = (
    "PHASE_23_PAPER_SHADOW_RISK_REVIEW_COMPLETE_"
    "READY_FOR_TESTNET_MICRO_EXECUTION_PLAN_"
    "NOT_APPROVED_FOR_EXECUTION"
    if passed
    else
    "PHASE_23_PAPER_SHADOW_RISK_REVIEW_FAILED_"
    "REVIEW_REQUIRED_NOT_APPROVED_FOR_EXECUTION"
)

record = {
    "phase": "phase_23_17_paper_shadow_risk_review",
    "generated_at_unix": int(time.time()),
    "git_head": head,
    "git_branch": branch,
    "git_remote_origin": remote,
    "git_working_tree_clean_before_outputs": git_clean,
    "current_transition_status":
        "paper_shadow_risk_review_only_not_approved_for_execution",
    "paper_shadow_risk_review_passed": passed,
    "risk_checks": risk_checks,
    "blockers": blockers,
    "risk_limits": {
        "micro_trade_notional_usdt": micro_notional,
        "max_order_notional_usdt": max_order,
        "max_daily_loss_usdt": max_daily_loss,
        "max_position_size_usdt": max_position,
        "micro_notional_within_order_limit": micro_within_order,
        "order_limit_within_position_limit": order_within_position,
    },
    "safe_flags": flags,
    "safe_flags_active": safe_flags_active,
    "kill_switch_enabled": kill_switch_enabled,
    "runtime_results_available": False,
    "paper_shadow_started": False,
    "monitoring_started": False,
    "run_dry_run_now": False,
    "run_backtest_now": False,
    "signed_endpoint_called": False,
    "account_endpoint_called": False,
    "order_endpoint_called": False,
    "production_credentials_used": False,
    "execution_allowed": False,
    "approved_for_execution": False,
    "approved_for_paper_shadow": False,
    "approved_for_live": False,
    "exchange_order_submission": False,
    "approved_for_micro_live_execution": False,
    "approved_for_real_live_trading": False,
    "production_api_key_usage": False,
    "real_capital_usage": False,
    "decision": decision,
    "next_phase": "Phase 23.18 — Testnet Micro-Execution Plan",
}

write(OUT, record)
write(RUNTIME_OUT, record)
write(REVIEW_FILE, record)

print(f"Report written to: {OUT}")
print(f"Runtime state written to: {RUNTIME_OUT}")
print(f"Review file written to: {REVIEW_FILE}")
print(f"paper_shadow_risk_review_passed={passed}")
print(f"safe_flags_active={safe_flags_active}")
print(f"kill_switch_enabled={kill_switch_enabled}")
print(f"micro_notional_within_order_limit={micro_within_order}")
print(f"order_limit_within_position_limit={order_within_position}")
print("paper_shadow_started=False")
print("monitoring_started=False")
print("execution_allowed=False")
print("exchange_order_submission=False")
print("approved_for_micro_live_execution=False")
print("approved_for_real_live_trading=False")
print(f"decision={decision}")

if blockers:
    print("blockers=" + ",".join(blockers))
