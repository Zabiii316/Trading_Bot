import json, os, subprocess, time
from pathlib import Path

OUT = Path("data/processed/phase23_no_order_submission_verification.json")
RUNTIME_OUT = Path("runtime/phase23_no_order_submission_verification_state.json")
VERIFY_FILE = Path("data/processed/phase23_reopening/no_order_submission_verification.json")

ORDER_TEST_FILES = [
    Path("data/processed/phase23_order_construction_safety_test.json"),
    Path("runtime/phase23_order_construction_safety_test_state.json"),
    Path("data/processed/phase23_reopening/order_construction_safety_test.json"),
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

order_records = [load(p) for p in ORDER_TEST_FILES]
final_state = load(FINAL_END_STATE)

order_test_passed = (
    any_true(order_records, "order_construction_safety_test_passed")
    or any("PHASE_23_ORDER_CONSTRUCTION_SAFETY_TEST_COMPLETE" in str(x.get("decision", "")) for x in order_records)
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

simulated_payload_only = any_true(order_records, "simulated_payload_only")
signed_endpoint_called_false = any_false(order_records, "signed_endpoint_called")
account_endpoint_called_false = any_false(order_records, "account_endpoint_called")
order_endpoint_called_false = any_false(order_records, "order_endpoint_called")
network_call_made_false = any_false(order_records, "network_call_made")
production_credentials_used_false = any_false(order_records, "production_credentials_used")
exchange_order_submission_false = any_false(order_records, "exchange_order_submission")
execution_allowed_false = any_false(order_records, "execution_allowed")
micro_live_approved_false = any_false(order_records, "approved_for_micro_live_execution")
real_live_approved_false = any_false(order_records, "approved_for_real_live_trading")
real_capital_usage_false = any_false(order_records, "real_capital_usage")

simulated_order_payload = first_value(order_records, "simulated_order_payload", {}) or {}
payload_has_symbol = bool(simulated_order_payload.get("symbol"))
payload_has_notional = bool(simulated_order_payload.get("quoteOrderQty"))
payload_client_id_simulated = "SIMULATED_ONLY" in str(simulated_order_payload.get("clientOrderId", ""))

verification_checks = {
    "git_head_present": bool(head),
    "git_branch_present": bool(branch),
    "git_remote_origin_present": bool(remote),
    "git_working_tree_clean_before_outputs": git_clean,
    "phase22_final_end_state_present": FINAL_END_STATE.exists(),
    "phase22_closed_on_hold": phase22_closed,
    "phase23_11_order_test_present": any(p.exists() for p in ORDER_TEST_FILES),
    "phase23_11_order_test_passed": order_test_passed,
    "safe_flags_active": safe_flags_active,
    "binance_testnet_true": flags["BINANCE_TESTNET"] == "true",
    "binance_use_testnet_true": flags["BINANCE_USE_TESTNET"] == "true",
    "live_trading_flag_false": flags["BINANCE_ENABLE_LIVE_TRADING"] == "false",
    "live_trading_allowed_false": flags["LIVE_TRADING_ALLOWED"] == "false",
    "kill_switch_enabled": kill_switch_enabled,
    "simulated_payload_only": simulated_payload_only,
    "payload_has_symbol": payload_has_symbol,
    "payload_has_notional": payload_has_notional,
    "payload_client_id_simulated": payload_client_id_simulated,
    "signed_endpoint_called_false": signed_endpoint_called_false,
    "account_endpoint_called_false": account_endpoint_called_false,
    "order_endpoint_called_false": order_endpoint_called_false,
    "network_call_made_false": network_call_made_false,
    "production_credentials_used_false": production_credentials_used_false,
    "exchange_order_submission_false": exchange_order_submission_false,
    "execution_allowed_false": execution_allowed_false,
    "approved_for_micro_live_execution_false": micro_live_approved_false,
    "approved_for_real_live_trading_false": real_live_approved_false,
    "real_capital_usage_false": real_capital_usage_false,
}

blockers = [k for k, v in verification_checks.items() if v is not True]
passed = not blockers

decision = (
    "PHASE_23_NO_ORDER_SUBMISSION_VERIFICATION_COMPLETE_READY_FOR_PAPER_SHADOW_RESTART_PLAN_NOT_APPROVED_FOR_EXECUTION"
    if passed else
    "PHASE_23_NO_ORDER_SUBMISSION_VERIFICATION_FAILED_REVIEW_REQUIRED_NOT_APPROVED_FOR_EXECUTION"
)

record = {
    "phase": "phase_23_12_no_order_submission_verification",
    "generated_at_unix": int(time.time()),
    "git_head": head,
    "git_branch": branch,
    "git_remote_origin": remote,
    "git_working_tree_clean_before_outputs": git_clean,
    "current_transition_status": "no_order_submission_verification_only_not_approved_for_execution",
    "no_order_submission_verification_passed": passed,
    "verification_checks": verification_checks,
    "blockers": blockers,
    "safe_flags": flags,
    "safe_flags_active": safe_flags_active,
    "kill_switch_enabled": kill_switch_enabled,
    "verified_source_phase": "phase_23_11_order_construction_safety_test",
    "simulated_order_payload_reviewed": simulated_order_payload,
    "no_order_submission_verified": passed,
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
    "next_phase": "Phase 23.13 — Paper Shadow Restart Plan"
}

write(OUT, record)
write(RUNTIME_OUT, record)
write(VERIFY_FILE, record)

print(f"Report written to: {OUT}")
print(f"Runtime state written to: {RUNTIME_OUT}")
print(f"Verification file written to: {VERIFY_FILE}")
print(f"no_order_submission_verification_passed={passed}")
print(f"safe_flags_active={safe_flags_active}")
print(f"kill_switch_enabled={kill_switch_enabled}")
print(f"simulated_payload_only={simulated_payload_only}")
print("signed_endpoint_called=False")
print("account_endpoint_called=False")
print("order_endpoint_called=False")
print("network_call_made=False")
print("production_credentials_used=False")
print("no_order_submission_verified=" + str(passed))
print("execution_allowed=False")
print("exchange_order_submission=False")
print("approved_for_micro_live_execution=False")
print("approved_for_real_live_trading=False")
print("production_api_key_usage=False")
print("real_capital_usage=False")
print(f"decision={decision}")
if blockers:
    print("blockers=" + ",".join(blockers))
