import json, os, subprocess, time
from pathlib import Path

OUT = Path("data/processed/phase23_paper_shadow_monitoring_validation.json")
RUNTIME_OUT = Path("runtime/phase23_paper_shadow_monitoring_validation_state.json")
VALIDATION_FILE = Path("data/processed/phase23_reopening/paper_shadow_monitoring_validation.json")

START_GATE_FILES = [
    Path("data/processed/phase23_paper_shadow_start_gate.json"),
    Path("runtime/phase23_paper_shadow_start_gate_state.json"),
    Path("data/processed/phase23_reopening/paper_shadow_start_gate.json"),
]

FINAL_END_STATE = Path("data/processed/phase22_project_final_end_state_record.json")

SCAN_ROOTS = [
    Path("scripts"),
    Path("services"),
    Path("libs"),
    Path("config"),
    Path("runtime"),
]

MONITORING_TERMS = [
    "monitor",
    "monitoring",
    "alert",
    "alerts",
    "heartbeat",
    "health",
    "metrics",
    "runtime",
    "evidence",
    "log",
    "logs",
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

def any_false(items, key):
    return any(item.get(key) is False for item in items)

def read_text_safe(path):
    try:
        return path.read_text(errors="ignore")
    except Exception:
        return ""

def scan_monitoring_references():
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
            haystack = (str(path) + "\n" + text).lower()
            matches = sorted({term for term in MONITORING_TERMS if term.lower() in haystack})

            if matches:
                findings.append({
                    "path": str(path),
                    "matched_terms": matches,
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

gates = [load(p) for p in START_GATE_FILES]
final_state = load(FINAL_END_STATE)

start_gate_passed = (
    any_true(gates, "paper_shadow_start_gate_passed")
    or any("PHASE_23_PAPER_SHADOW_START_GATE_CREATED" in str(x.get("decision", "")) for x in gates)
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

monitoring_findings = scan_monitoring_references()
monitoring_reference_count = len(monitoring_findings)

warnings = []
if monitoring_reference_count == 0:
    warnings.append("No monitoring references found in scanned roots")

checks = {
    "git_head_present": bool(head),
    "git_branch_present": bool(branch),
    "git_remote_origin_present": bool(remote),
    "git_working_tree_clean_before_outputs": git_clean,
    "phase22_final_end_state_present": FINAL_END_STATE.exists(),
    "phase22_closed_on_hold": phase22_closed,
    "phase23_14_start_gate_present": any(p.exists() for p in START_GATE_FILES),
    "phase23_14_start_gate_passed": start_gate_passed,
    "safe_flags_active": safe_flags_active,
    "binance_testnet_true": flags["BINANCE_TESTNET"] == "true",
    "binance_use_testnet_true": flags["BINANCE_USE_TESTNET"] == "true",
    "live_trading_flag_false": flags["BINANCE_ENABLE_LIVE_TRADING"] == "false",
    "live_trading_allowed_false": flags["LIVE_TRADING_ALLOWED"] == "false",
    "kill_switch_enabled": kill_switch_enabled,
    "prior_paper_shadow_not_started": any_false(gates, "paper_shadow_started"),
    "prior_paper_shadow_start_not_approved": any_false(gates, "approved_for_paper_shadow_start"),
    "prior_monitoring_not_started": any_false(gates, "monitoring_started"),
    "prior_execution_allowed_false": any_false(gates, "execution_allowed"),
    "prior_exchange_order_submission_false": any_false(gates, "exchange_order_submission"),
    "monitoring_scan_completed": isinstance(monitoring_findings, list),
    "validation_only_no_monitoring_start": True,
    "signed_endpoint_called_false": True,
    "account_endpoint_called_false": True,
    "order_endpoint_called_false": True,
    "network_call_made_false": True,
    "production_credentials_used_false": True,
}

blockers = [k for k, v in checks.items() if v is not True]
passed = not blockers

decision = (
    "PHASE_23_PAPER_SHADOW_MONITORING_VALIDATION_COMPLETE_READY_FOR_PAPER_SHADOW_RESULT_REVIEW_NOT_APPROVED_FOR_EXECUTION"
    if passed else
    "PHASE_23_PAPER_SHADOW_MONITORING_VALIDATION_FAILED_REVIEW_REQUIRED_NOT_APPROVED_FOR_EXECUTION"
)

record = {
    "phase": "phase_23_15_paper_shadow_monitoring_validation",
    "generated_at_unix": int(time.time()),
    "git_head": head,
    "git_branch": branch,
    "git_remote_origin": remote,
    "git_working_tree_clean_before_outputs": git_clean,
    "current_transition_status": "paper_shadow_monitoring_validation_only_not_started_not_approved_for_execution",
    "paper_shadow_monitoring_validation_passed": passed,
    "validation_checks": checks,
    "blockers": blockers,
    "warnings": warnings,
    "safe_flags": flags,
    "safe_flags_active": safe_flags_active,
    "kill_switch_enabled": kill_switch_enabled,
    "monitoring_scan": {
        "scan_roots": [str(x) for x in SCAN_ROOTS],
        "monitoring_reference_count": monitoring_reference_count,
        "monitoring_reference_files_limited": monitoring_findings[:75],
    },
    "monitoring_validation_scope": {
        "mode": "validation_only",
        "monitoring_start": False,
        "paper_shadow_engine_start": False,
        "exchange_submission": False,
        "signed_endpoint_call": False,
        "account_endpoint_call": False,
        "order_endpoint_call": False,
        "network_call": False,
        "production_credentials_used": False,
        "real_capital_usage": False
    },
    "paper_shadow_started": False,
    "paper_shadow_start_approved": False,
    "approved_for_paper_shadow_start": False,
    "approved_for_paper_shadow": False,
    "monitoring_started": False,
    "run_dry_run_now": False,
    "run_backtest_now": False,
    "signed_endpoint_called": False,
    "account_endpoint_called": False,
    "order_endpoint_called": False,
    "network_call_made": False,
    "production_credentials_used": False,
    "execution_allowed": False,
    "approved_for_execution": False,
    "approved_for_live": False,
    "exchange_order_submission": False,
    "approved_for_micro_live_execution": False,
    "approved_for_real_live_trading": False,
    "production_api_key_usage": False,
    "real_capital_usage": False,
    "decision": decision,
    "next_phase": "Phase 23.16 — Paper Shadow Result Review"
}

write(OUT, record)
write(RUNTIME_OUT, record)
write(VALIDATION_FILE, record)

print(f"Report written to: {OUT}")
print(f"Runtime state written to: {RUNTIME_OUT}")
print(f"Validation file written to: {VALIDATION_FILE}")
print(f"paper_shadow_monitoring_validation_passed={passed}")
print(f"safe_flags_active={safe_flags_active}")
print(f"kill_switch_enabled={kill_switch_enabled}")
print(f"monitoring_reference_count={monitoring_reference_count}")
print("current_transition_status=paper_shadow_monitoring_validation_only_not_started_not_approved_for_execution")
print("paper_shadow_started=False")
print("approved_for_paper_shadow_start=False")
print("monitoring_started=False")
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
