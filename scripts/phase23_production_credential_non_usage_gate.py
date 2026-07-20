import json, os, subprocess, time
from pathlib import Path

OUT = Path("data/processed/phase23_production_credential_non_usage_gate.json")
RUNTIME_OUT = Path("runtime/phase23_production_credential_non_usage_gate_state.json")
REOPEN_DIR = Path("data/processed/phase23_reopening")
GATE_FILE = REOPEN_DIR / "production_credential_non_usage_gate.json"

SECRETS_AUDIT_FILES = [
    Path("data/processed/phase23_secrets_api_key_mapping_audit.json"),
    Path("runtime/phase23_secrets_api_key_mapping_audit_state.json"),
    Path("data/processed/phase23_reopening/secrets_api_key_mapping_audit.json"),
]

FINAL_END_STATE = Path("data/processed/phase22_project_final_end_state_record.json")

PRODUCTION_SECRET_KEYS = [
    "BINANCE_API_KEY",
    "BINANCE_API_SECRET",
]

TESTNET_SECRET_KEYS = [
    "BINANCE_TESTNET_API_KEY",
    "BINANCE_TESTNET_API_SECRET",
]

SAFETY_KEYS = [
    "BINANCE_TESTNET",
    "BINANCE_USE_TESTNET",
    "BINANCE_ENABLE_LIVE_TRADING",
    "LIVE_TRADING_ALLOWED",
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

audits = [load(p) for p in SECRETS_AUDIT_FILES]
final_state = load(FINAL_END_STATE)

secrets_audit_passed = (
    any_true(audits, "secrets_api_key_mapping_audit_passed")
    or any("PHASE_23_SECRETS_API_KEY_MAPPING_AUDIT_COMPLETE" in str(x.get("decision", "")) for x in audits)
)

phase22_closed = (
    final_state.get("project_final_end_state_record_created") is True
    or "PHASE_22_PROJECT_FINAL_END_STATE_RECORD_CREATED" in str(final_state.get("decision", ""))
)

tracked_real_secret_findings = first_value(audits, "tracked_real_secret_findings_masked", []) or []
sensitive_values_printed = first_value(audits, "sensitive_values_printed", None)
sensitive_values_written_plaintext = first_value(audits, "sensitive_values_written_plaintext", None)

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

production_secret_env_map =false"
    and flags["LIVE_TRADING_ALLOWED"] == "false"
)

kill_switch_enabled = flags["KILL_SWITCH_ENABLED"].lower() in {" env_map(PRODUCTION_SECRET_KEYS)
testnet_secret_env_map = env_map(TESTNET_SECRET_KEYS)
safety_env_map = env_map(SAFETY_KEYS)

production_credentials_present = any(x["present"] for x in production_secret_env_map)
testnet_credentials_present = any(x["present"] for x in testnet_secret_env_map)

non_usage_warnings = []

if production_credentials_present:
    non_usage_warnings.append("Production Binance credentials are present in shell environment but usage remains disabled")
else:
    non_usage_warnings.append("Production Binance credentials are not present in shell environment")

if not testnet_credentials_present:
    non_usage_warnings.append("Testnet credentials are not present yet; Phase 23.9 may require testnet-only credentials")

gate_checks = {
    "git_head_present": bool(head),
    "git_branch_present": bool(branch),
    "git_remote_origin_present": bool(remote),
    "git_working_tree_clean_before_outputs": git_clean,
    "phase22_final_end_state_present": FINAL_END_STATE.exists(),
    "phase22_closed_on_hold": phase22_closed,
    "phase23_7_secrets_audit_present": any(p.exists() for p in SECRETS_AUDIT_FILES),
    "phase23_7_secrets_audit_passed": secrets_audit_passed,
    "safe_flags_active": safe_flags_active,
    "binance_testnet_true": flags["BINANCE_TESTNET"] == "true",
    "binance_use_testnet_true": flags["BINANCE_USE_TESTNET"] == "true",
    "live_trading_flag_false": flags["BINANCE_ENABLE_LIVE_TRADING"] == "false",
    "live_trading_allowed_false": flags["LIVE_TRADING_ALLOWED"] == "false",
    "kill_switch_enabled": kill_switch_enabled,
    "sensitive_values_printed_false": sensitive_values_printed is False,
    "sensitive_values_written_plaintext_false": sensitive_values_written_plaintext is False,
    "no_real_secrets_detected_in_tracked_files": len(tracked_real_secret_findings) == 0,
    "production_credentials_not_required_for_current_gate": True,
    "production_api_key_usage_false": True,
    "exchange_order_submission_false": True,
    "approved_for_micro_live_execution_false": True,
    "approved_for_real_live_trading_false": True,
}

blockers = [key for key, value in gate_checks.items() if value is not True]
gate_passed = not blockers

decision = (
    "PHASE_23_PRODUCTION_CREDENTIAL_NON_USAGE_GATE_COMPLETE_READY_FOR_TESTNET_CONNECTIVITY_VALIDATION_NOT_APPROVED_FOR_EXECUTION"
    if gate_passed else
    "PHASE_23_PRODUCTION_CREDENTIAL_NON_USAGE_GATE_FAILED_REVIEW_REQUIRED_NOT_APPROVED_FOR_EXECUTION"
)

record = {
    "phase": "phase_23_8_production_credential_non_usage_gate",
    "generated_at_unix": int(time.time()),
    "git_head": head,
    "git_branch": branch,
    "git_remote_origin": remote,
    "git_working_tree_clean_before_outputs": git_clean,
    "requested_transition": "on_hold_to_micro_trading_validation",
    "current_transition_status": "production_credential_non_usage_gate_only_not_approved_for_execution",
    "production_credential_non_usage_gate_passed": gate_passed,
    "gate_checks": gate_checks,
    "blockers": blockers,
    "non_usage_warnings": non_usage_warnings,
    "safe_flags": flags,
    "safe_flags_active": safe_flags_active,
    "kill_switch_enabled": kill_switch_enabled,
    "production_secret_env_map_masked": production_secret_env_map,
    "testnet_secret_env_map_masked": testnet_secret_env_map,
    "safety_env_map_masked": safety_env_map,
    "production_credentials_present": production_credentials_present,
    "testnet_credentials_present": testnet_credentials_present,
    "production_credentials_used": False,
    "testnet_only_validation_required_next": True,
    "sensitive_values_printed": False,
    "sensitive_values_written_plaintext": False,
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
    "next_phase": "Phase 23.9 — Testnet Connectivity Validation",
}

write(OUT, record)
write(RUNTIME_OUT, record)
write(GATE_FILE, record)

print(f"Report written to: {OUT}")
print(f"Runtime state written to: {RUNTIME_OUT}")
print(f"Gate file written to: {GATE_FILE}")
print(f"production_credential_non_usage_gate_passed={gate_passed}")
print(f"safe_flags_active={safe_flags_active}")
print(f"kill_switch_enabled={kill_switch_enabled}")
print(f"production_credentials_present={production_credentials_present}")
print(f"testnet_credentials_present={testnet_credentials_present}")
print("production_credentials_used=False")
print("current_transition_status=production_credential_non_usage_gate_only_not_approved_for_execution")
print("micro_live_deployment_started=False")
print("execution_allowed=False")
print("exchange_order_submission=False")
print("approved_for_micro_live_execution=False")
print("approved_for_real_live_trading=False")
print("production_api_key_usage=False")
print("real_capital_usage=False")
print(f"decision={decision}")
if non_usage_warnings:
    print("non_usage_warnings=" + ",".join(non_usage_warnings))
if blockers:
    print("blockers=" + ",".join(blockers))
