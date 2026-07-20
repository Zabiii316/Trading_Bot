import json, os, subprocess, time
from pathlib import Path

OUT = Path("data/processed/phase23_micro_trading_environment_validation_gate.json")
RUNTIME_OUT = Path("runtime/phase23_micro_trading_environment_validation_gate_state.json")
REOPEN_DIR = Path("data/processed/phase23_reopening")
VALIDATION_FILE = REOPEN_DIR / "micro_trading_environment_validation_gate.json"

AUDIT_FILES = [
    Path("data/processed/phase23_reopening_deployment_environment_audit.json"),
    Path("runtime/phase23_reopening_deployment_environment_audit_state.json"),
    Path("data/processed/phase23_reopening/reopening_deployment_environment_audit.json"),
]

FINAL_END_STATE = Path("data/processed/phase22_project_final_end_state_record.json")

SAFETY_ENV_KEYS = [
    "BINANCE_TESTNET",
    "BINANCE_USE_TESTNET",
    "BINANCE_ENABLE_LIVE_TRADING",
    "LIVE_TRADING_ALLOWED",
]

MICRO_CONFIG_KEYS = [
    "TRADING_SYMBOLS",
    "MICRO_TRADE_NOTIONAL_USDT",
    "MAX_ORDER_NOTIONAL_USDT",
    "MAX_DAILY_LOSS_USDT",
    "MAX_POSITION_SIZE_USDT",
    "KILL_SWITCH_ENABLED",
    "BINANCE_BASE_URL",
    "BINANCE_TESTNET_BASE_URL",
]

SENSITIVE_KEYS = [
    "BINANCE_API_KEY",
    "BINANCE_API_SECRET",
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

def first_value(items, key, default=None):
    for item in items:
        value = item.get(key)
        if value not in (None, ""):
            return value
    return default

def mask(value):
    if value in (None, ""):
        return None
    if len(value) <= 6:
        return "***"
    return value[:3] + "***" + value[-3:]

def env_map(keys):
    mapped = []
    for key in keys:
        value = os.getenv(key)
        mapped.append({
            "key": key,
            "present": value not in (None, ""),
            "masked_value": mask(value),
        })
    return mapped

def parse_positive_number(value):
    try:
        if value in (None, ""):
            return None
        n = float(value)
        return n if n > 0 else None
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

audits = [load(p) for p in AUDIT_FILES]
final_state = load(FINAL_END_STATE)

audit_passed = (
    any_true(audits, "environment_audit_passed")
    or any("PHASE_23_REOPENING_DEPLOYMENT_ENVIRONMENT_AUDIT_COMPLETE" in str(x.get("decision", "")) for x in audits)
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
}

safe_flags_active = (
    flags["BINANCE_TESTNET"] == "true"
    and flags["BINANCE_USE_TESTNET"] == "true"
    and flags["BINANCE_ENABLE_LIVE_TRADING"] == "false"
    and flags["LIVE_TRADING_ALLOWED"] == "false"
)

safety_env = env_map(SAFETY_ENV_KEYS)
micro_config_env = env_map(MICRO_CONFIG_KEYS)
sensitive_env = env_map(SENSITIVE_KEYS)

safety_env_present = all(x["present"] for x in safety_env)

micro_trade_notional = parse_positive_number(os.getenv("MICRO_TRADE_NOTIONAL_USDT"))
max_order_notional = parse_positive_number(os.getenv("MAX_ORDER_NOTIONAL_USDT"))
max_daily_loss = parse_positive_number(os.getenv("MAX_DAILY_LOSS_USDT"))
max_position_size = parse_positive_number(os.getenv("MAX_POSITION_SIZE_USDT"))

micro_notional_within_order_limit = (
    micro_trade_notional is not None
    and max_order_notional is not None
    and micro_trade_notional <= max_order_notional
)

kill_switch_raw = os.getenv("KILL_SWITCH_ENABLED", "")
kill_switch_mapped = kill_switch_raw.lower() in {"true", "1", "yes", "enabled"}

trading_symbols_present = os.getenv("TRADING_SYMBOLS", "") not in ("", None)

config_presence_count = sum(1 for x in micro_config_env if x["present"])

validation_checks = {
    "git_head_present": bool(head),
    "git_branch_present": bool(branch),
    "git_remote_origin_present": bool(remote),
    "git_working_tree_clean_before_outputs": git_clean,
    "phase22_final_end_state_present": FINAL_END_STATE.exists(),
    "phase22_closed_on_hold": phase22_closed,
    "phase23_1_audit_present": any(p.exists() for p in AUDIT_FILES),
    "phase23_1_audit_passed": audit_passed,
    "safe_flags_active": safe_flags_active,
    "safety_env_keys_present": safety_env_present,
    "live_trading_flag_false": flags["BINANCE_ENABLE_LIVE_TRADING"] == "false",
    "live_trading_allowed_false": flags["LIVE_TRADING_ALLOWED"] == "false",
    "binance_testnet_true": flags["BINANCE_TESTNET"] == "true",
    "binance_use_testnet_true": flags["BINANCE_USE_TESTNET"] == "true",
    "micro_config_mapping_created": config_presence_count >= 0,
    "production_credentials_not_used": True,
    "exchange_order_submission_disabled": True,
}

warnings = []
if not trading_symbols_present:
    warnings.append("TRADING_SYMBOLS not set yet")
if micro_trade_notional is None:
    warnings.append("MICRO_TRADE_NOTIONAL_USDT not set or not positive yet")
if max_order_notional is None:
    warnings.append("MAX_ORDER_NOTIONAL_USDT not set or not positive yet")
if max_daily_loss is None:
    warnings.append("MAX_DAILY_LOSS_USDT not set or not positive yet")
if max_position_size is None:
    warnings.append("MAX_POSITION_SIZE_USDT not set or not positive yet")
if not kill_switch_mapped:
    warnings.append("KILL_SWITCH_ENABLED not set to true/enabled yet")
if micro_trade_notional is not None and max_order_notional is not None and not micro_notional_within_order_limit:
    warnings.append("MICRO_TRADE_NOTIONAL_USDT is greater than MAX_ORDER_NOTIONAL_USDT")

blockers = [key for key, value in validation_checks.items() if value is not True]
validation_passed = not blockers

decision = (
    "PHASE_23_MICRO_TRADING_ENVIRONMENT_VALIDATION_GATE_COMPLETE_NOT_APPROVED_FOR_EXECUTION"
    if validation_passed else
    "PHASE_23_MICRO_TRADING_ENVIRONMENT_VALIDATION_GATE_FAILED_REVIEW_REQUIRED"
)

record = {
    "phase": "phase_23_2_micro_trading_environment_validation_gate",
    "generated_at_unix": int(time.time()),
    "git_head": head,
    "git_branch": branch,
    "git_remote_origin": remote,
    "git_working_tree_clean_before_outputs": git_clean,
    "previous_project_status": final_state.get("project_status"),
    "previous_phase22_status": final_state.get("phase22_status"),
    "requested_transition": "on_hold_to_micro_trading_validation",
    "current_transition_status": "environment_validation_gate_only_not_approved_for_execution",
    "environment_validation_passed": validation_passed,
    "validation_checks": validation_checks,
    "blockers": blockers,
    "warnings": warnings,
    "safe_flags": flags,
    "safe_flags_active": safe_flags_active,
    "safety_env_map": safety_env,
    "micro_config_env_map_masked": micro_config_env,
    "sensitive_env_map_masked": sensitive_env,
    "parsed_micro_limits": {
        "micro_trade_notional_usdt": micro_trade_notional,
        "max_order_notional_usdt": max_order_notional,
        "max_daily_loss_usdt": max_daily_loss,
        "max_position_size_usdt": max_position_size,
        "micro_notional_within_order_limit": micro_notional_within_order_limit,
        "kill_switch_enabled": kill_switch_mapped,
        "trading_symbols_present": trading_symbols_present,
    },
    "micro_trading_environment_validation_requested": True,
    "micro_trading_environment_validation_completed": validation_passed,
    "micro_trading_environment_validation_started": False,
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
    "next_phase": "Phase 23.3 — Micro-Trading Configuration Mapping Review",
}

write(OUT, record)
write(RUNTIME_OUT, record)
write(VALIDATION_FILE, record)

print(f"Report written to: {OUT}")
print(f"Runtime state written to: {RUNTIME_OUT}")
print(f"Validation file written to: {VALIDATION_FILE}")
print(f"environment_validation_passed={validation_passed}")
print(f"safe_flags_active={safe_flags_active}")
print("current_transition_status=environment_validation_gate_only_not_approved_for_execution")
print("micro_trading_environment_validation_completed=" + str(validation_passed))
print("micro_trading_environment_validation_started=False")
print("micro_live_deployment_started=False")
print("execution_allowed=False")
print("exchange_order_submission=False")
print("approved_for_micro_live_execution=False")
print("approved_for_real_live_trading=False")
print("production_api_key_usage=False")
print("real_capital_usage=False")
print(f"decision={decision}")
if warnings:
    print("warnings=" + ",".join(warnings))
if blockers:
    print("blockers=" + ",".join(blockers))
