import json, os, subprocess, time
from pathlib import Path

OUT = Path("data/processed/phase18_hold_state_weekly_dashboard_review_plan.json")
RUNTIME_OUT = Path("runtime/phase18_hold_state_weekly_dashboard_review_plan_state.json")
PLAN_DIR = Path("data/processed/phase18_hold_monitoring")

DAILY_CHECKLIST = Path("data/processed/phase18_hold_state_daily_checklist.json")
RUNTIME_DAILY_CHECKLIST = Path("runtime/phase18_hold_state_daily_checklist_state.json")
MONITORING_REPORT = Path("data/processed/phase18_hold_state_monitoring_report.json")
HEALTH_CHECK = Path("data/processed/phase18_hold_state_monitoring_health_check.json")
NEXT_ACTION = Path("data/processed/phase18_next_action_selection.json")

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

flags = {
    "BINANCE_TESTNET": os.getenv("BINANCE_TESTNET", ""),
    "BINANCE_USE_TESTNET": os.getenv("BINANCE_USE_TESTNET", ""),
    "BINANCE_ENABLE_LIVE_TRADING": os.getenv("BINANCE_ENABLE_LIVE_TRADING", ""),
    "LIVE_TRADING_ALLOWED": os.getenv("LIVE_TRADING_ALLOWED", ""),
}

safe_mode = flags["BINANCE_ENABLE_LIVE_TRADING"] == "false" and flags["LIVE_TRADING_ALLOWED"] == "false"
git_clean_before_outputs = git_clean()

daily = load_json(DAILY_CHECKLIST)
runtime_daily = load_json(RUNTIME_DAILY_CHECKLIST)
monitoring_report = load_json(MONITORING_REPORT)
health = load_json(HEALTH_CHECK)
next_action = load_json(NEXT_ACTION)

selected_option = (
    daily.get("selected_option")
    or runtime_daily.get("selected_option")
    or monitoring_report.get("selected_option")
    or next_action.get("selected_option")
)

daily_checklist_ready = (
    daily.get("daily_checklist_ready") is True
    or runtime_daily.get("daily_checklist_ready") is True
)

hold_state_report_passed = monitoring_report.get("hold_state_report_passed") is True
core_hold_health_passed = health.get("core_hold_health_passed") is True

paper_shadow_started = any_true(
    daily.get("paper_shadow_started"),
    runtime_daily.get("paper_shadow_started"),
    monitoring_report.get("paper_shadow_started"),
    health.get("paper_shadow_started"),
    next_action.get("paper_shadow_started")
)

approved_for_paper_shadow_start = any_true(
    daily.get("approved_for_paper_shadow_start"),
    runtime_daily.get("approved_for_paper_shadow_start"),
    monitoring_report.get("approved_for_paper_shadow_start"),
    health.get("approved_for_paper_shadow_start"),
    next_action.get("approved_for_paper_shadow_start")
)

exchange_order_submission = any_true(
    daily.get("exchange_order_submission"),
    runtime_daily.get("exchange_order_submission"),
    monitoring_report.get("exchange_order_submission"),
    health.get("exchange_order_submission"),
    next_action.get("exchange_order_submission")
)

approved_for_micro_live_execution = any_true(
    daily.get("approved_for_micro_live_execution"),
    runtime_daily.get("approved_for_micro_live_execution"),
    monitoring_report.get("approved_for_micro_live_execution"),
    health.get("approved_for_micro_live_execution"),
    next_action.get("approved_for_micro_live_execution")
)

approved_for_real_live_trading = any_true(
    daily.get("approved_for_real_live_trading"),
    runtime_daily.get("approved_for_real_live_trading"),
    monitoring_report.get("approved_for_real_live_trading"),
    health.get("approved_for_real_live_trading"),
    next_action.get("approved_for_real_live_trading")
)

dashboard_plan_checks = {
    "safe_mode_active": safe_mode,
    "daily_checklist_present": DAILY_CHECKLIST.exists(),
    "runtime_daily_checklist_present": RUNTIME_DAILY_CHECKLIST.exists(),
    "monitoring_report_present": MONITORING_REPORT.exists(),
    "health_check_present": HEALTH_CHECK.exists(),
    "next_action_present": NEXT_ACTION.exists(),
    "selected_option_is_remain_on_hold": selected_option == "remain_on_hold",
    "daily_checklist_ready": daily_checklist_ready,
    "hold_state_report_passed": hold_state_report_passed,
    "core_hold_health_passed": core_hold_health_passed,
    "paper_shadow_not_started": paper_shadow_started is False,
    "paper_shadow_start_not_approved": approved_for_paper_shadow_start is False,
    "exchange_order_submission_disabled": exchange_order_submission is False,
    "micro_live_not_approved": approved_for_micro_live_execution is False,
    "real_live_not_approved": approved_for_real_live_trading is False,
}

blockers = [k for k, v in dashboard_plan_checks.items() if v is not True]
dashboard_review_plan_ready = all(dashboard_plan_checks.values())

weekly_dashboard_review_plan = {
    "phase": "phase_18_6_hold_state_weekly_dashboard_review_plan_record",
    "created_at_unix": int(time.time()),
    "selected_option": selected_option,
    "review_frequency": "weekly",
    "dashboard_review_mode": "hold_state_observation_only",
    "execution_allowed": False,
    "paper_shadow_execution_allowed": False,
    "exchange_order_submission_allowed": False,
    "real_capital_allowed": False,
    "dashboards_to_review": [
        {
            "name": "Execution & Risk Dashboard",
            "required_hold_state": [
                "risk_decisions_zero_or_expected_baseline",
                "orders_and_fills_no_live_activity",
                "kill_switch_inactive_or_safe",
                "account_equity_no_live_capital"
            ]
        },
        {
            "name": "Market Data Health Dashboard",
            "required_hold_state": [
                "component_up_healthy",
                "ready_healthy",
                "websocket_reconnects_reasonable",
                "order_book_sequence_health_ok",
                "spread_bps_reasonable"
            ]
        },
        {
            "name": "Strategy Health Dashboard",
            "required_hold_state": [
                "signals_generated_no_live_execution",
                "strategy_metrics_observation_only",
                "no_approval_for_paper_shadow_or_live_trading"
            ]
        }
    ],
    "manual_review_items": [
        "Confirm no paper shadow session has started.",
        "Confirm no exchange orders were submitted.",
        "Confirm live trading flags remain disabled.",
        "Confirm dashboards show no unexpected execution activity.",
        "Confirm any No Data panels are expected for hold state.",
        "Confirm GitHub evidence remains committed."
    ],
    "dashboard_plan_checks": dashboard_plan_checks,
    "blockers": blockers,
    "dashboard_review_plan_ready": dashboard_review_plan_ready,
    "paper_shadow_started": False,
    "approved_for_paper_shadow_start": False,
    "exchange_order_submission": False,
    "approved_for_micro_live_execution": False,
    "approved_for_real_live_trading": False,
}

PLAN_DIR.mkdir(parents=True, exist_ok=True)

plan_file = PLAN_DIR / "hold_state_weekly_dashboard_review_plan.json"
write_json(plan_file, weekly_dashboard_review_plan)
write_json(RUNTIME_OUT, weekly_dashboard_review_plan)

if dashboard_review_plan_ready:
    decision = "PHASE_18_HOLD_STATE_WEEKLY_DASHBOARD_REVIEW_PLAN_CREATED_NOT_APPROVED_FOR_EXECUTION"
    next_phase = "Phase 18.7 — Hold State Weekly Dashboard Review Snapshot"
else:
    decision = "PHASE_18_HOLD_STATE_WEEKLY_DASHBOARD_REVIEW_PLAN_BLOCKED_REVIEW_REQUIRED"
    next_phase = "Phase 18.7 — Hold State Dashboard Plan Review"

report = {
    "phase": "phase_18_6_hold_state_weekly_dashboard_review_plan",
    "generated_at_unix": int(time.time()),
    "scope": "hold_state_weekly_dashboard_review_plan_only",
    "selected_option": selected_option,
    "safety_flags": flags,
    "safe_mode_active": safe_mode,
    "git_working_tree_clean": git_clean_before_outputs,
    "dashboard_review_plan_ready": dashboard_review_plan_ready,
    "dashboard_plan_checks": dashboard_plan_checks,
    "blockers": blockers,
    "paper_shadow_started": False,
    "approved_for_paper_shadow_start": False,
    "exchange_order_submission": False,
    "real_capital_allowed": False,
    "live_trading_enabled": False,
    "approved_for_micro_live_execution": False,
    "approved_for_real_live_trading": False,
    "plan_file": str(plan_file),
    "runtime_plan_file": str(RUNTIME_OUT),
    "decision": decision,
    "next_phase": next_phase,
    "safety_notes": [
        "This phase creates a weekly dashboard review plan only.",
        "This phase does not start paper shadow execution.",
        "This phase does not approve micro-live execution.",
        "This phase does not approve real live trading.",
        "This phase does not submit Binance orders.",
        "Dashboard review is observation-only while the system remains on hold."
    ]
}

write_json(OUT, report)

print(f"Report written to: {OUT}")
print(f"Runtime plan written to: {RUNTIME_OUT}")
print(f"Plan written to: {plan_file}")
print(f"safe_mode_active={safe_mode}")
print(f"selected_option={selected_option}")
print(f"dashboard_review_plan_ready={dashboard_review_plan_ready}")
print("paper_shadow_started=False")
print("approved_for_paper_shadow_start=False")
print("exchange_order_submission=False")
print("approved_for_micro_live_execution=False")
print("approved_for_real_live_trading=False")
print(f"decision={decision}")
