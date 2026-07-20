import json, os, subprocess, time
from pathlib import Path

OUT = Path("data/processed/phase23_order_construction_safety_test.json")
RUNTIME_OUT = Path("runtime/phase23_order_construction_safety_test_state.json")
REOPEN_DIR = Path("data/processed/phase23_reopening")
TEST_FILE = REOPEN_DIR / "order_construction_safety_test.json"

ADAPTER_VALIDATION_FILES = [
    Path("data/processed/phase23_exchange_adapter_dry_run_validation.json"),
    Path("runtime/phase23_exchange_adapter_dry_run_validation_state.json"),
    Path("data/processed/phase23_reopening/exchange_adapter_dry_run_validation.json"),
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

def first_value(items, key, default=None):
    for item in items:
        value = item.get(key)
        if value not in (None, ""):
            return value
    return default

def parse_positive_number(value):
    try:
        if value in (None, ""):
            return None
        number = float(value)
        return number if number > 0 else None
    except Exception:
        return None

def first_symbol(symbols):
    if not symbols:
        return "BTCUSDT"
    return symbols.split(",")[0].strip() or "BTCUSDT"

def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2))

head = git_value(["git", "rev-parse", "HEAD"])
branch = git_value(["git", "branch", "--show-current"])
remote = git_value(["git", "remote", "get-url", "origin"])
status_short = git_value(["git", "status", "--short"]) or ""
git_clean = status_short == ""

adapter_records = [load(p) for p in ADAPTER_VALIDATION_FILES]
final_state = load(FINAL_END_STATE)

adapter_validation_passed = (
    any_true(adapter_records, "exchange_adapter_dry_run_validation_passed")
    or any("PHASE_23_EXCHANGE_ADAPTER_DRY_RUN_VALIDATION_COMPLETE" in str(x.get("decision", "")) for x in adapter_records)
)

phase22_closed = (
    final_state.get("project_final_end_state_record_created") is True
    or "PHASE_22_PROJECT_FINAL_END_STATE_RECORD_CREATED" in str(final_state.get("decision", ""))
)

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
symbol = first_symbol(trading_symbols)

micro_trade_notional = parse_positive_number(os.getenv("MICRO_TRADE_NOTIONAL_USDT"))
max_order_notional = parse_positive_number(os.getenv("MAX_ORDER_NOTIONAL_USDT"))
max_daily_loss = parse_positive_number(os.getenv("MAX_DAILY_LOSS_USDT"))
max_position_size = parse_positive_number(os.getenv("MAX_POSITION_SIZE_USDT"))

micro_notional_within_order_limit = (
    micro_trade_notional is not None
    and max_order_notional is not None
    and micro_trade_notional <= max_order_notional
)

order_limit_within_position_limit = (
    max_order_notional is not None
    and max_position_size is not None
    and max_order_notional <= max_position_size
)

daily_loss_positive = max_daily_loss is not None and max_daily_loss > 0

simulated_order_payload = {
    "symbol": symbol,
    "side": "BUY",
    "type": "MARKET",
    "quoteOrderQty": str(micro_trade_notional) if micro_trade_notional is not None else None,
    "timeInForce": None,
    "clientOrderId": "SIMULATED_ONLY_PHASE_23_11",
}

forbidden_payload_keys = {"apiKey", "secret", "signature", "timestamp", "recvWindow"}
payload_keys_lower = {str(k).lower() for k in simulated_order_payload.keys()}
payload_contains_forbidden_keys = any(k.lower() in payload_keys_lower for k in forbidden_payload_keys)

risk_findings = []

if not symbol:
    risk_findings.append("Trading symbol is missing")
if micro_trade_notional is None:
    risk_findings.append("MICRO_TRADE_NOTIONAL_USDT is missing or invalid")
if max_order_notional is None:
    risk_findings.append("MAX_ORDER_NOTIONAL_USDT is missing or invalid")
if max_daily_loss is None:
    risk_findings.append("MAX_DAILY_LOSS_USDT is missing or invalid")
if max_position_size is None:
    risk_findings.append("MAX_POSITION_SIZE_USDT is missing or invalid")
if not kill_switch_enabled:
    risk_findings.append("KILL_SWITCH_ENABLED is not true/enabled")
if micro_trade_notional is not None and max_order_notional is not None and not micro_notional_within_order_limit:
    risk_findings.append("Simulated order notional exceeds max order notional")
if max_order_notional is not None and max_position_size is not None and not order_limit_within_position_limit:
    risk_findings.append("Max order notional exceeds max position size")
if payload_contains_forbidden_keys:
    risk_findings.append("Simulated order payload contains forbidden signed/secret fields")

risk_payload_safe = len(risk_findings) == 0

test_checks = {
    "git_head_present": bool(head),
    "git_branch_present": bool(branch),
    "git_remote_origin_present": bool(remote),
    "git_working_tree_clean_before_outputs": git_clean,
    "phase22_final_end_state_present": FINAL_END_STATE.exists(),
    "phase22_closed_on_hold": phase22_closed,
    "phase23_10_adapter_validation_present": any(p.exists() for p in ADAPTER_VALIDATION_FILES),
    "phase23_10_adapter_validation_passed": adapter_validation_passed,
    "safe_flags_active": safe_flags_active,
    "binance_testnet_true": flags["BINANCE_TESTNET"] == "true",
    "binance_use_testnet_true": flags["BINANCE_USE_TESTNET"] == "true",
    "live_trading_flag_false": flags["BINANCE_ENABLE_LIVE_TRADING"] == "false",
   "] == "true",
    "binance_use_testnet_true": flags["BINANCE_USE_TESTNET"] == "true",
    "live_trading_flag_false": flags["BINANCE_ENABLE_LIVE_TRADING"] == "false",
    "live_trading_allowed_false": flags["LIVE_TRADING_ALLOWED"] == "false",
    "kill_switch_enabled": kill_switch_enabled,
    "simulated_payload_created": isinstance(simulated_order_payload, dict),
    "payload_contains_forbidden_keys_false": payload_contains_forbidden_keys is False,
    "micro_notional_within_order_limit": micro_notional_within_order_limit,
    "order_limit_within_position_limit": order_limit_within_position_limit,
    "daily_loss_positive": daily_loss_positive,
    "risk_payload_safe": risk_payload_safe,
    "signed_endpoint_called_false": True,
    "account_endpoint_called_false": True,
    "order_endpoint_called_false": True,
    "network_call_made_false": True,
    "production_credentials_used_false": True,
    "exchange_order_submission_false": True,
    "approved_for_micro_live_execution_false": True,
    "approved_for_real_live_trading_false": True,
}

blockers = [k for k, v in test_checks.items() if v is not True]
test_passed = not blockers

decision = (
    "PHASE_23_ORDER_CONSTRUCTION_SAFETY_TEST_COMPLETE_READY_FOR_NO_ORDER_SUBMISSION_VERIFICATION_NOT_APPROVED_FOR_EXECUTION"
    if test_passed else
    "PHASE_23_ORDER_CONSTRUCTION_SAFETY_TEST_FAILED_REVIEW_REQUIRED_NOT_APPROVED_FOR_EXECUTION"
)

record = {
    "phase": "phase_23_11_order_construction_safety_test",
    "generated_at_unix": int(time.time()),
    "git_head": head,
    "git_branch": branch,
    "git_remote_origin": remote,
    "git_working_tree_clean_before_outputs": git_clean,
    "requested_transition": "on_hold_to_micro_trading_validation",
    "current_transition_status": "order_construction_safety_test_only_not_approved_for_execution",
    "order_construction_safety_test_passed": test_passed,
    "test_checks": test_checks,
    "blockers": blockers,
    "risk_findings": risk_findings,
    "safe_flags": flags,
    "safe_flags_active": safe_flags_active,
    "kill_switch_enabled": kill_switch_enabled,
    "simulated_order_payload": simulated_order_payload,
    "simulated_order_notional_usdt": micro_trade_notional,
    "risk_limits": {
        "micro_trade_notional_usdt": micro_trade_notional,
        "max_order_notional_usdt": max_order_notional,
        "max_daily_loss_usdt": max_daily_loss,
        "max_position_size_usdt": max_position_size,
        "micro_notional_within_order_limit": micro_notional_within_order_limit,
        "order_limit_within_position_limit": order_limit_within_position_limit,
        "daily_loss_positive": daily_loss_positive,
    },
    "simulated_payload_only": True,
    "signed_endpoint_called": False,
    "account_endpoint_called": False,
    "order_endpoint_called": False,
    "network_call_made": False,
    "production_credentials_used": False,
    "micro_live_deployment_started": False,
    "monitoring_started": False,
    "run_dry_run_now": False,
    "run_backtest_now": False,
    "execution_allowed": False,
    "approved_for_execution": False,
    "approved_for_paper_shadow": False,
    "approved_for_live": False,
    "paper_shadow_started": False,
    "approved_for_paper_shadow_start": False,
    "exchange_order_submission": False,
    "approved_for_micro_live_execution": False,
    "approved_for_real_live_trading": False,
    "production_api_key_usage": False,
    "real_capital_usage": False,
    "decision": decision,
    "next_phase": "Phase 23.12 — No-Order Submission Verification",
}

write(OUT, record)
write(RUNTIME_OUT, record)
write(TEST_FILE, record)

print(f"Report written to: {OUT}")
print(f"Runtime state written to: {RUNTIME_OUT}")
print(f"Test file written to: {TEST_FILE}")
print(f"order_construction_safety_test_passed={test_passed}")
print(f"safe_flags_active={safe_flags_active}")
print(f"kill_switch_enabled={kill_switch_enabled}")
print(f"symbol={symbol}")
print(f"simulated_order_notional_usdt={micro_trade_notional}")
print(f"micro_notional_within_order_limit={micro_notional_within_order_limit}")
print(f"order_limit_within_position_limit={order_limit_within_position_limit}")
print("simulated_payload_only=True")
print("signed_endpoint_called=False")
print("account_endpoint_called=False")
print("order_endpoint_called=False")
print("network_call_made=False")
print("production_credentials_used=False")
print("current_transition_status=order_construction_safety_test_only_not_approved_for_execution")
print("micro_live_deployment_started=False")
print("execution_allowed=False")
print("exchange_order_submission=False")
print("approved_for_micro_live_execution=False")
print("approved_for_real_live_trading=False")
print("production_api_key_usage=False")
print("real_capital_usage=False")
print(f"decision={decision}")
if risk_findings:
    print("risk_findings=" + ",".join(risk_findings))
if blockers:
    print("blockers=" + ",".join(blockers))
