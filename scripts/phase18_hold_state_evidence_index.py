import json, os, subprocess, time
from pathlib import Path

OUT = Path("data/processed/phase18_hold_state_evidence_index.json")
RUNTIME_OUT = Path("runtime/phase18_hold_state_evidence_index_state.json")
INDEX_DIR = Path("data/processed/phase18_hold_monitoring")

WEEKLY_SUMMARY = Path("data/processed/phase18_hold_state_weekly_review_summary.json")
RUNTIME_WEEKLY_SUMMARY = Path("runtime/phase18_hold_state_weekly_review_summary_state.json")
DASHBOARD_SNAPSHOT = Path("data/processed/phase18_hold_state_weekly_dashboard_review_snapshot.json")
WEEKLY_PLAN = Path("data/processed/phase18_hold_state_weekly_dashboard_review_plan.json")
DAILY_CHECKLIST = Path("data/processed/phase18_hold_state_daily_checklist.json")
MONITORING_REPORT = Path("data/processed/phase18_hold_state_monitoring_report.json")
HEALTH_CHECK = Path("data/processed/phase18_hold_state_monitoring_health_check.json")
MONITORING_PLAN = Path("data/processed/phase18_hold_state_monitoring_plan.json")
NEXT_ACTION = Path("data/processed/phase18_next_action_selection.json")
PHASE17_CLOSEOUT = Path("data/processed/phase17_safety_closeout_next_action_options.json")

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

weekly_summary = load_json(WEEKLY_SUMMARY)
runtime_weekly_summary = load_json(RUNTIME_WEEKLY_SUMMARY)
dashboard_snapshot = load_json(DASHBOARD_SNAPSHOT)
weekly_plan = load_json(WEEKLY_PLAN)
daily_checklist = load_json(DAILY_CHECKLIST)
monitoring_report = load_json(MONITORING_REPORT)
health_check = load_json(HEALTH_CHECK)
monitoring_plan = load_json(MONITORING_PLAN)
next_action = load_json(NEXT_ACTION)
phase17_closeout = load_json(PHASE17_CLOSEOUT)

selected_option = (
    weekly_summary.get("selected_option")
    or runtime_weekly_summary.get("selected_option")
    or dashboard_snapshot.get("selected_option")
    or weekly_plan.get("selected_option")
    or daily_checklist.get("selected_option")
    or monitoring_report.get("selected_option")
    or monitoring_plan.get("selected_option")
    or next_action.get("selected_option")
)

weekly_summary_passed = (
    weekly_summary.get("weekly_summary_passed") is True
    or runtime_weekly_summary.get("weekly_summary_passed") is True
)

dashboard_snapshot_ready = dashboard_snapshot.get("dashboard_snapshot_ready") is True
dashboard_review_plan_ready = weekly_plan.get("dashboard_review_plan_ready") is True
daily_checklist_ready = daily_checklist.get("daily_checklist_ready") is True
hold_state_report_passed = monitoring_report.get("hold_state_report_passed") is True
core_hold_health_passed = health_check.get("core_hold_health_passed") is True
monitoring_plan_ready = monitoring_plan.get("monitoring_plan_ready") is True
phase17_closed_safely = phase17_closeout.get("phase17_closed_safely") is True

records = [
    WEEKLY_SUMMARY,
    RUNTIME_WEEKLY_SUMMARY,
    DASHBOARD_SNAPSHOT,
    WEEKLY_PLAN,
    DAILY_CHECKLIST,
    MONITORING_REPORT,
    HEALTH_CHECK,
    MONITORING_PLAN,
    NEXT_ACTION,
    PHASE17_CLOSEOUT,
]

paper_shadow_started = any_true(*[load_json(p).get("paper_shadow_started") for p in records])
approved_for_paper_shadow_start = any_true(*[load_json(p).get("approved_for_paper_shadow_start") for p in records])
exchange_order_submission = any_true(*[load_json(p).get("exchange_order_submission") for p in records])
approved_for_micro_live_execution = any_true(*[load_json(p).get("approved_for_micro_live_execution") for p in records])
approved_for_real_live_trading = any_true(*[load_json(p).get("approved_for_real_live_trading") for p in records])

phase18_processed_files = sorted(str(p) for p in Path("data/processed").glob("phase18_*.json"))
phase18_runtime_files = sorted(str(p) for p in Path("runtime").glob("phase18_*.json"))
phase18_hold_monitoring_files = sorted(str(p) for p in Path("data/processed/phase18_hold_monitoring").glob("*.json"))

evidence_index_checks = {
    "safe_mode_active": safe_mode,
    "weekly_summary_present": WEEKLY_SUMMARY.exists(),
    "runtime_weekly_summary_present": RUNTIME_WEEKLY_SUMMARY.exists(),
    "dashboard_snapshot_present": DASHBOARD_SNAPSHOT.exists(),
    "weekly_plan_present": WEEKLY_PLAN.exists(),
    "daily_checklist_present": DAILY_CHECKLIST.exists(),
    "monitoring_report_present": MONITORING_REPORT.exists(),
    "health_check_present": HEALTH_CHECK.exists(),
    "monitoring_plan_present": MONITORING_PLAN.exists(),
    "next_action_present": NEXT_ACTION.exists(),
    "phase17_closeout_present": PHASE17_CLOSEOUT.exists(),
    "selected_option_is_remain_on_hold": selected_option == "remain_on_hold",
    "weekly_summary_passed": weekly_summary_passed,
    "dashboard_snapshot_ready": dashboard_snapshot_ready,
    "dashboard_review_plan_ready": dashboard_review_plan_ready,
    "daily_checklist_ready": daily_checklist_ready,
    "hold_state_report_passed": hold_state_report_passed,
    "core_hold_health_passed": core_hold_health_passed,
    "monitoring_plan_ready": monitoring_plan_ready,
    "phase17_closed_safely": phase17_closed_safely,
    "paper_shadow_not_started": paper_shadow_started is False,
    "paper_shadow_start_not_approved": approved_for_paper_shadow_start is False,
    "exchange_order_submission_disabled": exchange_order_submission is False,
    "micro_live_not_approved": approved_for_micro_live_execution is False,
    "real_live_not_approved": approved_for_real_live_trading is False,
}

blockers = [k for k, v in evidence_index_checks.items() if v is not True]
evidence_index_ready = all(evidence_index_checks.values())

INDEX_DIR.mkdir(parents=True, exist_ok=True)

if evidence_index_ready:
    decision = "PHASE_18_HOLD_STATE_EVIDENCE_INDEX_COMPLETE_HOLD_CONFIRMED_NOT_APPROVED_FOR_EXECUTION"
    next_phase = "Phase 18.10 — Hold State Closeout Report"
else:
    decision = "PHASE_18_HOLD_STATE_EVIDENCE_INDEX_BLOCKED_REVIEW_REQUIRED"
    next_phase = "Phase 18.10 — Hold State Evidence Review"

index_record = {
    "phase": "phase_18_9_hold_state_evidence_index_record",
    "created_at_unix": int(time.time()),
    "selected_option": selected_option,
    "evidence_index_ready": evidence_index_ready,
    "evidence_index_checks": evidence_index_checks,
    "blockers": blockers,
    "evidence_files": {
        "phase18_processed_files": phase18_processed_files,
        "phase18_runtime_files": phase18_runtime_files,
        "phase18_hold_monitoring_files": phase18_hold_monitoring_files,
        "phase17_closeout_file": str(PHASE17_CLOSEOUT),
    },
    "evidence_counts": {
        "phase18_processed_file_count": len(phase18_processed_files),
        "phase18_runtime_file_count": len(phase18_runtime_files),
        "phase18_hold_monitoring_file_count": len(phase18_hold_monitoring_files),
    },
    "status_summary": {
        "system_state": "HOLD",
        "paper_shadow_started": False,
        "approved_for_paper_shadow_start": False,
        "exchange_order_submission": False,
        "real_capital_allowed": False,
        "live_trading_enabled": False,
        "approved_for_micro_live_execution": False,
        "approved_for_real_live_trading": False,
    },
    "decision": decision,
    "next_phase": next_phase,
}

index_file = INDEX_DIR / "hold_state_evidence_index.json"
write_json(index_file, index_record)
write_json(RUNTIME_OUT, index_record)

report = {
    "phase": "phase_18_9_hold_state_evidence_index",
    "generated_at_unix": int(time.time()),
    "scope": "hold_state_evidence_index_only",
    "selected_option": selected_option,
    "safety_flags": flags,
    "safe_mode_active": safe_mode,
    "git_working_tree_clean": git_clean_before_outputs,
    "evidence_index_ready": evidence_index_ready,
    "evidence_index_checks": evidence_index_checks,
    "blockers": blockers,
    "phase18_processed_file_count": len(phase18_processed_files),
    "phase18_runtime_file_count": len(phase18_runtime_files),
    "phase18_hold_monitoring_file_count": len(phase18_hold_monitoring_files),
    "index_file": str(index_file),
    "runtime_index_file": str(RUNTIME_OUT),
    "paper_shadow_started": False,
    "approved_for_paper_shadow_start": False,
    "exchange_order_submission": False,
    "real_capital_allowed": False,
    "live_trading_enabled": False,
    "approved_for_micro_live_execution": False,
    "approved_for_real_live_trading": False,
    "decision": decision,
    "next_phase": next_phase,
    "safety_notes": [
        "This phase creates a hold-state evidence index only.",
        "This phase does not start paper shadow execution.",
        "This phase does not approve micro-live execution.",
        "This phase does not approve real live trading.",
        "This phase does not submit Binance orders.",
        "Real capital and exchange order submission remain disabled."
    ]
}

write_json(OUT, report)

print(f"Report written to: {OUT}")
print(f"Runtime index written to: {RUNTIME_OUT}")
print(f"Index written to: {index_file}")
print(f"safe_mode_active={safe_mode}")
print(f"selected_option={selected_option}")
print(f"evidence_index_ready={evidence_index_ready}")
print("paper_shadow_started=False")
print("approved_for_paper_shadow_start=False")
print("exchange_order_submission=False")
print("approved_for_micro_live_execution=False")
print("approved_for_real_live_trading=False")
print(f"decision={decision}")
