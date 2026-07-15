import json, os, subprocess, time, urllib.request
from pathlib import Path

OUT = Path("data/processed/phase18_hold_state_monitoring_health_check.json")
RUNTIME_OUT = Path("runtime/phase18_hold_state_monitoring_health_check_state.json")
HEALTH_DIR = Path("data/processed/phase18_hold_monitoring")

PLAN_INPUT = Path("data/processed/phase18_hold_state_monitoring_plan.json")
RUNTIME_PLAN = Path("runtime/phase18_hold_state_monitoring_plan_state.json")
NEXT_ACTION = Path("data/processed/phase18_next_action_selection.json")
RUNTIME_NEXT_ACTION = Path("runtime/phase18_next_action_selection_state.json")
PHASE17_CLOSEOUT = Path("data/processed/phase17_safety_closeout_next_action_options.json")
PHASE17_HOLD_STATE = Path("runtime/phase17_paper_shadow_hold_state.json")

MONITORING_ENDPOINTS = [
    "http://127.0.0.1:8081/health/live",
    "http://127.0.0.1:8081/health/ready",
    "http://127.0.0.1:8081/health",
    "http://127.0.0.1:8081/metrics"
]

def run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True)

def git_clean():
    return run(["git", "status", "--short"]).stdout.strip() == ""

def load_json(path):
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except Exception:
        return {}

def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2))

def http_probe(url):
    try:
        with urllib.request.urlopen(url, timeout=2) as response:
            body = response.read(300).decode("utf-8", errors="ignore")
            return {
                "url": url,
                "ok": 200 <= response.status < 300,
                "status_code": response.status,
                "body_sample": body
            }
    except Exception as e:
        return {
            "url": url,
            "ok": False,
            "error": f"{type(e).__name__}: {e}"
        }

def any_true(*values):
    return any(v is True for v in values)

flags = {
    "BINANCE_TESTNET": os.getenv("BINANCE_TESTNET", ""),
    "BINANCE_USE_TESTNET": os.getenv("BINANCE_USE_TESTNET", ""),
    "BINANCE_ENABLE_LIVE_TRADING": os.getenv("BINANCE_ENABLE_LIVE_TRADING", ""),
    "LIVE_TRADING_ALLOWED": os.getenv("LIVE_TRADING_ALLOWED", ""),
}

safe_mode = flags["BINANCE_ENABLE_LIVE_TRADING"] == "false" and flags["LIVE_TRADING_ALLOWED"] == "false"

plan = load_json(PLAN_INPUT)
runtime_plan = load_json(RUNTIME_PLAN)
next_action = load_json(NEXT_ACTION)
runtime_next_action = load_json(RUNTIME_NEXT_ACTION)
phase17_closeout = load_json(PHASE17_CLOSEOUT)
phase17_hold = load_json(PHASE17_HOLD_STATE)

selected_option = (
    plan.get("selected_option")
    or runtime_plan.get("selected_option")
    or next_action.get("selected_option")
    or runtime_next_action.get("selected_option")
)

monitoring_plan_ready = (
    plan.get("monitoring_plan_ready") is True
    or runtime_plan.get("monitoring_plan_ready") is True
)

paper_shadow_started = any_true(
    plan.get("paper_shadow_started"),
    runtime_plan.get("paper_shadow_started"),
    next_action.get("paper_shadow_started"),
    runtime_next_action.get("paper_shadow_started"),
    phase17_closeout.get("paper_shadow_started"),
    phase17_hold.get("paper_shadow_started")
)

approved_for_paper_shadow_start = any_true(
    plan.get("approved_for_paper_shadow_start"),
    runtime_plan.get("approved_for_paper_shadow_start"),
    next_action.get("approved_for_paper_shadow_start"),
    runtime_next_action.get("approved_for_paper_shadow_start"),
    phase17_closeout.get("approved_for_paper_shadow_start"),
    phase17_hold.get("approved_for_paper_shadow_start")
)

exchange_order_submission = any_true(
    plan.get("exchange_order_submission"),
    runtime_plan.get("exchange_order_submission"),
    next_action.get("exchange_order_submission"),
    runtime_next_action.get("exchange_order_submission"),
    phase17_closeout.get("exchange_order_submission"),
    phase17_hold.get("exchange_order_submission")
)

approved_for_micro_live_execution = any_true(
    plan.get("approved_for_micro_live_execution"),
    runtime_plan.get("approved_for_micro_live_execution"),
    next_action.get("approved_for_micro_live_execution"),
    runtime_next_action.get("approved_for_micro_live_execution"),
    phase17_closeout.get("approved_for_micro_live_execution"),
    phase17_hold.get("approved_for_micro_live_execution")
)

approved_for_real_live_trading = any_true(
    plan.get("approved_for_real_live_trading"),
    runtime_plan.get("approved_for_real_live_trading"),
    next_action.get("approved_for_real_live_trading"),
    runtime_next_action.get("approved_for_real_live_trading"),
    phase17_closeout.get("approved_for_real_live_trading"),
    phase17_hold.get("approved_for_real_live_trading")
)

monitoring_endpoint_results = [http_probe(url) for url in MONITORING_ENDPOINTS]
monitoring_endpoint_available = any(r.get("ok") is True for r in monitoring_endpoint_results)

core_health_checks = {
    "safe_mode_active": safe_mode,
    "plan_input_present": PLAN_INPUT.exists(),
    "runtime_plan_present": RUNTIME_PLAN.exists(),
    "next_action_present": NEXT_ACTION.exists(),
    "runtime_next_action_present": RUNTIME_NEXT_ACTION.exists(),
    "phase17_closeout_present": PHASE17_CLOSEOUT.exists(),
    "phase17_hold_state_present": PHASE17_HOLD_STATE.exists(),
    "selected_option_is_remain_on_hold": selected_option == "remain_on_hold",
    "monitoring_plan_ready": monitoring_plan_ready,
    "paper_shadow_not_started": paper_shadow_started is False,
    "paper_shadow_start_not_approved": approved_for_paper_shadow_start is False,
    "exchange_order_submission_disabled": exchange_order_submission is False,
    "micro_live_not_approved": approved_for_micro_live_execution is False,
    "real_live_not_approved": approved_for_real_live_trading is False,
}

blockers = [k for k, v in core_health_checks.items() if v is not True]
core_hold_health_passed = all(core_health_checks.values())

HEALTH_DIR.mkdir(parents=True, exist_ok=True)

if core_hold_health_passed and monitoring_endpoint_available:
    decision = "PHASE_18_HOLD_STATE_MONITORING_HEALTH_CHECK_COMPLETE_CORE_HEALTHY_ENDPOINTS_AVAILABLE_NOT_APPROVED_FOR_EXECUTION"
    next_phase = "Phase 18.4 — Hold State Monitoring Report"
elif core_hold_health_passed:
    decision = "PHASE_18_HOLD_STATE_MONITORING_HEALTH_CHECK_COMPLETE_CORE_HEALTHY_ENDPOINTS_OPTIONAL_NOT_AVAILABLE"
    next_phase = "Phase 18.4 — Hold State Monitoring Report"
else:
    decision = "PHASE_18_HOLD_STATE_MONITORING_HEALTH_CHECK_FAILED_REVIEW_REQUIRED"
    next_phase = "Phase 18.4 — Hold State Monitoring Review"

health_record = {
    "phase": "phase_18_3_hold_state_monitoring_health_check_record",
    "created_at_unix": int(time.time()),
    "selected_option": selected_option,
    "core_hold_health_passed": core_hold_health_passed,
    "monitoring_endpoint_available": monitoring_endpoint_available,
    "core_health_checks": core_health_checks,
    "blockers": blockers,
    "monitoring_endpoint_results": monitoring_endpoint_results,
    "paper_shadow_started": False,
    "approved_for_paper_shadow_start": False,
    "exchange_order_submission": False,
    "approved_for_micro_live_execution": False,
    "approved_for_real_live_trading": False,
    "decision": decision
}

health_file = HEALTH_DIR / "hold_state_monitoring_health_check.json"
write_json(health_file, health_record)
write_json(RUNTIME_OUT, health_record)

report = {
    "phase": "phase_18_3_hold_state_monitoring_health_check",
    "generated_at_unix": int(time.time()),
    "scope": "hold_state_monitoring_health_check_only",
    "selected_option": selected_option,
    "safety_flags": flags,
    "safe_mode_active": safe_mode,
    "git_working_tree_clean": git_clean(),
    "core_hold_health_passed": core_hold_health_passed,
    "monitoring_endpoint_available": monitoring_endpoint_available,
    "core_health_checks": core_health_checks,
    "blockers": blockers,
    "monitoring_endpoint_results": monitoring_endpoint_results,
    "paper_shadow_started": False,
    "approved_for_paper_shadow_start": False,
    "exchange_order_submission": False,
    "real_capital_allowed": False,
    "live_trading_enabled": False,
    "approved_for_micro_live_execution": False,
    "approved_for_real_live_trading": False,
    "health_file": str(health_file),
    "runtime_health_file": str(RUNTIME_OUT),
    "decision": decision,
    "next_phase": next_phase,
    "safety_notes": [
        "This phase performs a hold-state monitoring health check only.",
        "This phase does not start paper shadow execution.",
        "This phase does not approve micro-live execution.",
        "This phase does not approve real live trading.",
        "This phase does not submit Binance orders.",
        "Monitoring endpoints are useful but optional for core hold-state confirmation."
    ]
}

write_json(OUT, report)

print(f"Report written to: {OUT}")
print(f"Runtime health written to: {RUNTIME_OUT}")
print(f"Health record written to: {health_file}")
print(f"safe_mode_active={safe_mode}")
print(f"selected_option={selected_option}")
print(f"core_hold_health_passed={core_hold_health_passed}")
print(f"monitoring_endpoint_available={monitoring_endpoint_available}")
print("paper_shadow_started=False")
print("approved_for_paper_shadow_start=False")
print("exchange_order_submission=False")
print("approved_for_micro_live_execution=False")
print("approved_for_real_live_trading=False")
print(f"decision={decision}")
