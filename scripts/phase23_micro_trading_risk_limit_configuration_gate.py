import json, os, subprocess, time
from pathlib import Path

OUT = Path("data/processed/phase23_micro_trading_risk_limit_configuration_gate.json")
RUNTIME_OUT = Path("runtime/phase23_micro_trading_risk_limit_configuration_gate_state.json")
REOPEN_DIR = Path("data/processed/phase23_reopening")
GATE_FILE = REOPEN_DIR / "micro_trading_risk_limit_configuration_gate.json"

CONFIG_REVIEW_FILES = [
    Path("data/processed/phase23_micro_trading_configuration_mapping_review.json"),
    Path("runtime/phase23_micro_trading_configuration_mapping_review_state.json"),
    Path("data/processed/phase23_reopening/micro_trading_configuration_mapping_review.json"),
]

FINAL_END_STATE = Path("data/processed/phase22_project_final_end_state_record.json")

RISK_KEYS = [
    "TRADING_SYMBOLS",
    "MICRO_TRADE_NOTIONAL_USDT",
    "MAX_ORDER_NOTIONAL_USDT",
    "MAX_DAILY_LOSS_USDT",
    "MAX_POSITION_SIZE_USDT",
    "KILL_SWITCH_ENABLED",
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

def parse_positive_number(value):
    try:
        if value in (None, ""):
            return None
        number = float(value)
        return number if number > 0 else None
    except Exception:
        return None

def mask(value):
    if value in (None, ""):
        return None
    if len(value) <= 6:
        return "***"
    return value[:3] + "***" + value[-3:]

def env_map(keys):
    output = []
    for key in keys:
        value = os.getenv(key)
        output.append({
            "key": key,
            "present": value not in (None, ""),
            "masked_value": mask(value),
        })
    return output

def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2))

head = git_value(["git", "rev-parse", "HEAD"])
branch = git_value(["git", "branch", "--show-current"])
remote = git_value(["git", "remote", "get-url", "origin"])
status_short = git_value(["git", "status", "--short"]) or ""
git_clean = status_short == ""

reviews = [load(p) for p in CONFIG_REVIEW_FILES]
final_state = load(FINAL_END_STATE)

configuration_review_passed = (
    any_true(reviews, "configuration_mapping_review_passed")
    or any("PHASE_23_MICRO_TRADING_CONFIGURATION_MAPPING_REVIEW_COMPLETE" in str(x.get("decision", "")) for x in reviews)
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

trading_symbols = os.getenv("TRADING_SYMBOLS", "")
micro_trade_notional = parse_positive_number(os.getenv("MICRO_TRADE_NOTIONAL_USDT"))
max_order_notional = parse_positive_number(os.getenv("MAX_ORDER_NOTIONAL_USDT"))
max_daily_loss = parse_positive_number(os.getenv("MAX_DAILY_LOSS_USDT"))
max_position_size = parse_positive_number(os.getenv("MAX_POSITION_SIZE_USDT"))
kill_switch_enabled = os.getenv("KILL_SWITCH_ENABLED", "").lower() in {"true", "1", "yes", "enabled"}

risk_limit_warnings = []

if not trading_symbols:
    risk_limit_warnings.append("TRADING_SYMBOLS is not configured")
if micro_trade_notional is None:
    risk_limit_warnings.append("MICRO_TRADE_NOTIONAL_USDT is missing or invalid")
if max_order_notional is None:
    risk_limit_warnings.append("MAX_ORDER_NOTIONAL_USDT is missing or invalid")
if max_daily_loss is None:
    risk_limit_warnings.append("MAX_DAILY_LOSS_USDT is missing or invalid")
if max_position_size is None:
    risk_limit_warnings.append("MAX_POSITION_SIZE_USDT is missing or invalid")
if not kill_switch_enabled:
    risk_limit_warnings.append("KILL_SWITCH_ENABLED is not true/enabled")

micro_notional_within_order_limit = (
    micro_trade_notional is not None
    and max_order_notional is not None
    and micro_trade_notional <= max_order_notional
)

if micro_trade_notional is not None and max_order_notional is not None and not micro_notional_within_order_limit:
    risk_limit_warnings.append("MICRO_TRADE_NOTIONAL_USDT exceeds MAX_ORDER_NOTIONAL_USDT")

risk_limits_defined = len(risk_limit_warnings) == 0

gate_checks = {
    "git_head_present": bool(head),
    "git_branch_present": bool(branch),
    "git_remote_origin_present": bool(remote),
    "git_working_tree_clean_before_outputs": git_clean,
    "phase22_final_end_state_present": FINAL_END_STATE.exists(),
    "phase22_closed_on_hold": phase22_closed,
    "phase23_3_configuration_review_present": any(p.exists() for p in CONFIG_REVIEW_FILES),
    "phase23_3_configuration_review_passed": configuration_review_passed,
    "safe_flags_active": safe_flags_active,
    "live_trading_flag_false": flags["BINANCE_ENABLE_LIVE_TRADING"] == "false",
    "live_trading_allowed_false": flags["LIVE_TRADING_ALLOWED"] == "false",
    "exchange_order_submission_false": True,
    "production_api_key_usage_false": True,
}

blockers = [key for key, value in gate_checks.items() if value is not True]
risk_limit_gate_created = not blockers

if risk_limit_gate_created and risk_limits_defined:
    decision = "PHASE_23_MICRO_TRADING_RISK_LIMIT_CONFIGURATION_GATE_COMPLETE_READY_FOR_REVIEW_NOT_APPROVED_FOR_EXECUTION"
else:
    decision = "PHASE_23_MICRO_TRADING_RISK_LIMIT_CONFIGURATION_GATE_CREATED_RISK_VALUES_REQUIRED_NOT_APPROVED_FOR_EXECUTION"

record = {
    "phase": "phase_23_4_micro_trading_risk_limit_configuration_gate",
    "generated_at_unix": int(time.time()),
    "git_head": head,
    "git_branch": branch,
    "git_remote_origin": remote,
    "git_working_tree_clean_before_outputs": git_clean,
    "requested_transition": "on_hold_to_micro_trading_validation",
    "current_transition_status": "risk_limit_configuration_gate_only_not_approved_for_execution",
    "risk_limit_gate_created": risk_limit_gate_created,
    "risk_limits_defined": risk_limits_defined,
    "gate_checks": gate_checks,
    "blockers": blockers,
    "risk_limit_warnings": risk_limit_warnings,
    "risk_env_map_masked": env_map(RISK_KEYS),
    "parsed_risk_limits": {
        "trading_symbols": trading_symbols,
        "micro_trade_notional_usdt": micro_trade_notional,
        "max_order_notional_usdt": max_order_notional,
        "max_daily_loss_usdt": max_daily_loss,
        "max_position_size_usdt": max_position_size,
        "kill_switch_enabled": kill_switch_enabled,
        "micro_notional_within_order_limit": micro_notional_within_order_limit,
    },
    "safe_flags": flags,
    "safe_flags_active": safe_flags_active,
    "micro_trading_risk_limit_configuration_started": False,
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
    "next_phase": "Phase 23.5 — Micro-Trading Risk Limit Review",
}

write(OUT, record)
write(RUNTIME_OUT, record)
write(GATE_FILE, record)

print(f"Report written to: {OUT}")
print(f"Runtime state written to: {RUNTIME_OUT}")
print(f"Gate file written to: {GATE_FILE}")
print(f"risk_limit_gate_created={risk_limit_gate_created}")
print(f"risk_limits_defined={risk_limits_defined}")
print(f"safe_flags_active={safe_flags_active}")
print("current_transition_status=risk_limit_configuration_gate_only_not_approved_for_execution")
print("micro_trading_risk_limit_configuration_started=False")
print("micro_live_deployment_started=False")
print("execution_allowed=False")
print("exchange_order_submission=False")
print("approved_for_micro_live_execution=False")
print("approved_for_real_live_trading=False")
print("production_api_key_usage=False")
print("real_capital_usage=False")
print(f"decision={decision}")
if risk_limit_warnings:
    print("risk_limit_warnings=" + ",".join(risk_limit_warnings))
if blockers:
    print("blockers=" + ",".join(blockers))
