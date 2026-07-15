import json, os, subprocess, time
from pathlib import Path

OUT = Path("data/processed/phase18_hold_state_weekly_review_summary.json")
RUNTIME_OUT = Path("runtime/phase18_hold_state_weekly_review_summary_state.json")
SUMMARY_DIR = Path("data/processed/phase18_hold_monitoring")

SNAPSHOT = Path("data/processed/phase18_hold_state_weekly_dashboard_review_snapshot.json")
RUNTIME_SNAPSHOT = Path("runtime/phase18_hold_state_weekly_dashboard_review_snapshot_state.json")
DASHBOARD_PLAN = Path("data/processed/phase18_hold_state_weekly_dashboard_review_plan.json")
DAILY_CHECKLIST = Path("data/processed/phase18_hold_state_daily_checklist.json")
MONITORING_REPORT = Path("data/processed/phase18_hold_state_monitoring_report.json")
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

snapshot = load_json(SNAPSHOT)
runtime_snapshot = load_json(RUNTIME_SNAPSHOT)
dashboard_plan = load_json(DASHBOARD_PLAN)
daily = load_json(DAILY_CHECKLIST)
monitoring_report = load_json(MONITORING_REPORT)
next_action = load_json(NEXT_ACTION)

selected_option = (
    snapshot.get("selected_option")
    or runtime_snapshot.get("selected_option")
    or dashboard_plan.get("selected_option")
    or daily.get("selected_option")
    or monitoring_report.get("selected_option")
    or next_action.get("selected_option")
)

dashboard_snapshot_ready = (
    snapshot.get("dashboard_snapshot_ready") is True
    or runtime_snapshot.get("dashboard_snapshot_ready") is True
)

dashboard_review_plan_ready = dashboard_plan.get("dashboard_review_plan_ready") is True
daily_checklist_ready = daily.get("daily_checklist_ready") is True
hold_state_report_passed = monitoring_report.get("hold_state_report_passed") is True

paper_shadow_started = any_true(
    snapshot.get("paper_shadow_started"),
    runtime_snapshot.get("paper_shadow_started"),
    dashboard_plan.get("paper_shadow_started"),
    daily.get("paper_shadow_started"),
    monitoring_report.get("paper_shadow_started"),
    next_action.get("paper_shadow_started")
)

approved_for_paper_shadow_start = any_true(
    snapshot.get("approved_for_paper_shadow_start"),
    runtime_snapshot.get("approved_for_paper_shadow_start"),
    dashboard_plan.get("approved_for_paper_shadow_start"),
    daily.get("approved_for_paper_shadow_start"),
    monitoring_report.get("approved_for_paper_shadow_start"),
    next_action.get("approved_for_paper_shadow_start")
)

exchange_order_submission = any_true(
    snapshot.get("exchange_order_submission"),
    runtime_snapshot.get("exchange_order_submission"),
    dashboard_plan.get("exchange_order_submission"),
    daily.get("exchange_order_submission"),
    monitoring_report.get("exchange_order_submission"),
    next_action.get("exchange_order_submission")
)

approved_for_micro_live_execution = any_true(
    snapshot.get("approved_for_micro_live_execution"),
    runtime_snapshot.get("approved_for_micro_live_execution"),
    dashboard_plan.get("approved_for_micro_live_execution"),
    daily.get("approved_for_micro_live_execution"),
    monitoring_report.get("approved_for_micro_live_execution"),
    next_action.get("approved_for_micro_live_execution")
)

approved_for_real_live_trading = any_true(
    snapshot.get("approved_for_real_live_trading"),
    runtime_snapshot.get("approved_for_real_live_trading"),
    dashboard_plan.get("approved_for_real_live_trading"),
    daily.get("approved_for_real_live_trading"),
    monitoring_report.get("approved_for_real_live_trading"),
    next_action.get("approved_for_real_live_trading")
)

summary_checks = {
    "safe_mode_active": safe_mode,
    "snapshot_present": SNAPSHOT.exists(),
    "runtime_snapshot_present": RUNTIME_SNAPSHOT.exists(),
    "dashboard_plan_present": DASHBOARD_PLAN.exists(),
    "daily_checklist_present": DAILY_CHECKLIST.exists(),
    "monitoring_report_present": MONITORING_REPORT.exists(),
    "next_action_present": NEXT_ACTION.exists(),
    "selected_option_is_remain_on_hold": selected_option == "remain_on_hold",
    "dashboard_snapshot_ready": dashboard_snapshot_ready,
    "dashboard_review_plan_ready": dashboard_review_plan_ready,
    "daily_checklist_ready": daily_checklist_ready,
    "hold_state_report_passed": hold_state_report_passed,
    "paper_shadow_not_started": paper_shadow_started is False,
    "paper_shadow_start_not_approved": approved_for_paper_shadow_start is False,
    "exchange_order_submission_disabled": exchange_order_submission is False,
    "micro_live_not_approved": approved_for_micro_live_execution is False,
    "real_live_not_approved": approved_for_real_live_trading is False,
}

blockers = [k for k, v in summary_checks.items() if v is not True]
weekly_summary_passed = all(summary_checks.values())

SUMMARY_DIR.mkdir(parents=True, exist_ok=True)

if weekly_summary_passed:
    decision = "PHASE_18_HOLD_STATE_WEEKLY_REVIEW_SUMMARY_COMPLETE_HOLD_CONFIRMED_NOT_APPROVED_FOR_EXECUTION"
    next_phase = "Phase 18.9 — Hold State Evidence Index"
else:
    decision = "PHASE_18_HOLD_STATE_WEEKLY_REVIEW_SUMMARY_BLOCKED_REVIEW_REQUIRED"
    next_phase = "Phase 18.9 — Hold State Review"

summary_record = {
    "phase": "phase_18_8_hold_state_weekly_review_summary_record",
    "created_at_unix": int(time.time()),
    "selected_option": selected_option,
    "weekly_summary_passed": weekly_summary_passed,
    "summary_checks": summary_checks,
    "blockers": blockers,
    "weekly_review_summary": {
        "system_state": "HOLD",
        "paper_shadow_started": False,
        "paper_shadow_start_approved": False,
        "exchange_order_submission": False,
        "micro_live_approved": False,
        "real_live_trading_approved": False,
        "real_capital_allowed": False,
        "dashboard_review_mode": "observation_only",
        "next_action": "continue_hold_state_monitoring"
    },
    "recommended_actions": [
        "keep_safe_trading_flags_enabled",
        "keep_live_trading_flags_disabled",
        "continue_daily_hold_state_checklist",
        "repeat_weekly_dashboard_review",
        "do_not_start_paper_shadow_without_separate_manual_approval",
        "do_not_enable_exchange_order_submission",
        "do_not_use_real_capital"
    ],
    "decision": decision,
    "next_phase": next_phase
}

summary_file = SUMMARY_DIR / "hold_state_weekly_review_summary.json"
write_json(summary_file, summary_record)
write_json(RUNTIME_OUT, summary_record)

report = {
    "phase": "phase_18_8_hold_state_weekly_review_summary",
    "generated_at_unix": int(time.time()),
    "scope": "hold_state_weekly_review_summary_only",
    "selected_option": selected_option,
    "safety_flags": flags,
    "safe_mode_active": safe_mode,
    "git_working_tree_clean": git_clean_before_outputs,
    "weekly_summary_passed": weekly_summary_passed,
    "summary_checks": summary_checks,
    "blockers": blockers,
    "paper_shadow_started": False,
    "approved_for_paper_shadow_start": False,
    "exchange_order_submission": False,
    "real_capital_allowed": False,
    "live_trading_enabled": False,
    "approved_for_micro_live_execution": False,
    "approved_for_real_live_trading": False,
    "summary_file": str(summary_file),
    "runtime_summary_file": str(RUNTIME_OUT),
    "decision": decision,
    "next_phase": next_phase,
    "safety_notes": [
        "This phase creates a weekly hold-state review summary only.",
        "This phase does not start paper shadow execution.",
        "This phase does not approve micro-live execution.",
        "This phase does not approve real live trading.",
        "This phase does not submit Binance orders.",
        "Real capital and exchange order submission remain disabled."
    ]
}

write_json(OUT, report)

print(f"Report written to: {OUT}")
print(f"Runtime summary written to: {RUNTIME_OUT}")
print(f"Summary written to: {summary_file}")
print(f"safe_mode_active={safe_mode}")
print(f"selected_option={selected_option}")
print(f"weekly_summary_passed={weekly_summary_passed}")
print("paper_shadow_started=False")
print("approved_for_paper_shadow_start=False")
print("exchange_order_submission=False")
print("approved_for_micro_live_execution=False")
print("approved_for_real_live_trading=False")
print(f"decision={decision}")
