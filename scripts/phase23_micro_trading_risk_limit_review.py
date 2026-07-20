import json, os, subprocess, time
from pathlib import Path

OUT = Path("data/processed/phase23_micro_trading_risk_limit_review.json")
RUNTIME_OUT = Path("runtime/phase23_micro_trading_risk_limit_review_state.json")
REOPEN_DIR = Path("data/processed/phase23_reopening")
REVIEW_FILE = REOPEN_DIR / "micro_trading_risk_limit_review.json"

RISK_GATE_FILES = [
    Path("data/processed/phase23_micro_trading_risk_limit_configuration_gate.json"),
    Path("runtime/phase23_micro_trading_risk_limit_configuration_gate_state.json"),
    Path("data/processed/phase23_reopening/micro_trading_risk_limit_configuration_gate.json"),
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

def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2))

head = git_value(["git", "rev-parse", "HEAD"])
branch = git_value(["git", "branch", "--show-current"])
remote = git_value(["git", "remote", "get-url", "origin"])
status_short = git_value(["git", "status", "--short"]) or ""
git_clean = status_short == ""

gates = [load(p) for p in RISK_GATE_FILES]
final_state = load(FINAL_END_STATE)

risk_gate_created = (
    any_true(gates, "risk_limit_gate_created")
    or any("PHASE_23_MICRO_TRADING_RISK_LIMIT_CONFIGURATION_GATE" in str(x.get("decision", "")) for x in gates)
)

phase22_closed = (
    final_state.get("project_final_end_state_record_created") is True
    or "PHASE_22_PROJECT_FINAL_END_STATE_RECORD_CREATED" in str(final_state.get("decision", ""))
)

latest_gate = gates[0] if gates else {}
gate_risk_warnings = first_value(gates, "risk_limit_warnings", []) or []
gate_parsed_limits = first_value(gates, "parsed_risk_limits", {}) or {}

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

trading_symbols = os.getenv("TRADING_SYMBOLS") or gate_parsed_limits.get("trading_symbols")
micro_trade_notional = parse_positive_number(os.getenv("MICRO_TRADE_NOTIONAL_USDT")) or gate_parsed_limits.get("micro_trade_notional_usdt")
max_order_notional = parse_positive_number(os.getenv("MAX_ORDER_NOTIONAL_USDT")) or gate_parsed_limits.get("max_order_notional_usdt")
max_daily_loss = parse_positive_number(os.getenv("MAX_DAILY_LOSS_USDT")) or gate_parsed_limits.get("max_daily_loss_usdt")
max_position_size = parse_positive_number(os.getenv("MAX_POSITION_SIZE_USDT")) or gate_parsed_limits.get("max_position_size_usdt")

kill_switch_raw = os.getenv("KILL_SWITCH_ENABLED", "")
kill_switch_enabled = (
    kill_switch_raw.lower() in {"true", "1", "yes", "enabled"}
    or gate_parsed_limits.get("kill_switch_enabled") is True
)

risk_review_findings = []

if not trading_symbols:
    risk_review_findings.append("TRADING_SYMBOLS is not configured")
if micro_trade_notional is None:
    risk_review_findings.append("MICRO_TRADE_NOTIONAL_USDT is not configured as a positive value")
if max_order_notional is None:
    risk_review_findings.append("MAX_ORDER_NOTIONAL_USDT is not configured as a positive value")
if max_daily_loss is None:
    risk_review_findings.append("MAX_DAILY_LOSS_USDT is not configured as a positive value")
if max_position_size is None:
    risk_review_findings.append("MAX_POSITION_SIZE_USDT is not configured as a positive value")
if not kill_switch_enabled:
    risk_review_findings.append("KILL_SWITCH_ENABLED is not true/enabled")

micro_notional_within_order_limit = (
    micro_trade_notional is not None
    and max_order_notional is not None
    and float(micro_trade_notional) <= float(max_order_notional)
)

order_limit_within_position_limit = (
    max_order_notional is not None
    and max_position_size is not None
    and float(max_order_notional) <= float(max_position_size)
)

daily_loss_positive = max_daily_loss is not None and float(max_daily_loss) > 0

if micro_trade_notional is not None and max_order_notional is not None and not micro_notional_within_order_limit:
    risk_review_findings.append("MICRO_TRADE_NOTIONAL_USDT exceeds MAX_ORDER_NOTIONAL_USDT")

if max_order_notional is not None and max_position_size is not None and not order_limit_within_position_limit:
    risk_review_findings.append("MAX_ORDER_NOTIONAL_USDT exceeds MAX_POSITION_SIZE_USDT")

risk_limits_reviewed = True
risk_limits_acceptable_for_next_gate = len(risk_review_findings) == 0

review_checks = {
    "git_head_present": bool(head),
    "git_branch_present": bool(branch),
    "git_remote_origin_present": bool(remote),
    "git_working_tree_clean_before_outputs": git_clean,
    "phase22_final_end_state_present": FINAL_END_STATE.exists(),
    "phase22_closed_on_hold": phase22_closed,
    "phase23_4_risk_gate_present": any(p.exists() for p in RISK_GATE_FILES),
    "phase23_4_risk_gate_created": risk_gate_created,
    "safe_flags_active": safe_flags_active,
    "live_trading_flag_false": flags["BINANCE_ENABLE_LIVE_TRADING"] == "false",
    "live_trading_allowed_false": flags["LIVE_TRADING_ALLOWED"] == "false",
    "exchange_order_submission_false": latest_gate.get("exchange_order_submission") is False,
    "production_api_key_usage_false": latest_gate.get("production_api_key_usage") is False,
    "approved_for_micro_live_execution_false": latest_gate.get("approved_for_micro_live_execution") is False,
    "approved_for_real_live_trading_false": latest_gate.get("approved_for_real_live_trading") is False,
}

blockers = [key for key, value in review_checks.items() if value is not True]
review_passed = not blockers

if review_passed and risk_limits_acceptable_for_next_gate:
    decision = "PHASE_23_MICRO_TRADING_RISK_LIMIT_REVIEW_COMPLETE_READY_FOR_KILL_SWITCH_REVALIDATION_NOT_APPROVED_FOR_EXECUTION"
else:
    decision = "PHASE_23_MICRO_TRADING_RISK_LIMIT_REVIEW_COMPLETE_RISK_VALUES_REQUIRE_REMEDIATION_NOT_APPROVED_FOR_EXECUTION"

record = {
    "phase": "phase_23_5_micro_trading_risk_limit_review",
    "generated_at_unix": int(time.time()),
    "git_head": head,
    "git_branch": branch,
    "git_remote_origin": remote,
    "git_working_tree_clean_before_outputs": git_clean,
    "requested_transition": "on_hold_to_micro_trading_validation",
    "current_transition_status": "risk_limit_review_only_not_approved_for_execution",
    "risk_limit_review_passed": review_passed,
    "risk_limits_reviewed": risk_limits_reviewed,
    "risk_limits_acceptable_for_next_gate": risk_limits_acceptable_for_next_gate,
    "review_checks": review_checks,
    "blockers": blockers,
    "risk_review_findings": risk_review_findings,
    "risk_gate_warnings_from_phase23_4": gate_risk_warnings,
    "reviewed_risk_limits": {
        "trading_symbols": trading_symbols,
        "micro_trade_notional_usdt": micro_trade_notional,
        "max_order_notional_usdt": max_order_notional,
        "max_daily_loss_usdt": max_daily_loss,
        "max_position_size_usdt": max_position_size,
        "kill_switch_enabled": kill_switch_enabled,
        "micro_notional_within_order_limit": micro_notional_within_order_limit,
        "order_limit_within_position_limit": order_limit_within_position_limit,
        "daily_loss_positive": daily_loss_positive,
    },
    "safe_flags": flags,
    "safe_flags_active": safe_flags_active,
    "micro_trading_risk_limit_review_completed": review_passed,
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
    "next_phase": "Phase 23.6 — Kill Switch Revalidation",
}

write(OUT, record)
write(RUNTIME_OUT, record)
write(REVIEW_FILE, record)

print(f"Report written to: {OUT}")
print(f"Runtime state written to: {RUNTIME_OUT}")
print(f"Review file written to: {REVIEW_FILE}")
print(f"risk_limit_review_passed={review_passed}")
print(f"risk_limits_reviewed={risk_limits_reviewed}")
print(f"risk_limits_acceptable_for_next_gate={risk_limits_acceptable_for_next_gate}")
print(f"safe_flags_active={safe_flags_active}")
print("current_transition_status=risk_limit_review_only_not_approved_for_execution")
print("micro_live_deployment_started=False")
print("execution_allowed=False")
print("exchange_order_submission=False")
print("approved_for_micro_live_execution=False")
print("approved_for_real_live_trading=False")
print("production_api_key_usage=False")
print("real_capital_usage=False")
print(f"decision={decision}")
if risk_review_findings:
    print("risk_review_findings=" + ",".join(risk_review_findings))
if blockers:
    print("blockers=" + ",".join(blockers))
