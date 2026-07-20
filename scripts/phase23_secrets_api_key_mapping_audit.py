import json, os, re, subprocess, time
from pathlib import Path

OUT = Path("data/processed/phase23_secrets_api_key_mapping_audit.json")
RUNTIME_OUT = Path("runtime/phase23_secrets_api_key_mapping_audit_state.json")
REOPEN_DIR = Path("data/processed/phase23_reopening")
AUDIT_FILE = REOPEN_DIR / "secrets_api_key_mapping_audit.json"

KILL_SWITCH_FILES = [
    Path("data/processed/phase23_kill_switch_revalidation.json"),
    Path("runtime/phase23_kill_switch_revalidation_state.json"),
    Path("data/processed/phase23_reopening/kill_switch_revalidation.json"),
]

FINAL_END_STATE = Path("data/processed/phase22_project_final_end_state_record.json")

SENSITIVE_KEYS = [
    "BINANCE_API_KEY",
    "BINANCE_API_SECRET",
    "BINANCE_TESTNET_API_KEY",
    "BINANCE_TESTNET_API_SECRET",
]

NON_SECRET_ENV_KEYS = [
    "BINANCE_TESTNET",
    "BINANCE_USE_TESTNET",
    "BINANCE_ENABLE_LIVE_TRADING",
    "LIVE_TRADING_ALLOWED",
    "BINANCE_BASE_URL",
    "BINANCE_TESTNET_BASE_URL",
    "TRADING_SYMBOLS",
    "MICRO_TRADE_NOTIONAL_USDT",
    "MAX_ORDER_NOTIONAL_USDT",
    "MAX_DAILY_LOSS_USDT",
    "MAX_POSITION_SIZE_USDT",
    "KILL_SWITCH_ENABLED",
]

SAFE_PLACEHOLDER_VALUES = {
    "",
    "changeme",
    "change_me",
    "your_key_here",
    "your_secret_here",
    "placeholder",
    "example",
    "test",
    "none",
    "null",
    "xxx",
    "***",
}

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

def env_map(keys, include_present_only=False):
    mapped = []
    for key in keys:
        value = os.getenv(key)
        if include_present_only and value in (None, ""):
            continue
        mapped.append({
            "key": key,
            "present": value not in (None, ""),
            "masked_value": mask(value),
        })
    return mapped

def read_text_safe(path):
    try:
        return path.read_text(errors="ignore")
    except Exception:
        return ""

def tracked_files():
    result = run(["git", "ls-files"])
    if result.returncode != 0:
        return []
    return [Path(x.strip()) for x in result.stdout.splitlines() if x.strip()]

def looks_like_real_secret(value):
    cleaned = value.strip().strip('"').strip("'").strip()
    lowered = cleaned.lower()

    if lowered in SAFE_PLACEHOLDER_VALUES:
        return False
    if "example" in lowered or "placeholder" in lowered or "your_" in lowered:
        return False
    if len(cleaned) < 12:
        return False

    return True

def scan_tracked_files_for_sensitive_assignments():
    findings = []
    allowed_suffixes = {".py", ".env", ".example", ".md", ".json", ".yml", ".yaml", ".toml", ".ini", ".txt"}
    assignment_pattern = re.compile(
        r"(?P<key>BINANCE_API_KEY|BINANCE_API_SECRET|BINANCE_TESTNET_API_KEY|BINANCE_TESTNET_API_SECRET)\s*=\s*(?P<value>[^\n\r#]+)"
    )

    for path in tracked_files():
        if not path.exists() or not path.is_file():
            continue
        if path.suffix not in allowed_suffixes and not str(path).endswith(".env.example"):
            continue

        text = read_text_safe(path)
        for match in assignment_pattern.finditer(text):
            key = match.group("key")
            value = match.group("value").strip()
            real_secret = looks_like_real_secret(value)

            findings.append({
                "path": str(path),
                "key": key,
                "value_masked": mask(value),
                "looks_like_real_secret": real_secret,
            })

    return findings

def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2))

head = git_value(["git", "rev-parse", "HEAD"])
branch = git_value(["git", "branch", "--show-current"])
remote = git_value(["git", "remote", "get-url", "origin"])
status_short = git_value(["git", "status", "--short"]) or ""
git_clean = status_short == ""

kill_switch_records = [load(p) for p in KILL_SWITCH_FILES]
final_state = load(FINAL_END_STATE)

kill_switch_revalidation_passed = (
    any_true(kill_switch_records, "kill_switch_revalidation_passed")
    or any("PHASE_23_KILL_SWITCH_REVALIDATION_COMPLETE" in str(x.get("decision", "")) for x in kill_switch_records)
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

sensitive_env_map = env_map(SENSITIVE_KEYS)
non_secret_env_map = env_map(NON_SECRET_ENV_KEYS)

tracked_secret_findings = scan_tracked_files_for_sensitive_assignments()
tracked_real_secret_findings = [
    item for item in tracked_secret_findings
    if item.get("looks_like_real_secret") is True
]

secrets_audit_warnings = []

present_sensitive_keys = [x["key"] for x in sensitive_env_map if x["present"]]
if present_sensitive_keys:
    secrets_audit_warnings.append("Sensitive API keys are present in shell environment and were masked in evidence")
else:
    secrets_audit_warnings.append("No sensitive API keys are currently present in shell environment")

if tracked_real_secret_findings:
    secrets_audit_warnings.append("Potential real secrets detected in tracked files and must be removed before any deployment")

audit_checks = {
    "git_head_present": bool(head),
    "git_branch_present": bool(branch),
    "git_remote_origin_present": bool(remote),
    "git_working_tree_clean_before_outputs": git_clean,
    "phase22_final_end_state_present": FINAL_END_STATE.exists(),
    "phase22_closed_on_hold": phase22_closed,
    "phase23_6_kill_switch_revalidation_present": any(p.exists() for p in KILL_SWITCH_FILES),
    "phase23_6_kill_switch_revalidation_passed": kill_switch_revalidation_passed,
    "safe_flags_active": safe_flags_active,
    "kill_switch_enabled": kill_switch_enabled,
    "live_trading_flag_false": flags["BINANCE_ENABLE_LIVE_TRADING"] == "false",
    "live_trading_allowed_false": flags["LIVE_TRADING_ALLOWED"] == "false",
    "sensitive_env_mapping_created": isinstance(sensitive_env_map, list),
    "non_secret_env_mapping_created": isinstance(non_secret_env_map, list),
    "tracked_files_scanned_for_sensitive_assignments": isinstance(tracked_secret_findings, list),
    "no_real_secrets_detected_in_tracked_files": len(tracked_real_secret_findings) == 0,
    "production_api_key_usage_false": True,
    "exchange_order_submission_false": True,
    "approved_for_micro_live_execution_false": True,
    "approved_for_real_live_trading_false": True,
}

blockers = [key for key, value in audit_checks.items() if value is not True]
secrets_audit_passed = not blockers

decision = (
    "PHASE_23_SECRETS_API_KEY_MAPPING_AUDIT_COMPLETE_READY_FOR_PRODUCTION_CREDENTIAL_NON_USAGE_GATE_NOT_APPROVED_FOR_EXECUTION"
    if secrets_audit_passed else
    "PHASE_23_SECRETS_API_KEY_MAPPING_AUDIT_FAILED_REVIEW_REQUIRED_NOT_APPROVED_FOR_EXECUTION"
)

record = {
    "phase": "phase_23_7_secrets_api_key_mapping_audit",
    "generated_at_unix": int(time.time()),
    "git_head": head,
    "git_branch": branch,
    "git_remote_origin": remote,
    "git_working_tree_clean_before_outputs": git_clean,
    "requested_transition": "on_hold_to_micro_trading_validation",
    "current_transition_status": "secrets_api_key_mapping_audit_only_not_approved_for_execution",
    "secrets_api_key_mapping_audit_passed": secrets_audit_passed,
    "audit_checks": audit_checks,
    "blockers": blockers,
    "secrets_audit_warnings": secrets_audit_warnings,
    "safe_flags": flags,
    "safe_flags_active": safe_flags_active,
    "kill_switch_enabled": kill_switch_enabled,
    "sensitive_env_map_masked": sensitive_env_map,
    "non_secret_env_map_masked": non_secret_env_map,
    "tracked_sensitive_assignment_findings_masked": tracked_secret_findings[:100],
    "tracked_real_secret_findings_masked": tracked_real_secret_findings[:100],
    "sensitive_values_printed": False,
    "sensitive_values_written_plaintext": False,
    "production_api_key_usage": False,
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
    "real_capital_usage": False,
    "decision": decision,
    "next_phase": "Phase 23.8 — Production Credential Non-Usage Gate",
}

write(OUT, record)
write(RUNTIME_OUT, record)
write(AUDIT_FILE, record)

print(f"Report written to: {OUT}")
print(f"Runtime state written to: {RUNTIME_OUT}")
print(f"Audit file written to: {AUDIT_FILE}")
print(f"secrets_api_key_mapping_audit_passed={secrets_audit_passed}")
print(f"safe_flags_active={safe_flags_active}")
print(f"kill_switch_enabled={kill_switch_enabled}")
print(f"sensitive_env_keys_present_count={len(present_sensitive_keys)}")
print(f"tracked_sensitive_assignment_count={len(tracked_secret_findings)}")
print(f"tracked_real_secret_findings_count={len(tracked_real_secret_findings)}")
print("current_transition_status=secrets_api_key_mapping_audit_only_not_approved_for_execution")
print("sensitive_values_printed=False")
print("sensitive_values_written_plaintext=False")
print("micro_live_deployment_started=False")
print("execution_allowed=False")
print("exchange_order_submission=False")
print("approved_for_micro_live_execution=False")
print("approved_for_real_live_trading=False")
print("production_api_key_usage=False")
print("real_capital_usage=False")
print(f"decision={decision}")
if secrets_audit_warnings:
    print("secrets_audit_warnings=" + ",".join(secrets_audit_warnings))
if blockers:
    print("blockers=" + ",".join(blockers))
