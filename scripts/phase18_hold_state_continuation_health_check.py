import json, os, subprocess, time, urllib.request
from pathlib import Path

OUT = Path("data/processed/phase18_hold_state_continuation_health_check.json")
RUNTIME_OUT = Path("runtime/phase18_hold_state_continuation_health_check_state.json")
HEALTH_DIR = Path("data/processed/phase18_hold_monitoring")

CONTINUATION_PLAN = Path("data/processed/phase18_hold_state_continuation_plan.json")
RUNTIME_CONTINUATION_PLAN = Path("runtime/phase18_hold_state_continuation_plan_state.json")
CLOSEOUT = Path("data/processed/phase18_hold_state_closeout_report.json")
EVIDENCE_INDEX = Path("data/processed/phase18_hold_state_evidence_index.json")
WEEKLY_SUMMARY = Path("data/processed/phase18_hold_state_weekly_review_summary.json")
NEXT_ACTION = Path("data/processed/phase18_next_action_selection.json")
PHASE17_CLOSEOUT = Path("data/processed/phase17_safety_closeout_next_action_options.json")

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

def any_true(*values):
    return any(v is True for v in values)

def probe(url):
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

flags = {
    "BINANCE_TESTNET": os.getenv("BINANCE_TESTNET", ""),
    "BINANCE_USE_TESTNET": os.getenv("BINANCE_USE_TESTNET", ""),
    "BINANCE_ENABLE_LIVE_TRADING": os.getenv("BINANCE_ENABLE_LIVE_TRADING", ""),
    "LIVE_TRADING_ALLOWED": os.getenv("LIVE_TRADING_ALLOWED", ""),
}

safe_mode = flags["BINANCE_ENABLE_LIVE_TRADING"] == "false" and flags["LIVE_TRADING_ALLOWED"] == "false"
git_clean_before_outputs = git_clean()

continuation = load_json(CONTINUATION_PLAN)
runtime_continuation = load_json(RUNTIME_CONTINUATION_PLAN)
closeout = load_json(CLOSEOUT)
evidence_index = load_json(EVIDENCE_INDEX)
weekly_summary = load_json(WEEKLY_SUMMARY)
next_action = load_json(NEXT_ACTION)
phase17_closeout = load_json(PHASE17_CLOSEOUT)

records = [
    continuation,
    runtime_continuation,
    closeout,
    evidence_index,
    weekly_summary,
    next_action,
    phase17_closeout,
]

selected_option = (
    continuation.get("selected_option")
    or runtime_continuation.get("selected_option")
    or closeout.get("selected_option")
    or evidence_index.get("selected_option")
    or weekly_summary.get("selected_option")
    or next_action.get("selected_option")
)

continuation_plan_ready = (
    continuation.get("continuation_plan_ready") is True
    or runtime_continuation.get("continuation_plan_ready") is True
)

hold_state_closeout_passed = closeout.get("hold_state_closeout_passed") is True
evidence_index_ready = evidence_index.get("evidence_index_ready") is True
weekly_summary_passed = weekly_summary.get("weekly_summary_passed") is True
phase17_closed_safely = phase17_closeout.get("phase17_closed_safely") is True

paper_shadow_started = any_true(*[r.get("paper_shadow_started") for r in records])
approved_for_paper_shadow_start = any_true(*[r.get("approved_for_paper_shadow_start") for r in records])
exchange_order_submission = any_true(*[r.get("exchange_order_submission") for r in records])
real_capital_allowed = any_true(*[r.get("real_capital_allowed") for r in records])
live_trading_enabled = any_true(*[r.get("live_trading_enabled") for r in records])
approved_for_micro_live_execution = any_true(*[r.get("approved_for_micro_live_execution") for r in records])
approved_for_real_live_trading = any_true(*[r.get("approved_for_real_live_trading") for r in records])

endpoint_results = [probe(url) for url in MONITORING_ENDPOINTS]
monitoring_endpoint_available = any(r.get("ok") is True for r in endpoint_results)

health_checks = {
    "safe_mode_active": safe_mode,
    "continuation_plan_present": CONTINUATION_PLAN.exists(),
    "runtime_continuation_plan_present": RUNTIME_CONTINUATION_PLAN.exists(),
    "closeout_present": CLOSEOUT.exists(),
    "evidence_index_present": EVIDENCE_INDEX.exists(),
    "weekly_summary_present": WEEKLY_SUMMARY.exists(),
    "next_action_present": NEXT_ACTION.exists(),
    "phase17_closeout_present": PHASE17_CLOSEOUT.exists(),
    "selected_option_is_remain_on_hold": selected_option == "remain_on_hold",
    "continuation_plan_ready": continuation_plan_ready,
    "hold_state_closeout_passed": hold_state_closeout_passed,
    "evidence_index_ready": evidence_index_ready,
    "weekly_summary_passed": weekly_summary_passed,
    "phase17_closed_safely": phase17_closed_safely,
    "paper_shadow_not_started": paper_shadow_started is False,
    "paper_shadow_start_not_approved": approved_for_paper_shadow_start is False,
    "exchange_order_submission_disabled": exchange_order_submission is False,
    "real_capital_disabled": real_capital_allowed is False,
    "live_trading_disabled": live_trading_enabled is False,
    "micro_live_not_approved": approved_for_micro_live_execution is False,
    "real_live_not_approved": approved_for_real_live_trading is False,
}

blockers = [k for k, v in health_checks.items() if v is not True]
continuation_health_passed = all(health_checks.values())

HEALTH_DIR.mkdir(parents=True, exist_ok=True)

if continuation_health_passed and monitoring_endpoint_available:
    decision = "PHASE_18_HOLD_STATE_CONTINUATION_HEALTH_CHECK_COMPLETE_ENDPOINTS_AVAILABLE_NOT_APPROVED_FOR_EXECUTION"
    next_phase = "Phase 18.13 — Hold State Continuation Evidence Snapshot"
elif continuation_health_passed:
    decision = "PHASE_18_HOLD_STATE_CONTINUATION_HEALTH_CHECK_COMPLETE_ENDPOINTS_OPTIONAL_NOT_AVAILABLE"
    next_phase = "Phase 18.13 — Hold State Continuation Evidence Snapshot"
else:
    decision = "PHASE_18_HOLD_STATE_CONTINUATION_HEALTH_CHECK_BLOCKED_REVIEW_REQUIRED"
    next_phase = "Phase 18.13 — Hold State Continuation Review"

health_record = {
    "phase": "phase_18_12_hold_state_continuation_health_check_record",
    "created_at_unix": int(time.time()),
    "selected_option": selected_option,
    "continuation_health_passed": continuation_health_passed,
    "monitoring_endpoint_available": monitoring_endpoint_available,
    "health_checks": health_checks,
    "blockers": blockers,
    "endpoint_results": endpoint_results,
    "status_summary": {
        "system_state": "HOLD",
        "paper_shadow_started": False,
        "approved_for_paper_shadow_start": False,
        "exchange_order_submission": False,
        "real_capital_allowed": False,
        "live_trading_enabled": False,
        "approved_for_micro_live_execution": False,
        "approved_for_real_live_trading": False
    },
    "decision": decision,
    "next_phase": next_phase
}

health_file = HEALTH_DIR / "hold_state_continuation_health_check.json"
write_json(health_file, health_record)
write_json(RUNTIME_OUT, health_record)

report = {
    "phase": "phase_18_12_hold_state_continuation_health_check",
    "generated_at_unix": int(time.time()),
    "scope": "hold_state_continuation_health_check_only",
    "selected_option": selected_option,
    "safety_flags": flags,
    "safe_mode_active": safe_mode,
    "git_working_tree_clean": git_clean_before_outputs,
    "continuation_health_passed": continuation_health_passed,
    "monitoring_endpoint_available": monitoring_endpoint_available,
    "health_checks": health_checks,
    "blockers": blockers,
    "endpoint_results": endpoint_results,
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
        "This phase performs a hold-state continuation health check only.",
        "This phase does not start paper shadow execution.",
        "This phase does not approve micro-live execution.",
        "This phase does not approve real live trading.",
        "This phase does not submit Binance orders.",
        "Monitoring endpoints are optional for hold-state confirmation."
    ]
}

write_json(OUT, report)

print(f"Report written to: {OUT}")
print(f"Runtime health written to: {RUNTIME_OUT}")
print(f"Health file written to: {health_file}")
print(f"safe_mode_active={safe_mode}")
print(f"selected_option={selected_option}")
print(f"continuation_health_passed={continuation_health_passed}")
print(f"monitoring_endpoint_available={monitoring_endpoint_available}")
print("paper_shadow_started=False")
print("approved_for_paper_shadow_start=False")
print("exchange_order_submission=False")
print("approved_for_micro_live_execution=False")
print("approved_for_real_live_trading=False")
print(f"decision={decision}")
