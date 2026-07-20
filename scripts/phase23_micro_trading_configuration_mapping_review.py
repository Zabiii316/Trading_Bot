import json, os, subprocess, time
from pathlib import Path

OUT = Path("data/processed/phase23_micro_trading_configuration_mapping_review.json")
RUNTIME_OUT = Path("runtime/phase23_micro_trading_configuration_mapping_review_state.json")
REOPEN_DIR = Path("data/processed/phase23_reopening")
REVIEW_FILE = REOPEN_DIR / "micro_trading_configuration_mapping_review.json"

VALIDATION_FILES = [
    Path("data/processed/phase23_micro_trading_environment_validation_gate.json"),
    Path("runtime/phase23_micro_trading_environment_validation_gate_state.json"),
    Path("data/processed/phase23_reopening/micro_trading_environment_validation_gate.json"),
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

def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2))

head = git_value(["git", "rev-parse", "HEAD"])
branch = git_value(["git", "branch", "--show-current"])
remote = git_value(["git", "remote", "get-url", "origin"])
status_short = git_value(["git", "status", "--short"]) or ""
git_clean = status_short == ""

validations = [load(p) for p in VALIDATION_FILES]
final_state = load(FINAL_END_STATE)

validation_passed = (
    any_true(validations, "environment_validation_passed")
    or any("PHASE_23_MICRO_TRADING_ENVIRONMENT_VALIDATION_GATE_COMPLETE" in str(x.get("decision", "")) for x in validations)
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

latest_validation = validations[0] if validations else {}
parsed_limits = first_value(validations, "parsed_micro_limits", {}) or {}
warnings = first_value(validations, "warnings", []) or []

micro_config_env_map = first_value(validations, "micro_config_env_map_masked", []) or []
safety_env_map = first_value(validations, "safety_env_map", []) or []
sensitive_env_map = first_value(validations, "sensitive_env_map_masked", []) or []

micro_config_mapping_present = isinstance(micro_config_env_map, list)
safety_mapping_present = isinstance(safety_env_map, list) and len(safety_env_map) > 0
sensitive_mapping_present = isinstance(sensitive_env_map, list)

required_safety_keys = {"BINANCE_TESTNET", "BINANCE_USE_TESTNET", "BINANCE_ENABLE_LIVE_TRADING", "LIVE_TRADING_ALLOWED"}
mapped_safety_keys = {x.get("key") for x in safety_env_map if isinstance(x, dict)}
required_safety_keys_mapped = required_safety_keys.issubset(mapped_safety_keys)

micro_config_review_notes = []
if warnings:
    micro_config_review_notes.append("Micro configuration warnings exist and must be resolved before any approval gate.")
else:
    micro_config_review_notes.append("No micro configuration warnings were reported by Phase 23.2.")

review_checks = {
    "git_head_present": bool(head),
    "git_branch_present": bool(branch),
    "git_remote_origin_present": bool(remote),
    "git_working_tree_clean_before_outputs": git_clean,
    "phase22_final_end_state_present": FINAL_END_STATE.exists(),
    "phase22_closed_on_hold": phase22_closed,
    "phase23_2_validation_present": any(p.exists() for p in VALIDATION_FILES),
    "phase23_2_validation_passed": validation_passed,
    "safe_flags_active": safe_flags_active,
    "live_trading_flag_false": flags["BINANCE_ENABLE_LIVE_TRADING"] == "false",
    "live_trading_allowed_false": flags["LIVE_TRADING_ALLOWED"] == "false",
    "safety_mapping_present": safety_mapping_present,
    "required_safety_keys_mapped": required_safety_keys_mapped,
    "micro_config_mapping_present": micro_config_mapping_present,
    "sensitive_mapping_present_without_key_usage": sensitive_mapping_present,
    "production_api_key_usage_false": latest_validation.get("production_api_key_usage") is False,
    "exchange_order_submission_false": latest_validation.get("exchange_order_submission") is False,
    "approved_for_micro_live_execution_false": latest_validation.get("approved_for_micro_live_execution") is False,
    "approved_for_real_live_trading_false": latest_validation.get("approved_for_real_live_trading") is False,
}

blockers = [key for key, value in review_checks.items() if value is not True]
review_passed = not blockers

decision = (
    "PHASE_23_MICRO_TRADING_CONFIGURATION_MAPPING_REVIEW_COMPLETE_NOT_APPROVED_FOR_EXECUTION"
    if review_passed else
    "PHASE_23_MICRO_TRADING_CONFIGURATION_MAPPING_REVIEW_FAILED_REVIEW_REQUIRED"
)

record = {
    "phase": "phase_23_3_micro_trading_configuration_mapping_review",
    "generated_at_unix": int(time.time()),
    "git_head": head,
    "git_branch": branch,
    "git_remote_origin": remote,
    "git_working_tree_clean_before_outputs": git_clean,
    "previous_project_status": final_state.get("project_status"),
    "previous_phase22_status": final_state.get("phase22_status"),
    "requested_transition": "on_hold_to_micro_trading_validation",
    "current_transition_status": "configuration_mapping_review_only_not_approved_for_execution",
    "configuration_mapping_review_passed": review_passed,
    "review_checks": review_checks,
    "blockers": blockers,
    "warnings_from_phase23_2": warnings,
    "review_notes": micro_config_review_notes,
    "safe_flags": flags,
    "safe_flags_active": safe_flags_active,
    "safety_env_map": safety_env_map,
    "micro_config_env_map_masked": micro_config_env_map,
    "sensitive_env_map_masked": sensitive_env_map,
    "parsed_micro_limits_from_phase23_2": parsed_limits,
    "micro_trading_environment_validation_completed": validation_passed,
    "micro_trading_configuration_review_completed": review_passed,
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
    "next_phase": "Phase 23.4 — Micro-Trading Risk Limit Configuration Gate",
}

write(OUT, record)
write(RUNTIME_OUT, record)
write(REVIEW_FILE, record)

print(f"Report written to: {OUT}")
print(f"Runtime state written to: {RUNTIME_OUT}")
print(f"Review file written to: {REVIEW_FILE}")
print(f"configuration_mapping_review_passed={review_passed}")
print(f"safe_flags_active={safe_flags_active}")
print("current_transition_status=configuration_mapping_review_only_not_approved_for_execution")
print("micro_trading_environment_validation_completed=" + str(validation_passed))
print("micro_trading_configuration_review_completed=" + str(review_passed))
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
    print("warnings_from_phase23_2=" + ",".join(warnings))
if blockers:
    print("blockers=" + ",".join(blockers))
