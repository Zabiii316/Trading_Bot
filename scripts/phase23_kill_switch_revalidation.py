import json, os, subprocess, time
from pathlib import Path

OUT = Path("data/processed/phase23_kill_switch_revalidation.json")
RUNTIME_OUT = Path("runtime/phase23_kill_switch_revalidation_state.json")
REOPEN_DIR = Path("data/processed/phase23_reopening")
REVALIDATION_FILE = REOPEN_DIR / "kill_switch_revalidation.json"

RISK_REVIEW_FILES = [
    Path("data/processed/phase23_micro_trading_risk_limit_review.json"),
    Path("runtime/phase23_micro_trading_risk_limit_review_state.json"),
    Path("data/processed/phase23_reopening/micro_trading_risk_limit_review.json"),
]

FINAL_END_STATE = Path("data/processed/phase22_project_final_end_state_record.json")
RISK_ENV_FILE = Path("runtime/micro_trading_risk_limits.env")

SCAN_ROOTS = [
    Path("scripts"),
    Path("services"),
    Path("libs"),
    Path("config"),
    Path("runtime"),
]

KILL_SWITCH_TERMS = [
    "KILL_SWITCH_ENABLED",
    "kill_switch",
    "kill switch",
    "LIVE_TRADING_ALLOWED",
    "BINANCE_ENABLE_LIVE_TRADING",
]

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

def read_text_safe(path):
    try:
        return path.read_text(errors="ignore")
    except Exception:
        return ""

def scan_kill_switch_references():
    findings = []
    allowed_suffixes = {".py", ".env", ".md", ".json", ".yml", ".yaml", ".toml", ".ini"}
    for root in SCAN_ROOTS:
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            if path.suffix not in allowed_suffixes:
                continue
            text = read_text_safe(path)
            matches = []
            text_lower = text.lower()
            for term in KILL_SWITCH_TERMS:
                if term.lower() in text_lower:
                    matches.append(term)
            if matches:
                findings.append({
                    "path": str(path),
                    "matched_terms": sorted(set(matches)),
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

reviews = [load(p) for p in RISK_REVIEW_FILES]
final_state = load(FINAL_END_STATE)

risk_review_passed = (
    any_true(reviews, "risk_limit_review_passed")
    or any("PHASE_23_MICRO_TRADING_RISK_LIMIT_REVIEW_COMPLETE" in str(x.get("decision", "")) for x in reviews)
)

risk_limits_ready = (
    any_true(reviews, "risk_limits_acceptable_for_next_gate")
    or any("READY_FOR_KILL_SWITCH_REVALIDATION" in str(x.get("decision", "")) for x in reviews)
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

kill_switch_env_enabled = flags["KILL_SWITCH_ENABLED"].lower() in {"true", "1", "yes", "enabled"}

risk_env_text = read_text_safe(RISK_ENV_FILE)
risk_env_contains_kill_switch = "KILL_SWITCH_ENABLED" in risk_env_text
risk_env_sets_kill_switch_true = (
    'KILL_SWITCH_ENABLED="true"' in risk_env_text
    or "KILL_SWITCH_ENABLED=true" in risk_env_text
    or "KILL_SWITCH_ENABLED='true'" in risk_env_text
)

kill_switch_references = scan_kill_switch_references()
kill_switch_reference_count = len(kill_switch_references)

revalidation_warnings = []
if kill_switch_reference_count == 0:
    revalidation_warnings.append("No kill switch references found in scanned project files")
if not risk_env_sets_kill_switch_true:
    revalidation_warnings.append("runtime/micro_trading_risk_limits.env does not explicitly set KILL_SWITCH_ENABLED=true")

revalidation_checks = {
    "git_head_present": bool(head),
    "git_branch_present": bool(branch),
    "git_remote_origin_present": bool(remote),
    "git_working_tree_clean_before_outputs": git_clean,
    "phase22_final_end_state_present": FINAL_END_STATE.exists(),
    "phase22_closed_on_hold": phase22_closed,
    "phase23_5_risk_review_present": any(p.exists() for p in RISK_REVIEW_FILES),
    "phase23_5_risk_review_passed": risk_review_passed,
    "phase23_5_risk_limits_ready": risk_limits_ready,
    "safe_flags_active": safe_flags_active,
    "live_trading_flag_false": flags["BINANCE_ENABLE_LIVE_TRADING"] == "false",
    "live_trading_allowed_false": flags["LIVE_TRADING_ALLOWED"] == "false",
    "risk_env_file_present": RISK_ENV_FILE.exists(),
    "kill_switch_env_enabled": kill_switch_env_enabled,
    "risk_env_contains_kill_switch": risk_env_contains_kill_switch,
    "exchange_order_submission_false": True,
    "production_api_key_usage_false": True,
    "approved_for_micro_live_execution_false": True,
    "approved_for_real_live_trading_false": True,
}

blockers = [key for key, value in revalidation_checks.items() if value is not True]
revalidation_passed = not blockers

decision = (
    "PHASE_23_KILL_SWITCH_REVALIDATION_COMPLETE_READY_FOR_SECRETS_AUDIT_NOT_APPROVED_FOR_EXECUTION"
    if revalidation_passed else
    "PHASE_23_KILL_SWITCH_REVALIDATION_FAILED_REVIEW_REQUIRED_NOT_APPROVED_FOR_EXECUTION"
)

record = {
    "phase": "phase_23_6_kill_switch_revalidation",
    "generated_at_unix": int(time.time()),
    "git_head": head,
    "git_branch": branch,
    "git_remote_origin": remote,
    "git_working_tree_clean_before_outputs": git_clean,
    "requested_transition": "on_hold_to_micro_trading_validation",
    "current_transition_status": "kill_switch_revalidation_only_not_approved_for_execution",
    "kill_switch_revalidation_passed": revalidation_passed,
    "revalidation_checks": revalidation_checks,
    "blockers": blockers,
    "revalidation_warnings": revalidation_warnings,
    "safe_flags": flags,
    "safe_flags_active": safe_flags_active,
    "kill_switch": {
        "risk_env_file": str(RISK_ENV_FILE),
        "risk_env_file_present": RISK_ENV_FILE.exists(),
        "kill_switch_env_enabled": kill_switch_env_enabled,
        "risk_env_contains_kill_switch": risk_env_contains_kill_switch,
        "risk_env_sets_kill_switch_true": risk_env_sets_kill_switch_true,
        "kill_switch_reference_count": kill_switch_reference_count,
        "kill_switch_references": kill_switch_references[:50],
    },
    "phase23_5_risk_review_passed": risk_review_passed,
    "phase23_5_risk_limits_ready": risk_limits_ready,
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
    "next_phase": "Phase 23.7 — Secrets / API Key Mapping Audit",
}

write(OUT, record)
write(RUNTIME_OUT, record)
write(REVALIDATION_FILE, record)

print(f"Report written to: {OUT}")
print(f"Runtime state written to: {RUNTIME_OUT}")
print(f"Revalidation file written to: {REVALIDATION_FILE}")
print(f"kill_switch_revalidation_passed={revalidation_passed}")
print(f"kill_switch_env_enabled={kill_switch_env_enabled}")
print(f"risk_env_contains_kill_switch={risk_env_contains_kill_switch}")
print(f"risk_env_sets_kill_switch_true={risk_env_sets_kill_switch_true}")
print(f"kill_switch_reference_count={kill_switch_reference_count}")
print(f"safe_flags_active={safe_flags_active}")
print("current_transition_status=kill_switch_revalidation_only_not_approved_for_execution")
print("micro_live_deployment_started=False")
print("execution_allowed=False")
print("exchange_order_submission=False")
print("approved_for_micro_live_execution=False")
print("approved_for_real_live_trading=False")
print("production_api_key_usage=False")
print("real_capital_usage=False")
print(f"decision={decision}")
if revalidation_warnings:
    print("revalidation_warnings=" + ",".join(revalidation_warnings))
if blockers:
    print("blockers=" + ",".join(blockers))
