import json, os, subprocess, time
from pathlib import Path

OUT = Path("data/processed/phase23_reopening_deployment_environment_audit.json")
RUNTIME_OUT = Path("runtime/phase23_reopening_deployment_environment_audit_state.json")
REOPEN_DIR = Path("data/processed/phase23_reopening")
AUDIT_FILE = REOPEN_DIR / "reopening_deployment_environment_audit.json"

FINAL_END_STATE = Path("data/processed/phase22_project_final_end_state_record.json")

REQUIRED_ENV_KEYS = [
    "BINANCE_TESTNET",
    "BINANCE_USE_TESTNET",
    "BINANCE_ENABLE_LIVE_TRADING",
    "LIVE_TRADING_ALLOWED",
]

PRODUCTION_ENV_KEYS = [
    "BINANCE_API_KEY",
    "BINANCE_API_SECRET",
    "BINANCE_BASE_URL",
    "BINANCE_TESTNET_BASE_URL",
    "TRADING_SYMBOLS",
    "MAX_POSITION_SIZE_USDT",
    "MAX_DAILY_LOSS_USDT",
    "MAX_ORDER_NOTIONAL_USDT",
    "MICRO_TRADE_NOTIONAL_USDT",
    "KILL_SWITCH_ENABLED",
]

def run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True)

def git_value(cmd):
    result = run(cmd)
    return result.stdout.strip() if result.returncode == 0 else None

def load_json(path):
    try:
        return json.loads(path.read_text()) if path.exists() else {}
    except Exception:
        return {}

def mask_env_value(value):
    if value in (None, ""):
        return None
    if len(value) <= 6:
        return "***"
    return value[:3] + "***" + value[-3:]

def env_entry(key):
    value = os.getenv(key)
    return {
        "key": key,
        "present": value not in (None, ""),
        "masked_value": mask_env_value(value),
    }

def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2))

head = git_value(["git", "rev-parse", "HEAD"])
branch = git_value(["git", "branch", "--show-current"])
remote = git_value(["git", "remote", "get-url", "origin"])
status_short = git_value(["git", "status", "--short"]) or ""
git_clean = status_short == ""

flags = {
    "BINANCE_TESTNET": os.getenv("BINANCE_TESTNET", ""),
    "BINANCE_USE_TESTNET": os.getenv("BINANCE_USE_TESTNET", ""),
    "BINANCE_ENABLE_LIVE_TRADING": os.getenv("BINANCE_ENABLE_LIVE_TRADING", ""),
    "LIVE_TRADING_ALLOWED": os.getenv("LIVE_TRADING_ALLOWED", ""),
}

safe_flags_active = (
    flags["BINANCE_ENABLE_LIVE_TRADING"] == "false"
    and flags["LIVE_TRADING_ALLOWED"] == "false"
)

final_state = load_json(FINAL_END_STATE)
phase22_final_closed = (
    final_state.get("project_final_end_state_record_created") is True
    or "PHASE_22_PROJECT_FINAL_END_STATE_RECORD_CREATED" in str(final_state.get("decision", ""))
)

required_env_map = [env_entry(k) for k in REQUIRED_ENV_KEYS]
production_env_map = [env_entry(k) for k in PRODUCTION_ENV_KEYS]

required_env_present = all(x["present"] for x in required_env_map)

audit_checks = {
    "git_head_present": bool(head),
    "git_branch_present": bool(branch),
    "git_remote_origin_present": bool(remote),
    "git_working_tree_clean_before_outputs": git_clean,
    "phase22_final_end_state_present": FINAL_END_STATE.exists(),
    "phase22_final_closed_on_hold": phase22_final_closed,
    "safe_flags_active": safe_flags_active,
    "required_safety_env_keys_present": required_env_present,
    "live_trading_flag_false": flags["BINANCE_ENABLE_LIVE_TRADING"] == "false",
    "live_trading_allowed_false": flags["LIVE_TRADING_ALLOWED"] == "false",
}

blockers = [k for k, v in audit_checks.items() if v is not True]
audit_passed = not blockers

decision = (
    "PHASE_23_REOPENING_DEPLOYMENT_ENVIRONMENT_AUDIT_COMPLETE_MICRO_VALIDATION_NOT_APPROVED_FOR_EXECUTION"
    if audit_passed else
    "PHASE_23_REOPENING_DEPLOYMENT_ENVIRONMENT_AUDIT_FAILED_REVIEW_REQUIRED"
)

record = {
    "phase": "phase_23_1_reopening_deployment_environment_audit",
    "generated_at_unix": int(time.time()),
    "git_head": head,
    "git_branch": branch,
    "git_remote_origin": remote,
    "git_working_tree_clean_before_outputs": git_clean,
    "previous_project_status": final_state.get("project_status"),
    "previous_phase22_status": final_state.get("phase22_status"),
    "requested_transition": "on_hold_to_micro_trading_validation",
    "current_transition_status": "audit_only_not_approved_for_execution",
    "environment_audit_passed": audit_passed,
    "audit_checks": audit_checks,
    "blockers": blockers,
    "required_env_map": required_env_map,
    "production_env_map_masked": production_env_map,
    "safe_flags": flags,
    "safe_flags_active": safe_flags_active,
    "micro_trading_environment_validation_requested": True,
    "micro_trading_environment_validation_started": False,
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
    "next_phase": "Phase 23.2 — Micro-Trading Environment Validation Gate",
}

write(OUT, record)
write(RUNTIME_OUT, record)
write(AUDIT_FILE, record)

print(f"Report written to: {OUT}")
print(f"Runtime state written to: {RUNTIME_OUT}")
print(f"Audit file written to: {AUDIT_FILE}")
print(f"environment_audit_passed={audit_passed}")
print(f"safe_flags_active={safe_flags_active}")
print("requested_transition=on_hold_to_micro_trading_validation")
print("current_transition_status=audit_only_not_approved_for_execution")
print("micro_trading_environment_validation_requested=True")
print("micro_trading_environment_validation_started=False")
print("execution_allowed=False")
print("exchange_order_submission=False")
print("approved_for_micro_live_execution=False")
print("approved_for_real_live_trading=False")
print(f"decision={decision}")
if blockers:
    print("blockers=" + ",".join(blockers))
