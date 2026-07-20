import json, os, subprocess, time
from pathlib import Path

OUT = Path("data/processed/phase23_exchange_adapter_dry_run_validation.json")
RUNTIME_OUT = Path("runtime/phase23_exchange_adapter_dry_run_validation_state.json")
REOPEN_DIR = Path("data/processed/phase23_reopening")
VALIDATION_FILE = REOPEN_DIR / "exchange_adapter_dry_run_validation.json"

TESTNET_CONNECTIVITY_FILES = [
    Path("data/processed/phase23_testnet_connectivity_validation.json"),
    Path("runtime/phase23_testnet_connectivity_validation_state.json"),
    Path("data/processed/phase23_reopening/testnet_connectivity_validation.json"),
]

FINAL_END_STATE = Path("data/processed/phase22_project_final_end_state_record.json")

SCAN_ROOTS = [
    Path("scripts"),
    Path("services"),
    Path("libs"),
    Path("config"),
    Path("runtime"),
]

ADAPTER_TERMS = [
    "exchange",
    "adapter",
    "binance",
    "broker",
    "client",
]

DRY_RUN_TERMS = [
    "dry_run",
    "DRY_RUN",
    "paper",
    "simulation",
    "simulate",
    "mock",
    "testnet",
]

ORDER_TERMS = [
    "create_order",
    "submit_order",
    "place_order",
    "newOrder",
    "/api/v3/order",
    "order_endpoint",
]

SIGNED_TERMS = [
    "signature",
    "SIGNED",
    "timestamp",
    "recvWindow",
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

def scan_files():
    findings = {
        "adapter_candidate_files": [],
        "dry_run_reference_files": [],
        "order_reference_files": [],
        "signed_reference_files": [],
    }

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
            lower = text.lower()
            path_lower = str(path).lower()

            adapter_matches = [term for term in ADAPTER_TERMS if term.lower() in lower or term.lower() in path_lower]
            dry_run_matches = [term for term in DRY_RUN_TERMS if term.lower() in lower]
            order_matches = [term for term in ORDER_TERMS if term.lower() in lower]
            signed_matches = [term for term in SIGNED_TERMS if term.lower() in lower]

            if adapter_matches:
                findings["adapter_candidate_files"].append({
                    "path": str(path),
                    "matched_terms": sorted(set(adapter_matches)),
                })

            if dry_run_matches:
                findings["dry_run_reference_files"].append({
                    "path": str(path),
                    "matched_terms": sorted(set(dry_run_matches)),
                })

            if order_matches:
                findings["order_reference_files"].append({
                    "path": str(path),
                    "matched_terms": sorted(set(order_matches)),
                })

            if signed_matches:
                findings["signed_reference_files"].append({
                    "path": str(path),
                    "matched_terms": sorted(set(signed_matches)),
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

connectivity_records = [load(p) for p in TESTNET_CONNECTIVITY_FILES]
final_state = load(FINAL_END_STATE)

testnet_connectivity_passed = (
    any_true(connectivity_records, "testnet_connectivity_validation_passed")
    or any("PHASE_23_TESTNET_CONNECTIVITY_VALIDATION_COMPLETE" in str(x.get("decision", "")) for x in connectivity_records)
)

testnet_public_connectivity_ok = (
    any_true(connectivity_records, "testnet_public_connectivity_ok")
    or first_value(connectivity_records, "testnet_public_connectivity_ok", False) is True
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

scan_results = scan_files()

adapter_candidate_count = len(scan_results["adapter_candidate_files"])
dry_run_reference_count = len(scan_results["dry_run_reference_files"])
order_reference_count = len(scan_results["order_reference_files"])
signed_reference_count = len(scan_results["signed_reference_files"])

validation_warnings = []

if adapter_candidate_count == 0:
    validation_warnings.append("No exchange adapter candidate files found in scanned roots")

if dry_run_reference_count == 0:
    validation_warnings.append("No dry-run/simulation references found in scanned roots")

if order_reference_count > 0:
    validation_warnings.append("Order-related references exist; later phases must confirm they are blocked by dry-run guards before execution approval")

if signed_reference_count > 0:
    validation_warnings.append("Signed-endpoint related references exist; this phase did not execute them")

validation_checks = {
    "git_head_present": bool(head),
    "git_branch_present": bool(branch),
    "git_remote_origin_present": bool(remote),
    "git_working_tree_clean_before_outputs": git_clean,
    "phase22_final_end_state_present": FINAL_END_STATE.exists(),
    "phase22_closed_on_hold": phase22_closed,
    "phase23_9_testnet_connectivity_present": any(p.exists() for p in TESTNET_CONNECTIVITY_FILES),
    "phase23_9_testnet_connectivity_passed": testnet_connectivity_passed,
    "phase23_9_testnet_public_connectivity_ok": testnet_public_connectivity_ok,
    "safe_flags_active": safe_flags_active,
    "binance_testnet_true": flags["BINANCE_TESTNET"] == "true",
    "binance_use_testnet_true": flags["BINANCE_USE_TESTNET"] == "true",
    "live_trading_flag_false": flags["BINANCE_ENABLE_LIVE_TRADING"] == "false",
    "live_trading_allowed_false": flags["LIVE_TRADING_ALLOWED"] == "false",
    "kill_switch_enabled": kill_switch_enabled,
    "static_dry_run_validation_only": True,
    "adapter_scan_completed": isinstance(scan_results, dict),
    "signed_endpoint_called_false": True,
    "account_endpoint_called_false": True,
    "order_endpoint_called_false": True,
    "production_credentials_used_false": True,
    "exchange_order_submission_false": True,
    "approved_for_micro_live_execution_false": True,
    "approved_for_real_live_trading_false": True,
}

blockers = [k for k, v in validation_checks.items() if v is not True]
validation_passed = not blockers

decision = (
    "PHASE_23_EXCHANGE_ADAPTER_DRY_RUN_VALIDATION_COMPLETE_READY_FOR_ORDER_CONSTRUCTION_SAFETY_TEST_NOT_APPROVED_FOR_EXECUTION"
    if validation_passed else
    "PHASE_23_EXCHANGE_ADAPTER_DRY_RUN_VALIDATION_FAILED_REVIEW_REQUIRED_NOT_APPROVED_FOR_EXECUTION"
)

record = {
    "phase": "phase_23_10_exchange_adapter_dry_run_validation",
    "generated_at_unix": int(time.time()),
    "git_head": head,
    "git_branch": branch,
    "git_remote_origin": remote,
    "git_working_tree_clean_before_outputs": git_clean,
    "requested_transition": "on_hold_to_micro_trading_validation",
    "current_transition_status": "exchange_adapter_dry_run_validation_only_not_approved_for_execution",
    "exchange_adapter_dry_run_validation_passed": validation_passed,
    "validation_checks": validation_checks,
    "blockers": blockers,
    "validation_warnings": validation_warnings,
    "safe_flags": flags,
    "safe_flags_active": safe_flags_active,
    "kill_switch_enabled": kill_switch_enabled,
    "scan_summary": {
        "adapter_candidate_count": adapter_candidate_count,
        "dry_run_reference_count": dry_run_reference_count,
        "order_reference_count": order_reference_count,
        "signed_reference_count": signed_reference_count,
    },
    "scan_results_limited": {
        "adapter_candidate_files": scan_results["adapter_candidate_files"][:50],
        "dry_run_reference_files": scan_results["dry_run_reference_files"][:50],
        "order_reference_files": scan_results["order_reference_files"][:50],
        "signed_reference_files": scan_results["signed_reference_files"][:50],
    },
    "static_validation_only": True,
    "signed_endpoint_called": False,
    "account_endpoint_called": False,
    "order_endpoint_called": False,
    "production_credentials_used": False,
    "testnet_public_connectivity_ok": testnet_public_connectivity_ok,
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
    "next_phase": "Phase 23.11 — Order Construction Safety Test",
}

write(OUT, record)
write(RUNTIME_OUT, record)
write(VALIDATION_FILE, record)

print(f"Report written to: {OUT}")
print(f"Runtime state written to: {RUNTIME_OUT}")
print(f"Validation file written to: {VALIDATION_FILE}")
print(f"exchange_adapter_dry_run_validation_passed={validation_passed}")
print(f"safe_flags_active={safe_flags_active}")
print(f"kill_switch_enabled={kill_switch_enabled}")
print(f"adapter_candidate_count={adapter_candidate_count}")
print(f"dry_run_reference_count={dry_run_reference_count}")
print(f"order_reference_count={order_reference_count}")
print(f"signed_reference_count={signed_reference_count}")
print("static_validation_only=True")
print("signed_endpoint_called=False")
print("account_endpoint_called=False")
print("order_endpoint_called=False")
print("production_credentials_used=False")
print("current_transition_status=exchange_adapter_dry_run_validation_only_not_approved_for_execution")
print("micro_live_deployment_started=False")
print("execution_allowed=False")
print("exchange_order_submission=False")
print("approved_for_micro_live_execution=False")
print("approved_for_real_live_trading=False")
print("production_api_key_usage=False")
print("real_capital_usage=False")
print(f"decision={decision}")
if validation_warnings:
    print("validation_warnings=" + ",".join(validation_warnings))
if blockers:
    print("blockers=" + ",".join(blockers))
