import json, os, subprocess, time, urllib.parse, urllib.request
from pathlib import Path

OUT = Path("data/processed/phase23_testnet_connectivity_validation.json")
RUNTIME_OUT = Path("runtime/phase23_testnet_connectivity_validation_state.json")
REOPEN_DIR = Path("data/processed/phase23_reopening")
VALIDATION_FILE = REOPEN_DIR / "testnet_connectivity_validation.json"

NON_USAGE_GATE_FILES = [
    Path("data/processed/phase23_production_credential_non_usage_gate.json"),
    Path("runtime/phase23_production_credential_non_usage_gate_state.json"),
    Path("data/processed/phase23_reopening/production_credential_non_usage_gate.json"),
]

FINAL_END_STATE = Path("data/processed/phase22_project_final_end_state_record.json")

DEFAULT_TESTNET_BASE_URL = "https://testnet.binance.vision"

PUBLIC_ENDPOINTS = [
    "/api/v3/ping",
    "/api/v3/time",
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

def safe_get_json(url, timeout=10):
    started = time.time()
    try:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "phase23-testnet-connectivity-validation",
                "Accept": "application/json",
            },
            method="GET",
        )
        with urllib.request.urlopen(req, timeout=timeout) as response:
            raw = response.read().decode("utf-8", errors="replace")
            elapsed_ms = int((time.time() - started) * 1000)
            try:
                body = json.loads(raw) if raw else {}
            except Exception:
                body = {"raw": raw[:500]}
            return {
                "ok": 200 <= response.status < 300,
                "status": response.status,
                "elapsed_ms": elapsed_ms,
                "body_preview": body,
                "error": None,
            }
    except Exception as exc:
        elapsed_ms = int((time.time() - started) * 1000)
        return {
            "ok": False,
            "status": None,
            "elapsed_ms": elapsed_ms,
            "body_preview": None,
            "error": str(exc),
        }

def normalize_base_url(value):
    base = value.strip() if value else DEFAULT_TESTNET_BASE_URL
    return base.rstrip("/")

def first_symbol(symbols):
    if not symbols:
        return "BTCUSDT"
    return symbols.split(",")[0].strip() or "BTCUSDT"

def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2))

head = git_value(["git", "rev-parse", "HEAD"])
branch = git_value(["git", "branch", "--show-current"])
remote = git_value(["git", "remote", "get-url", "origin"])
status_short = git_value(["git", "status", "--short"]) or ""
git_clean = status_short == ""

gate_records = [load(p) for p in NON_USAGE_GATE_FILES]
final_state = load(FINAL_END_STATE)

non_usage_gate_passed = (
    any_true(gate_records, "production_credential_non_usage_gate_passed")
    or any("PHASE_23_PRODUCTION_CREDENTIAL_NON_USAGE_GATE_COMPLETE" in str(x.get("decision", "")) for x in gate_records)
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

testnet_base_url = normalize_base_url(os.getenv("BINANCE_TESTNET_BASE_URL", ""))
production_base_url = normalize_base_url(os.getenv("BINANCE_BASE_URL", ""))

uses_testnet_base = "testnet" in testnet_base_url.lower()
does_not_use_production_base = testnet_base_url != production_base_url or "testnet" in testnet_base_url.lower()

trading_symbols = os.getenv("TRADING_SYMBOLS", "BTCUSDT")
symbol = first_symbol(trading_symbols)

connectivity_results = {}
for endpoint in PUBLIC_ENDPOINTS:
    url = testnet_base_url + endpoint
    connectivity_results[endpoint] = safe_get_json(url)

exchange_info_url = (
    testnet_base_url
    + "/api/v3/exchangeInfo?"
    + urllib.parse.urlencode({"symbol": symbol})
)
exchange_info_result = safe_get_json(exchange_info_url)

public_ping_ok = connectivity_results["/api/v3/ping"]["ok"]
public_time_ok = connectivity_results["/api/v3/time"]["ok"]
exchange_info_ok = exchange_info_result["ok"]

testnet_public_connectivity_ok = public_ping_ok and public_time_ok

validation_warnings = []

if not exchange_info_ok:
    validation_warnings.append(f"exchangeInfo public validation failed for symbol {symbol}")

if not uses_testnet_base:
    validation_warnings.append("BINANCE_TESTNET_BASE_URL does not clearly contain the word testnet; confirm endpoint manually")

validation_checks = {
    "git_head_present": bool(head),
    "git_branch_present": bool(branch),
    "git_remote_origin_present": bool(remote),
    "git_working_tree_clean_before_outputs": git_clean,
    "phase22_final_end_state_present": FINAL_END_STATE.exists(),
    "phase22_closed_on_hold": phase22_closed,
    "phase23_8_non_usage_gate_present": any(p.exists() for p in NON_USAGE_GATE_FILES),
    "phase23_8_non_usage_gate_passed": non_usage_gate_passed,
    "safe_flags_active": safe_flags_active,
    "binance_testnet_true": flags["BINANCE_TESTNET"] == "true",
    "binance_use_testnet_true": flags["BINANCE_USE_TESTNET"] == "true",
    "live_trading_flag_false": flags["BINANCE_ENABLE_LIVE_TRADING"] == "false",
    "live_trading_allowed_false": flags["LIVE_TRADING_ALLOWED"] == "false",
    "kill_switch_enabled": kill_switch_enabled,
    "uses_testnet_base_url": uses_testnet_base,
    "does_not_use_production_base_url": does_not_use_production_base,
    "public_ping_ok": public_ping_ok,
    "public_time_ok": public_time_ok,
    "testnet_public_connectivity_ok": testnet_public_connectivity_ok,
    "signed_endpoint_called_false": True,
    "production_credentials_used_false": True,
    "exchange_order_submission_false": True,
    "approved_for_micro_live_execution_false": True,
    "approved_for_real_live_trading_false": True,
}

blockers = [k for k, v in validation_checks.items() if v is not True]
validation_passed = not blockers

decision = (
    "PHASE_23_TESTNET_CONNECTIVITY_VALIDATION_COMPLETE_READY_FOR_EXCHANGE_ADAPTER_DRY_RUN_VALIDATION_NOT_APPROVED_FOR_EXECUTION"
    if validation_passed else
    "PHASE_23_TESTNET_CONNECTIVITY_VALIDATION_FAILED_REVIEW_REQUIRED_NOT_APPROVED_FOR_EXECUTION"
)

record = {
    "phase": "phase_23_9_testnet_connectivity_validation",
    "generated_at_unix": int(time.time()),
    "git_head": head,
    "git_branch": branch,
    "git_remote_origin": remote,
    "git_working_tree_clean_before_outputs": git_clean,
    "requested_transition": "on_hold_to_micro_trading_validation",
    "current_transition_status": "testnet_connectivity_validation_only_not_approved_for_execution",
    "testnet_connectivity_validation_passed": validation_passed,
    "validation_checks": validation_checks,
    "blockers": blockers,
    "validation_warnings": validation_warnings,
    "safe_flags": flags,
    "safe_flags_active": safe_flags_active,
    "kill_switch_enabled": kill_switch_enabled,
    "testnet_base_url": testnet_base_url,
    "production_base_url_masked": production_base_url,
    "tested_symbol": symbol,
    "public_endpoint_results": connectivity_results,
    "exchange_info_public_result": exchange_info_result,
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
    "next_phase": "Phase 23.10 — Exchange Adapter Dry-Run Validation",
}

write(OUT, record)
write(RUNTIME_OUT, record)
write(VALIDATION_FILE, record)

print(f"Report written to: {OUT}")
print(f"Runtime state written to: {RUNTIME_OUT}")
print(f"Validation file written to: {VALIDATION_FILE}")
print(f"testnet_connectivity_validation_passed={validation_passed}")
print(f"safe_flags_active={safe_flags_active}")
print(f"kill_switch_enabled={kill_switch_enabled}")
print(f"testnet_base_url={testnet_base_url}")
print(f"tested_symbol={symbol}")
print(f"public_ping_ok={public_ping_ok}")
print(f"public_time_ok={public_time_ok}")
print(f"exchange_info_ok={exchange_info_ok}")
print("signed_endpoint_called=False")
print("account_endpoint_called=False")
print("order_endpoint_called=False")
print("production_credentials_used=False")
print("current_transition_status=testnet_connectivity_validation_only_not_approved_for_execution")
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
