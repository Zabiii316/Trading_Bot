import json, os, subprocess, time
from pathlib import Path

OUT = Path("data/processed/phase23_paper_shadow_restart_plan.json")
RUNTIME_OUT = Path("runtime/phase23_paper_shadow_restart_plan_state.json")
PLAN_FILE = Path("data/processed/phase23_reopening/paper_shadow_restart_plan.json")

NO_ORDER_FILES = [
    Path("data/processed/phase23_no_order_submission_verification.json"),
    Path("runtime/phase23_no_order_submission_verification_state.json"),
    Path("data/processed/phase23_reopening/no_order_submission_verification.json"),
]

FINAL_END_STATE = Path("data/processed/phase22_project_final_end_state_record.json")

def run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True)

def git_value(cmd):
    r = run(cmd)
    return r.stdout.strip() if r.returncode == 0 else None

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
git_status = git_value(["git", "status", "--short"]) or ""
git_clean = git_status == ""

no_order_records = [load(p) for p in NO_ORDER_FILES]
final_state = load(FINAL_END_STATE)

no_order_verification_passed = (
    any_true(no_order_records, "no_order_submission_verification_passed")
    or any("PHASE_23_NO_ORDER_SUBMISSION_VERIFICATION_COMPLETE" in str(x.get("decision", "")) for x in no_order_records)
)

phase22_closed = (
    final_state.get("project_final_end_state_record_created") is True
    or "PHASE_22_PROJECT_FINAL_END_STATE_RECORD_CREATED" in str(final_state.get("decision", ""))
)

no_order_submission_verified = (
    any_true(no_order_records, "no_order_submission_verified")
    or no_order_verification_passed
)

signed_endpoint_called_false = any_false(no_order_records, "signed_endpoint_called")
account_endpoint_called_false = any_false(no_order_records, "account_endpoint_called")
order_endpoint_called_false = any_false(no_order_records, "order_endpoint_called")
network_call_made_false = any_false(no_order_records, "network_call_made")
exchange_order_submission_false = any_false(no_order_records, "exchange_order_submission")
production_credentials_used_false = any_false(no_order_records, "production_credentials_used")

flags = {
    "BINANCE_TESTNET": os.getenv("BINANCE_TESTNET", ""),
    "BINANCE_USE_TESTNET": os.getenv("BINANCE_USE_TESTNET", ""),
    "BINANCE_ENABLE_LIVE_TRADING": os.getenv("BINANCE_ENABLE_LIVE_TRADING", ""),
    "LIVE_TRADING_ALLOWED": os.getenv("LIVE_TRADING_ALLOWED", ""),
    "KILL_SWITCH_ENABLED": os.getenv("KILL_SWITCH_ENABLED", ""),
}

safe_flags_active = (
    flags["BINANCE_TESTNET"] == "true"
    and flags["BINANCE_USE_TESTNET"] == "true"
    and flags["BINANCE_ENABLE_LIVE_TRADING"] == "false"
    and flags["LIVE_TRADING_ALLOWED"] == "false"
)

kill_switch_enabled = flags["KILL_SWITCH_ENABLED"].lower() in {"true", "1", "yes", "enabled"}

trading_symbols = os.getenv("TRADING_SYMBOLS", "BTCUSDT")
micro_trade_notional = os.getenv("MICRO_TRADE_NOTIONAL_USDT", "")
max_order_notional = os.getenv("MAX_ORDER_NOTIONAL_USDT", "")
max_daily_loss = os.getenv("MAX_DAILY_LOSS_USDT", "")
max_position_size = os.getenv("MAX_POSITION_SIZE_USDT", "")

plan_checks = {
    "git_head_present": bool(head),
    "git_branch_present": bool(branch),
    "git_remote_origin_present": bool(remote),
    "git_working_tree_clean_before_outputs": git_clean,
    "phase22_final_end_state_present": FINAL_END_STATE.exists(),
    "phase22_closed_on_hold": phase22_closed,
    "phase23_12_no_order_verification_present": any(p.exists() for p in NO_ORDER_FILES),
    "phase23_12_no_order_verification_passed": no_order_verification_passed,
    "no_order_submission_verified": no_order_submission_verified,
    "safe_flags_active": safe_flags_active,
    "binance_testnet_true": flags["BINANCE_TESTNET"] == "true",
    "binance_use_testnet_true": flags["BINANCE_USE_TESTNET"] == "true",
    "live_trading_flag_false": flags["BINANCE_ENABLE_LIVE_TRADING"] == "false",
    "live_trading_allowed_false": flags["LIVE_TRADING_ALLOWED"] == "false",
    "kill_switch_enabled": kill_switch_enabled,
    "signed_endpoint_called_false": signed_endpoint_called_false,
    "account_endpoint_called_false": account_endpoint_called_false,
    "order_endpoint_called_false": order_endpoint_called_false,
    "network_call_made_false": network_call_made_false,
    "exchange_order_submission_false": exchange_order_submission_false,
    "production_credentials_used_false": production_credentials_used_false,
    "paper_shadow_started_false": True,
    "paper_shadow_start_approved_false": True,
    "execution_allowed_false": True,
    "approved_for_micro_live_execution_false": True,
    "approved_for_real_live_trading_false": True,
}

blockers = [k for k, v in plan_checks.items() if v is not True]
passed = not blockers

decision = (
    "PHASE_23_PAPER_SHADOW_RESTART_PLAN_CREATED_READY_FOR_PAPER_SHADOW_START_GATE_NOT_APPROVED_FOR_EXECUTION"
    if passed else
    "PHASE_23_PAPER_SHADOW_RESTART_PLAN_FAILED_REVIEW_REQUIRED_NOT_APPROVED_FOR_EXECUTION"
)

record = {
    "phase": "phase_23_13_paper_shadow_restart_plan",
    "generated_at_unix": int(time.time()),
    "git_head": head,
    "git_branch": branch,
    "git_remote_origin": remote,
    "git_working_tree_clean_before_outputs": git_clean,
    "current_transition_status": "paper_shadow_restart_plan_only_not_started_not_approved_for_execution",
    "paper_shadow_restart_plan_created": passed,
    "plan_checks": plan_checks,
    "blockers": blockers,
    "safe_flags": flags,
    "safe_flags_active": safe_flags_active,
    "kill_switch_enabled": kill_switch_enabled,
    "planned_scope": {
        "mode": "paper_shadow_planning_only",
        "trading_symbols": trading_symbols,
        "micro_trade_notional_usdt": micro_trade_notional,
        "max_order_notional_usdt": max_order_notional,
        "max_daily_loss_usdt": max_daily_loss,
        "max_position_size_usdt": max_position_size,
        "paper_shadow_engine_required": True,
        "exchange_submission_must_remain_disabled": True,
        "signed_endpoints_must_remain_disabled": True,
        "production_credentials_must_not_be_used": True,
        "manual_start_gate_required_next": True
    },
    "required_before_paper_shadow_start": [
        "Phase 23.14 paper shadow start gate must pass",
        "Execution flags must remain disabled",
        "Exchange order submission must remain false",
        "Paper shadow engine must write simulated events only",
        "No signed Binance endpoint may be called",
        "No production credential usage may occur",
        "Manual owner approval record must be created before any later live gate"
    ],
    "forbidden_in_this_phase": [
        "start paper shadow",
        "start monitoring",
        "run dry run execution",
        "run backtest",
        "call signed endpoint",
        "call account endpoint",
        "call order endpoint",
        "submit exchange order",
        "enable live trading",
        "use production credentials",
        "use real capital"
    ],
    "verified_source_phase": "phase_23_12_no_order_submission_verification",
    "no_order_submission_verified": no_order_submission_verified,
    "signed_endpoint_called": False,
    "account_endpoint_called": False,
    "order_endpoint_called": False,
    "network_call_made": False,
    "production_credentials_used": False,
    "paper_shadow_started": False,
    "paper_shadow_start_approved": False,
    "approved_for_paper_shadow_start": False,
    "micro_live_deployment_started": False,
    "monitoring_started": False,
    "run_dry_run_now": False,
    "run_backtest_now": False,
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
    "next_phase": "Phase 23.14 — Paper Shadow Start Gate"
}

write(OUT, record)
write(RUNTIME_OUT, record)
write(PLAN_FILE, record)

print(f"Report written to: {OUT}")
print(f"Runtime state written to: {RUNTIME_OUT}")
print(f"Plan file written to: {PLAN_FILE}")
print(f"paper_shadow_restart_plan_created={passed}")
print(f"safe_flags_active={safe_flags_active}")
print(f"kill_switch_enabled={kill_switch_enabled}")
print("current_transition_status=paper_shadow_restart_plan_only_not_started_not_approved_for_execution")
print("paper_shadow_started=False")
print("paper_shadow_start_approved=False")
print("approved_for_paper_shadow_start=False")
print("signed_endpoint_called=False")
print("account_endpoint_called=False")
print("order_endpoint_called=False")
print("network_call_made=False")
print("production_credentials_used=False")
print("execution_allowed=False")
print("exchange_order_submission=False")
print("approved_for_micro_live_execution=False")
print("approved_for_real_live_trading=False")
print("production_api_key_usage=False")
print("real_capital_usage=False")
print(f"decision={decision}")
if blockers:
    print("blockers=" + ",".join(blockers))
