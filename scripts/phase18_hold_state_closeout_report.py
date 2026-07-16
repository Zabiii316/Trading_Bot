import json, os, subprocess, time
from pathlib import Path

OUT = Path("data/processed/phase18_hold_state_closeout_report.json")
RUNTIME_OUT = Path("runtime/phase18_hold_state_closeout_report_state.json")
CLOSEOUT_DIR = Path("data/processed/phase18_hold_monitoring")

EVIDENCE_INDEX = Path("data/processed/phase18_hold_state_evidence_index.json")
RUNTIME_EVIDENCE_INDEX = Path("runtime/phase18_hold_state_evidence_index_state.json")
WEEKLY_SUMMARY = Path("data/processed/phase18_hold_state_weekly_review_summary.json")
DASHBOARD_SNAPSHOT = Path("data/processed/phase18_hold_state_weekly_dashboard_review_snapshot.json")
DAILY_CHECKLIST = Path("data/processed/phase18_hold_state_daily_checklist.json")
MONITORING_REPORT = Path("data/processed/phase18_hold_state_monitoring_report.json")
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

evidence_index = load_json(EVIDENCE_INDEX)
runtime_evidence_index = load_json(RUNTIME_EVIDENCE_INDEX)
weekly_summary = load_json(WEEKLY_SUMMARY)
dashboard_snapshot = load_json(DASHBOARD_SNAPSHOT)
daily_checklist = load_json(DAILY_CHECKLIST)
monitoring_report = load_json(MONITORING_REPORT)
next_action = load_json(NEXT_ACTION)
phase17_closeout = load_json(PHASE17_CLOSEOUT)

records = [
    evidence_index,
    runtime_evidence_index,
    weekly_summary,
    dashboard_snapshot,
    daily_checklist,
    monitoring_report,
    next_action,
    phase17_closeout,
]

selected_option = (
    evidence_index.get("selected_option")
    or runtime_evidence_index.get("selected_option")
    or weekly_summary.get("selected_option")
    or next_action.get("selected_option")
)

evidence_index_ready = (
    evidence_index.get("evidence_index_ready") is True
    or runtime_evidence_index.get("evidence_index_ready") is True
)

weekly_summary_passed = weekly_summary.get("weekly_summary_passed") is True
dashboard_snapshot_ready = dashboard_snapshot.get("dashboard_snapshot_ready") is True
daily_checklist_ready = daily_checklist.get("daily_checklist_ready") is True
hold_state_report_passed = monitoring_report.get("hold_state_report_passed") is True
phase17_closed_safely = phase17_closeout.get("phase17_closed_safely") is True

paper_shadow_started = any_true(*[r.get("paper_shadow_started") for r in records])
approved_for_paper_shadow_start = any_true(*[r.get("approved_for_paper_shadow_start") for r in records])
exchange_order_submission = any_true(*[r.get("exchange_order_submission") for r in records])
approved_for_micro_live_execution = any_true(*[r.get("approved_for_micro_live_execution") for r in records])
approved_for_real_live_trading = any_true(*[r.get("approved_for_real_live_trading") for r in records])

phase18_processed_files = sorted(str(p) for p in Path("data/processed").glob("phase18_*.json"))
phase18_runtime_files = sorted(str(p) for p in Path("runtime").glob("phase18_*.json"))
phase18_hold_monitoring_files = sorted(str(p) for p in Path("data/processed/phase18_hold_monitoring").glob("*.json"))

closeout_checks = {
    "safe_mode_active": safe_mode,
    "evidence_index_present": EVIDENCE_INDEX.exists(),
    "runtime_evidence_index_present": RUNTIME_EVIDENCE_INDEX.exists(),
    "weekly_summary_present": WEEKLY_SUMMARY.exists(),
    "dashboard_snapshot_present": DASHBOARD_SNAPSHOT.exists(),
    "daily_checklist_present": DAILY_CHECKLIST.exists(),
    "monitoring_report_present": MONITORING_REPORT.exists(),
    "next_action_present": NEXT_ACTION.exists(),
    "phase17_closeout_present": PHASE17_CLOSEOUT.exists(),
    "selected_option_is_remain_on_hold": selected_option == "remain_on_hold",
    "evidence_index_ready": evidence_index_ready,
    "weekly_summary_passed": weekly_summary_passed,
    "dashboard_snapshot_ready": dashboard_snapshot_ready,
    "daily_checklist_ready": daily_checklist_ready,
    "hold_state_report_passed": hold_state_report_passed,
    "phase17_closed_safely": phase17_closed_safely,
    "paper_shadow_not_started": paper_shadow_started is False,
    "paper_shadow_start_not_approved": approved_for_paper_shadow_start is False,
    "exchange_order_submission_disabled": exchange_order_submission is False,
    "micro_live_not_approved": approved_for_micro_live_execution is False,
    "real_live_not_approved": approved_for_real_live_trading is False,
}

blockers = [k for k, v in closeout_checks.items() if v is not True]
hold_state_closeout_passed = all(closeout_checks.values())

CLOSEOUT_DIR.mkdir(parents=True, exist_ok=True)

if hold_state_closeout_passed:
    decision = "PHASE_18_HOLD_STATE_CLOSEOUT_COMPLETE_HOLD_CONFIRMED_NOT_APPROVED_FOR_EXECUTION"
    next_phase = "Phase 18.11 — Hold State Continuation Plan"
else:
    decision = "PHASE_18_HOLD_STATE_CLOSEOUT_BLOCKED_REVIEW_REQUIRED"
    next_phase = "Phase 18.11 — Hold State Closeout Review"

closeout_record = {
    "phase": "phase_18_10_hold_state_closeout_report_record",
    "created_at_unix": int(time.time()),
    "selected_option": selected_option,
    "hold_state_closeout_passed": hold_state_closeout_passed,
    "closeout_checks": closeout_checks,
    "blockers": blockers,
    "evidence_counts": {
        "phase18_processed_file_count": len(phase18_processed_files),
        "phase18_runtime_file_count": len(phase18_runtime_files),
        "phase18_hold_monitoring_file_count": len(phase18_hold_monitoring_files)
    },
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
    "next_allowed_actions": [
        "continue_hold_state_monitoring",
        "strategy_rework_only",
        "historical_data_expansion_only",
        "dashboard_review_only"
    ],
    "blocked_actions": [
        "paper_shadow_start",
        "micro_live_execution",
        "real_live_trading",
        "exchange_order_submission",
        "real_capital_usage"
    ],
    "decision": decision,
    "next_phase": next_phase
}

closeout_file = CLOSEOUT_DIR / "hold_state_closeout_report.json"
write_json(closeout_file, closeout_record)
write_json(RUNTIME_OUT, closeout_record)

report = {
    "phase": "phase_18_10_hold_state_closeout_report",
    "generated_at_unix": int(time.time()),
    "scope": "hold_state_closeout_report_only",
    "selected_option": selected_option,
    "safety_flags": flags,
    "safe_mode_active": safe_mode,
    "git_working_tree_clean": git_clean_before_outputs,
    "hold_state_closeout_passed": hold_state_closeout_passed,
    "closeout_checks": closeout_checks,
    "blockers": blockers,
    "phase18_processed_file_count": len(phase18_processed_files),
    "phase18_runtime_file_count": len(phase18_runtime_files),
    "phase18_hold_monitoring_file_count": len(phase18_hold_monitoring_files),
    "paper_shadow_started": False,
    "approved_for_paper_shadow_start": False,
    "exchange_order_submission": False,
    "real_capital_allowed": False,
    "live_trading_enabled": False,
    "approved_for_micro_live_execution": False,
    "approved_for_real_live_trading": False,
    "closeout_file": str(closeout_file),
    "runtime_closeout_file": str(RUNTIME_OUT),
    "decision": decision,
    "next_phase": next_phase,
    "safety_notes": [
        "This phase creates a hold-state closeout report only.",
        "This phase does not start paper shadow execution.",
        "This phase does not approve micro-live execution.",
        "This phase does not approve real live trading.",
        "This phase does not submit Binance orders.",
        "Real capital and exchange order submission remain disabled."
    ]
}

write_json(OUT, report)

print(f"Report written to: {OUT}")
print(f"Runtime closeout written to: {RUNTIME_OUT}")
print(f"Closeout written to: {closeout_file}")
print(f"safe_mode_active={safe_mode}")
print(f"selected_option={selected_option}")
print(f"hold_state_closeout_passed={hold_state_closeout_passed}")
print("paper_shadow_started=False")
print("approved_for_paper_shadow_start=False")
print("exchange_order_submission=False")
print("approved_for_micro_live_execution=False")
print("approved_for_real_live_trading=False")
print(f"decision={decision}")
