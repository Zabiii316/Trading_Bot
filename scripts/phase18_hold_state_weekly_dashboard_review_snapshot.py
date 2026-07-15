import json, os, subprocess, time, urllib.request
from pathlib import Path

OUT = Path("data/processed/phase18_hold_state_weekly_dashboard_review_snapshot.json")
RUNTIME_OUT = Path("runtime/phase18_hold_state_weekly_dashboard_review_snapshot_state.json")
SNAPSHOT_DIR = Path("data/processed/phase18_hold_monitoring")

PLAN_INPUT = Path("data/processed/phase18_hold_state_weekly_dashboard_review_plan.json")
RUNTIME_PLAN = Path("runtime/phase18_hold_state_weekly_dashboard_review_plan_state.json")
DAILY_CHECKLIST = Path("data/processed/phase18_hold_state_daily_checklist.json")
HEALTH_CHECK = Path("data/processed/phase18_hold_state_monitoring_health_check.json")
MONITORING_REPORT = Path("data/processed/phase18_hold_state_monitoring_report.json")
NEXT_ACTION = Path("data/processed/phase18_next_action_selection.json")

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

flags = {
    "BINANCE_TESTNET": os.getenv("BINANCE_TESTNET", ""),
    "BINANCE_USE_TESTNET": os.getenv("BINANCE_USE_TESTNET", ""),
    "BINANCE_ENABLE_LIVE_TRADING": os.getenv("BINANCE_ENABLE_LIVE_TRADING", ""),
    "LIVE_TRADING_ALLOWED": os.getenv("LIVE_TRADING_ALLOWED", ""),
}

safe_mode = flags["BINANCE_ENABLE_LIVE_TRADING"] == "false" and flags["LIVE_TRADING_ALLOWED"] == "false"
git_clean_before_outputs = git_clean()

plan = load_json(PLAN_INPUT)
runtime_plan = load_json(RUNTIME_PLAN)
daily = load_json(DAILY_CHECKLIST)
health = load_json(HEALTH_CHECK)
monitoring_report = load_json(MONITORING_REPORT)
next_action = load_json(NEXT_ACTION)

selected_option = (
    plan.get("selected_option")
    or runtime_plan.get("selected_option")
    or daily.get("selected_option")
    or monitoring_report.get("selected_option")
    or next_action.get("selected_option")
)

dashboard_review_plan_ready = (
    plan.get("dashboard_review_plan_ready") is True
    or runtime_plan.get("dashboard_review_plan_ready") is True
)

daily_checklist_ready = daily.get("daily_checklist_ready") is True
core_hold_health_passed = health.get("core_hold_health_passed") is True
hold_state_report_passed = monitoring_report.get("hold_state_report_passed") is True

paper_shadow_started = any_true(
    plan.get("paper_shadow_started"),
    runtime_plan.get("paper_shadow_started"),
    daily.get("paper_shadow_started"),
    health.get("paper_shadow_started"),
    monitoring_report.get("paper_shadow_started"),
    next_action.get("paper_shadow_started")
)

approved_for_paper_shadow_start = any_true(
    plan.get("approved_for_paper_shadow_start"),
    runtime_plan.get("approved_for_paper_shadow_start"),
    daily.get("approved_for_paper_shadow_start"),
    health.get("approved_for_paper_shadow_start"),
    monitoring_report.get("approved_for_paper_shadow_start"),
    next_action.get("approved_for_paper_shadow_start")
)

exchange_order_submission = any_true(
    plan.get("exchange_order_submission"),
    runtime_plan.get("exchange_order_submission"),
    daily.get("exchange_order_submission"),
    health.get("exchange_order_submission"),
    monitoring_report.get("exchange_order_submission"),
    next_action.get("exchange_order_submission")
)

approved_for_micro_live_execution = any_true(
    plan.get("approved_for_micro_live_execution"),
    runtime_plan.get("approved_for_micro_live_execution"),
    daily.get("approved_for_micro_live_execution"),
    health.get("approved_for_micro_live_execution"),
    monitoring_report.get("approved_for_micro_live_execution"),
    next_action.get("approved_for_micro_live_execution")
)

approved_for_real_live_trading = any_true(
    plan.get("approved_for_real_live_trading"),
    runtime_plan.get("approved_for_real_live_trading"),
    daily.get("approved_for_real_live_trading"),
    health.get("approved_for_real_live_trading"),
    monitoring_report.get("approved_for_real_live_trading"),
    next_action.get("approved_for_real_live_trading")
)

endpoint_results = [http_probe(url) for url in MONITORING_ENDPOINTS]
monitoring_endpoint_available = any(r.get("ok") is True for r in endpoint_results)

snapshot_checks = {
    "safe_mode_active": safe_mode,
    "plan_input_present": PLAN_INPUT.exists(),
    "runtime_plan_present": RUNTIME_PLAN.exists(),
    "daily_checklist_present": DAILY_CHECKLIST.exists(),
    "health_check_present": HEALTH_CHECK.exists(),
    "monitoring_report_present": MONITORING_REPORT.exists(),
    "next_action_present": NEXT_ACTION.exists(),
    "selected_option_is_remain_on_hold": selected_option == "remain_on_hold",
    "dashboard_review_plan_ready": dashboard_review_plan_ready,
    "daily_checklist_ready": daily_checklist_ready,
    "core_hold_health_passed": core_hold_health_passed,
    "hold_state_report_passed": hold_state_report_passed,
    "paper_shadow_not_started": paper_shadow_started is False,
    "paper_shadow_start_not_approved": approved_for_paper_shadow_start is False,
    "exchange_order_submission_disabled": exchange_order_submission is False,
    "micro_live_not_approved": approved_for_micro_live_execution is False,
    "real_live_not_approved": approved_for_real_live_trading is False,
}

blockers = [k for k, v in snapshot_checks.items() if v is not True]
dashboard_snapshot_ready = all(snapshot_checks.values())

dashboard_snapshot_items = [
    {
        "dashboard": "Execution & Risk Dashboard",
        "expected_hold_state": [
            "No live orders",
            "No live fills",
            "No approved micro-live execution",
            "No real capital exposure",
            "Kill switch safe or inactive"
        ],
        "review_status": "manual_visual_review_required",
        "execution_allowed": False
    },
    {
        "dashboard": "Market Data Health Dashboard",
        "expected_hold_state": [
            "Component health visible if monitoring service is running",
            "Ready status visible if monitoring service is running",
            "No execution dependency",
            "Endpoint availability optional during hold state"
        ],
        "review_status": "manual_visual_review_required",
        "execution_allowed": False
    },
    {
        "dashboard": "Strategy Health Dashboard",
        "expected_hold_state": [
            "Strategy metrics observation only",
            "No paper shadow execution",
            "No live signal execution",
            "No exchange order submission"
        ],
        "review_status": "manual_visual_review_required",
        "execution_allowed": False
    }
]

SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)

if dashboard_snapshot_ready and monitoring_endpoint_available:
    decision = "PHASE_18_HOLD_STATE_WEEKLY_DASHBOARD_SNAPSHOT_COMPLETE_ENDPOINTS_AVAILABLE_NOT_APPROVED_FOR_EXECUTION"
    next_phase = "Phase 18.8 — Hold State Weekly Review Summary"
elif dashboard_snapshot_ready:
    decision = "PHASE_18_HOLD_STATE_WEEKLY_DASHBOARD_SNAPSHOT_COMPLETE_ENDPOINTS_OPTIONAL_NOT_AVAILABLE"
    next_phase = "Phase 18.8 — Hold State Weekly Review Summary"
else:
    decision = "PHASE_18_HOLD_STATE_WEEKLY_DASHBOARD_SNAPSHOT_BLOCKED_REVIEW_REQUIRED"
    next_phase = "Phase 18.8 — Hold State Dashboard Snapshot Review"

snapshot_record = {
    "phase": "phase_18_7_hold_state_weekly_dashboard_review_snapshot_record",
    "created_at_unix": int(time.time()),
    "selected_option": selected_option,
    "dashboard_snapshot_ready": dashboard_snapshot_ready,
    "monitoring_endpoint_available": monitoring_endpoint_available,
    "snapshot_checks": snapshot_checks,
    "blockers": blockers,
    "endpoint_results": endpoint_results,
    "dashboard_snapshot_items": dashboard_snapshot_items,
    "paper_shadow_started": False,
    "approved_for_paper_shadow_start": False,
    "exchange_order_submission": False,
    "real_capital_allowed": False,
    "live_trading_enabled": False,
    "approved_for_micro_live_execution": False,
    "approved_for_real_live_trading": False,
    "decision": decision,
    "next_phase": next_phase
}

snapshot_file = SNAPSHOT_DIR / "hold_state_weekly_dashboard_review_snapshot.json"
write_json(snapshot_file, snapshot_record)
write_json(RUNTIME_OUT, snapshot_record)

report = {
    "phase": "phase_18_7_hold_state_weekly_dashboard_review_snapshot",
    "generated_at_unix": int(time.time()),
    "scope": "hold_state_weekly_dashboard_review_snapshot_only",
    "selected_option": selected_option,
    "safety_flags": flags,
    "safe_mode_active": safe_mode,
    "git_working_tree_clean": git_clean_before_outputs,
    "dashboard_snapshot_ready": dashboard_snapshot_ready,
    "monitoring_endpoint_available": monitoring_endpoint_available,
    "snapshot_checks": snapshot_checks,
    "blockers": blockers,
    "endpoint_results": endpoint_results,
    "dashboard_snapshot_items": dashboard_snapshot_items,
    "paper_shadow_started": False,
    "approved_for_paper_shadow_start": False,
    "exchange_order_submission": False,
    "real_capital_allowed": False,
    "live_trading_enabled": False,
    "approved_for_micro_live_execution": False,
    "approved_for_real_live_trading": False,
    "snapshot_file": str(snapshot_file),
    "runtime_snapshot_file": str(RUNTIME_OUT),
    "decision": decision,
    "next_phase": next_phase,
    "safety_notes": [
        "This phase records a weekly dashboard review snapshot only.",
        "This phase does not start paper shadow execution.",
        "This phase does not approve micro-live execution.",
        "This phase does not approve real live trading.",
        "This phase does not submit Binance orders.",
        "Dashboard review remains observation-only while the system is on hold."
    ]
}

write_json(OUT, report)

print(f"Report written to: {OUT}")
print(f"Runtime snapshot written to: {RUNTIME_OUT}")
print(f"Snapshot written to: {snapshot_file}")
print(f"safe_mode_active={safe_mode}")
print(f"selected_option={selected_option}")
print(f"dashboard_snapshot_ready={dashboard_snapshot_ready}")
print(f"monitoring_endpoint_available={monitoring_endpoint_available}")
print("paper_shadow_started=False")
print("approved_for_paper_shadow_start=False")
print("exchange_order_submission=False")
print("approved_for_micro_live_execution=False")
print("approved_for_real_live_trading=False")
print(f"decision={decision}")
