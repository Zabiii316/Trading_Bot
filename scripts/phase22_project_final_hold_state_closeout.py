import json, os, subprocess, time
from pathlib import Path

OUT = Path("data/processed/phase22_project_final_hold_state_closeout.json")
RUNTIME_OUT = Path("runtime/phase22_project_final_hold_state_closeout_state.json")
PHASE22_DIR = Path("data/processed/phase22_project_archive")

FINAL_SUMMARY = Path("data/processed/phase22_project_hold_state_final_summary.json")
FINAL_SUMMARY_RUNTIME = Path("runtime/phase22_project_hold_state_final_summary_state.json")
FINAL_SUMMARY_FILE = Path("data/processed/phase22_project_archive/project_hold_state_final_summary.json")

ARCHIVE_CLOSEOUT = Path("data/processed/phase22_project_hold_state_archive_safety_closeout.json")
ARCHIVE_CONSOLIDATION = Path("data/processed/phase22_project_hold_state_archive_consolidation.json")
ARCHIVE_REVIEW = Path("data/processed/phase22_project_hold_state_archive_review.json")
ARCHIVE_INDEX_REPORT = Path("data/processed/phase22_project_hold_state_archive_and_evidence_index.json")
ARCHIVE_MANIFEST = Path("data/processed/phase22_project_archive/project_hold_state_archive_manifest.json")
ARCHIVE_INDEX = Path("data/processed/phase22_project_archive/project_hold_state_evidence_index.json")

PHASE21_FINAL = Path("data/processed/phase21_post_strategy_rework_hold_monitoring_final_safety_closeout.json")
PHASE20_CLOSEOUT = Path("data/processed/phase20_strategy_rework_safety_closeout.json")

def run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True)

def git_clean():
    return run(["git", "status", "--short"]).stdout.strip() == ""

def git_head():
    r = run(["git", "rev-parse", "HEAD"])
    return r.stdout.strip() if r.returncode == 0 else None

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

flags = {
    "BINANCE_TESTNET": os.getenv("BINANCE_TESTNET", ""),
    "BINANCE_USE_TESTNET": os.getenv("BINANCE_USE_TESTNET", ""),
    "BINANCE_ENABLE_LIVE_TRADING": os.getenv("BINANCE_ENABLE_LIVE_TRADING", ""),
    "LIVE_TRADING_ALLOWED": os.getenv("LIVE_TRADING_ALLOWED", ""),
}

safe_mode = (
    flags["BINANCE_ENABLE_LIVE_TRADING"] == "false"
    and flags["LIVE_TRADING_ALLOWED"] == "false"
)

current_git_head = git_head()
git_working_tree_clean = git_clean()

summary = load_json(FINAL_SUMMARY)
summary_runtime = load_json(FINAL_SUMMARY_RUNTIME)
summary_file = load_json(FINAL_SUMMARY_FILE)
archive_closeout = load_json(ARCHIVE_CLOSEOUT)
archive_consolidation = load_json(ARCHIVE_CONSOLIDATION)
archive_review = load_json(ARCHIVE_REVIEW)
archive_index_report = load_json(ARCHIVE_INDEX_REPORT)
archive_manifest = load_json(ARCHIVE_MANIFEST)
archive_index = load_json(ARCHIVE_INDEX)
phase21 = load_json(PHASE21_FINAL)
phase20 = load_json(PHASE20_CLOSEOUT)

final_summary_ready = (
    summary.get("final_summary_ready") is True
    or summary_runtime.get("final_summary_ready") is True
    or summary_file.get("final_summary_ready") is True
)

archive_safety_closeout_passed = archive_closeout.get("archive_safety_closeout_passed") is True
archive_consolidated = archive_consolidation.get("archive_consolidated") is True
archive_review_passed = archive_review.get("archive_review_passed") is True
archive_index_ready = archive_index_report.get("archive_index_ready") is True or archive_index.get("archive_index_ready") is True
phase21_final_passed = phase21.get("final_safety_closeout_passed") is True
phase20_closeout_passed = phase20.get("strategy_rework_safety_closeout_passed") is True

project_status = (
    summary.get("project_status")
    or summary_runtime.get("project_status")
    or summary_file.get("project_status")
)

phase20_status = (
    summary.get("phase20_status")
    or summary_runtime.get("phase20_status")
    or summary_file.get("phase20_status")
    or phase20.get("phase20_status")
)

phase21_status = (
    summary.get("phase21_status")
    or summary_runtime.get("phase21_status")
    or summary_file.get("phase21_status")
    or phase21.get("phase21_status")
)

phase22_status = (
    summary.get("phase22_status")
    or summary_runtime.get("phase22_status")
    or summary_file.get("phase22_status")
)

selected_phase21_next_action = (
    summary.get("selected_phase21_next_action")
    or summary_runtime.get("selected_phase21_next_action")
    or summary_file.get("selected_phase21_next_action")
)

evidence_count = (
    summary.get("evidence_file_count")
    or summary_file.get("evidence_file_count")
    or archive_manifest.get("evidence_file_count", 0)
)

runtime_count = (
    summary.get("runtime_file_count")
    or summary_file.get("runtime_file_count")
    or archive_manifest.get("runtime_file_count", 0)
)

doc_count = (
    summary.get("documentation_file_count")
    or summary_file.get("documentation_file_count")
    or archive_manifest.get("documentation_file_count", 0)
)

closeout_checks = {
    "safe_mode_active": safe_mode,
    "final_summary_present": FINAL_SUMMARY.exists(),
    "final_summary_runtime_present": FINAL_SUMMARY_RUNTIME.exists(),
    "final_summary_file_present": FINAL_SUMMARY_FILE.exists(),
    "archive_closeout_present": ARCHIVE_CLOSEOUT.exists(),
    "archive_consolidation_present": ARCHIVE_CONSOLIDATION.exists(),
    "archive_review_present": ARCHIVE_REVIEW.exists(),
    "archive_index_report_present": ARCHIVE_INDEX_REPORT.exists(),
    "archive_manifest_present": ARCHIVE_MANIFEST.exists(),
    "archive_index_present": ARCHIVE_INDEX.exists(),
    "phase21_final_present": PHASE21_FINAL.exists(),
    "phase20_closeout_present": PHASE20_CLOSEOUT.exists(),
    "final_summary_ready": final_summary_ready,
    "archive_safety_closeout_passed": archive_safety_closeout_passed,
    "archive_consolidated": archive_consolidated,
    "archive_review_passed": archive_review_passed,
    "archive_index_ready": archive_index_ready,
    "phase21_final_safety_closeout_passed": phase21_final_passed,
    "phase20_closeout_passed": phase20_closeout_passed,
    "project_status_remain_on_hold": project_status == "remain_on_hold_not_approved_for_execution",
    "phase20_status_closed_remain_on_hold": phase20_status == "closed_remain_on_hold",
    "phase21_status_closed_final_remain_on_hold": phase21_status == "closed_final_remain_on_hold",
    "phase22_status_final_summary_created": phase22_status == "final_summary_created",
    "selected_phase21_next_action_is_remain_on_hold": selected_phase21_next_action == "remain_on_hold",
    "evidence_files_indexed": evidence_count > 0,
    "runtime_files_indexed": runtime_count > 0,
    "documentation_files_indexed": doc_count > 0,
    "monitoring_not_started": summary.get("monitoring_started") is False,
    "run_dry_run_now_false": summary.get("run_dry_run_now") is False,
    "run_backtest_now_false": summary.get("run_backtest_now") is False,
    "execution_allowed_false": summary.get("execution_allowed") is False,
    "approved_for_execution_false": summary.get("approved_for_execution") is False,
    "approved_for_paper_shadow_false": summary.get("approved_for_paper_shadow") is False,
    "approved_for_live_false": summary.get("approved_for_live") is False,
    "paper_shadow_not_started": summary.get("paper_shadow_started") is False,
    "paper_shadow_start_not_approved": summary.get("approved_for_paper_shadow_start") is False,
    "exchange_order_submission_disabled": summary.get("exchange_order_submission") is False,
    "micro_live_not_approved": summary.get("approved_for_micro_live_execution") is False,
    "real_live_not_approved": summary.get("approved_for_real_live_trading") is False,
}

blockers = [key for key, value in closeout_checks.items() if value is not True]
final_hold_state_closeout_passed = all(closeout_checks.values())

if final_hold_state_closeout_passed:
    decision = "PHASE_22_PROJECT_FINAL_HOLD_STATE_CLOSEOUT_COMPLETE_REMAIN_ON_HOLD_NOT_APPROVED_FOR_EXECUTION"
    next_phase = "Phase 22.7 — Project Final Evidence Seal"
else:
    decision = "PHASE_22_PROJECT_FINAL_HOLD_STATE_CLOSEOUT_FAILED_REVIEW_REQUIRED"
    next_phase = "Phase 22.7 — Project Final Hold State Closeout Fix"

closeout_file = PHASE22_DIR / "project_final_hold_state_closeout.json"

record = {
    "phase": "phase_22_6_project_final_hold_state_closeout_record",
    "created_at_unix": int(time.time()),
    "git_head": current_git_head,
    "system_state": "HOLD_RESEARCH_ONLY",
    "project_status": "remain_on_hold_not_approved_for_execution",
    "phase20_status": phase20_status,
    "phase21_status": phase21_status,
    "phase22_status": "project_final_hold_state_closeout_complete",
    "selected_phase21_next_action": selected_phase21_next_action,
    "final_hold_state_closeout_passed": final_hold_state_closeout_passed,
    "closeout_checks": closeout_checks,
    "blockers": blockers,
    "evidence_file_count": evidence_count,
    "runtime_file_count": runtime_count,
    "documentation_file_count": doc_count,
    "final_hold_state": {
        "system_state": "HOLD_RESEARCH_ONLY",
        "project_status": "remain_on_hold_not_approved_for_execution",
        "phase20_status": phase20_status,
        "phase21_status": phase21_status,
        "phase22_status": "project_final_hold_state_closeout_complete",
        "selected_phase21_next_action": selected_phase21_next_action,
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
        "approved_for_real_live_trading": False
    },
    "blocked_actions": [
        "monitoring_job_execution",
        "offline_runner_dry_run_execution",
        "backtest_execution",
        "paper_shadow_start",
        "micro_live_execution",
        "real_live_trading",
        "exchange_order_submission",
        "real_capital_usage",
        "production_api_key_usage"
    ],
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
    "decision": decision,
    "next_phase": next_phase,
}

report = {
    "phase": "phase_22_6_project_final_hold_state_closeout",
    "generated_at_unix": int(time.time()),
    "scope": "final_hold_state_closeout_only_no_monitoring_no_dry_run_no_backtest_no_execution",
    "git_head": current_git_head,
    "safety_flags": flags,
    "safe_mode_active": safe_mode,
    "git_working_tree_clean": git_working_tree_clean,
    "project_status": "remain_on_hold_not_approved_for_execution",
    "phase20_status": phase20_status,
    "phase21_status": phase21_status,
    "phase22_status": "project_final_hold_state_closeout_complete",
    "selected_phase21_next_action": selected_phase21_next_action,
    "final_hold_state_closeout_passed": final_hold_state_closeout_passed,
    "evidence_file_count": evidence_count,
    "runtime_file_count": runtime_count,
    "documentation_file_count": doc_count,
    "closeout_checks": closeout_checks,
    "blockers": blockers,
    "closeout_file": str(closeout_file),
    "runtime_closeout_file": str(RUNTIME_OUT),
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
    "decision": decision,
    "next_phase": next_phase,
}

write_json(closeout_file, record)
write_json(RUNTIME_OUT, record)
write_json(OUT, report)

print(f"Report written to: {OUT}")
print(f"Runtime closeout written to: {RUNTIME_OUT}")
print(f"Closeout file written to: {closeout_file}")
print(f"safe_mode_active={safe_mode}")
print(f"final_hold_state_closeout_passed={final_hold_state_closeout_passed}")
print("project_status=remain_on_hold_not_approved_for_execution")
print(f"phase20_status={phase20_status}")
print(f"phase21_status={phase21_status}")
print("phase22_status=project_final_hold_state_closeout_complete")
print(f"selected_phase21_next_action={selected_phase21_next_action}")
print(f"evidence_file_count={evidence_count}")
print(f"runtime_file_count={runtime_count}")
print(f"documentation_file_count={doc_count}")
print("monitoring_started=False")
print("run_dry_run_now=False")
print("run_backtest_now=False")
print("execution_allowed=False")
print("approved_for_execution=False")
print("approved_for_paper_shadow=False")
print("approved_for_live=False")
print("paper_shadow_started=False")
print("approved_for_paper_shadow_start=False")
print("exchange_order_submission=False")
print("approved_for_micro_live_execution=False")
print("approved_for_real_live_trading=False")
print(f"decision={decision}")
