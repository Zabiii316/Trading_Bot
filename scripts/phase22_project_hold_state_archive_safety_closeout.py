import json, os, subprocess, time
from pathlib import Path

OUT = Path("data/processed/phase22_project_hold_state_archive_safety_closeout.json")
RUNTIME_OUT = Path("runtime/phase22_project_hold_state_archive_safety_closeout_state.json")
PHASE22_DIR = Path("data/processed/phase22_project_archive")

CONSOLIDATION = Path("data/processed/phase22_project_hold_state_archive_consolidation.json")
CONSOLIDATION_RUNTIME = Path("runtime/phase22_project_hold_state_archive_consolidation_state.json")
CONSOLIDATION_FILE = Path("data/processed/phase22_project_archive/project_hold_state_archive_consolidation.json")

REVIEW = Path("data/processed/phase22_project_hold_state_archive_review.json")
ARCHIVE_REPORT = Path("data/processed/phase22_project_hold_state_archive_and_evidence_index.json")
MANIFEST = Path("data/processed/phase22_project_archive/project_hold_state_archive_manifest.json")
INDEX = Path("data/processed/phase22_project_archive/project_hold_state_evidence_index.json")
PHASE21_FINAL = Path("data/processed/phase21_post_strategy_rework_hold_monitoring_final_safety_closeout.json")

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

safe_mode = flags["BINANCE_ENABLE_LIVE_TRADING"] == "false" and flags["LIVE_TRADING_ALLOWED"] == "false"
current_git_head = git_head()
git_working_tree_clean = git_clean()

consolidation = load_json(CONSOLIDATION)
consolidation_runtime = load_json(CONSOLIDATION_RUNTIME)
consolidation_file_data = load_json(CONSOLIDATION_FILE)
review = load_json(REVIEW)
archive_report = load_json(ARCHIVE_REPORT)
manifest = load_json(MANIFEST)
index = load_json(INDEX)
phase21 = load_json(PHASE21_FINAL)

archive_consolidated = (
    consolidation.get("archive_consolidated") is True
    or consolidation_runtime.get("archive_consolidated") is True
    or consolidation_file_data.get("archive_consolidated") is True
)

archive_review_passed = review.get("archive_review_passed") is True
archive_index_ready = (
    archive_report.get("archive_index_ready") is True
    or index.get("archive_index_ready") is True
)

phase20_status = (
    consolidation.get("phase20_status")
    or consolidation_runtime.get("phase20_status")
    or consolidation_file_data.get("phase20_status")
    or review.get("phase20_status")
    or archive_report.get("phase20_status")
)

phase21_status = (
    consolidation.get("phase21_status")
    or consolidation_runtime.get("phase21_status")
    or consolidation_file_data.get("phase21_status")
    or review.get("phase21_status")
    or archive_report.get("phase21_status")
)

selected_phase21_next_action = (
    consolidation.get("selected_phase21_next_action")
    or consolidation_runtime.get("selected_phase21_next_action")
    or consolidation_file_data.get("selected_phase21_next_action")
    or review.get("selected_phase21_next_action")
    or archive_report.get("selected_phase21_next_action")
)

evidence_count = (
    consolidation.get("evidence_file_count")
    or review.get("evidence_file_count")
    or archive_report.get("evidence_file_count")
    or manifest.get("evidence_file_count", 0)
)

runtime_count = (
    consolidation.get("runtime_file_count")
    or review.get("runtime_file_count")
    or archive_report.get("runtime_file_count")
    or manifest.get("runtime_file_count", 0)
)

doc_count = (
    consolidation.get("documentation_file_count")
    or review.get("documentation_file_count")
    or archive_report.get("documentation_file_count")
    or manifest.get("documentation_file_count", 0)
)

closeout_checks = {
    "safe_mode_active": safe_mode,
    "consolidation_present": CONSOLIDATION.exists(),
    "consolidation_runtime_present": CONSOLIDATION_RUNTIME.exists(),
    "consolidation_file_present": CONSOLIDATION_FILE.exists(),
    "review_present": REVIEW.exists(),
    "archive_report_present": ARCHIVE_REPORT.exists(),
    "manifest_present": MANIFEST.exists(),
    "index_present": INDEX.exists(),
    "phase21_final_present": PHASE21_FINAL.exists(),
    "archive_consolidated": archive_consolidated,
    "archive_review_passed": archive_review_passed,
    "archive_index_ready": archive_index_ready,
    "phase20_status_closed_remain_on_hold": phase20_status == "closed_remain_on_hold",
    "phase21_status_closed_final_remain_on_hold": phase21_status == "closed_final_remain_on_hold",
    "selected_phase21_next_action_is_remain_on_hold": selected_phase21_next_action == "remain_on_hold",
    "evidence_files_indexed": evidence_count > 0,
    "runtime_files_indexed": runtime_count > 0,
    "documentation_files_indexed": doc_count > 0,
    "monitoring_not_started": consolidation.get("monitoring_started") is False,
    "run_dry_run_now_false": consolidation.get("run_dry_run_now") is False,
    "run_backtest_now_false": consolidation.get("run_backtest_now") is False,
    "execution_allowed_false": consolidation.get("execution_allowed") is False,
    "approved_for_execution_false": consolidation.get("approved_for_execution") is False,
    "approved_for_paper_shadow_false": consolidation.get("approved_for_paper_shadow") is False,
    "approved_for_live_false": consolidation.get("approved_for_live") is False,
    "paper_shadow_not_started": consolidation.get("paper_shadow_started") is False,
    "paper_shadow_start_not_approved": consolidation.get("approved_for_paper_shadow_start") is False,
    "exchange_order_submission_disabled": consolidation.get("exchange_order_submission") is False,
    "micro_live_not_approved": consolidation.get("approved_for_micro_live_execution") is False,
    "real_live_not_approved": consolidation.get("approved_for_real_live_trading") is False,
}

blockers = [key for key, value in closeout_checks.items() if value is not True]
archive_safety_closeout_passed = all(closeout_checks.values())

if archive_safety_closeout_passed:
    decision = "PHASE_22_PROJECT_HOLD_STATE_ARCHIVE_SAFETY_CLOSEOUT_COMPLETE_REMAIN_ON_HOLD_NOT_APPROVED_FOR_EXECUTION"
    next_phase = "Phase 22.5 — Project Hold State Final Summary"
else:
    decision = "PHASE_22_PROJECT_HOLD_STATE_ARCHIVE_SAFETY_CLOSEOUT_FAILED_REVIEW_REQUIRED"
    next_phase = "Phase 22.5 — Project Archive Safety Closeout Fix"

closeout_file = PHASE22_DIR / "project_hold_state_archive_safety_closeout.json"

record = {
    "phase": "phase_22_4_project_hold_state_archive_safety_closeout_record",
    "created_at_unix": int(time.time()),
    "git_head": current_git_head,
    "system_state": "HOLD_RESEARCH_ONLY",
    "phase20_status": phase20_status,
    "phase21_status": phase21_status,
    "phase22_status": "archive_safety_closeout_complete",
    "selected_phase21_next_action": selected_phase21_next_action,
    "archive_safety_closeout_passed": archive_safety_closeout_passed,
    "closeout_checks": closeout_checks,
    "blockers": blockers,
    "evidence_file_count": evidence_count,
    "runtime_file_count": runtime_count,
    "documentation_file_count": doc_count,
    "final_archive_state": {
        "archive_state": "closed_index_only",
        "system_state": "HOLD_RESEARCH_ONLY",
        "phase20_status": phase20_status,
        "phase21_status": phase21_status,
        "phase22_status": "archive_safety_closeout_complete",
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
    "allowed_next_actions": [
        "project_hold_state_final_summary",
        "documentation_only",
        "manual_approval_review_only"
    ],
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
    "next_phase": next_phase
}

report = {
    "phase": "phase_22_4_project_hold_state_archive_safety_closeout",
    "generated_at_unix": int(time.time()),
    "scope": "archive_safety_closeout_only_no_monitoring_no_dry_run_no_backtest_no_execution",
    "git_head": current_git_head,
    "safety_flags": flags,
    "safe_mode_active": safe_mode,
    "git_working_tree_clean": git_working_tree_clean,
    "phase20_status": phase20_status,
    "phase21_status": phase21_status,
    "phase22_status": "archive_safety_closeout_complete",
    "selected_phase21_next_action": selected_phase21_next_action,
    "archive_safety_closeout_passed": archive_safety_closeout_passed,
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
    "next_phase": next_phase
}

write_json(closeout_file, record)
write_json(RUNTIME_OUT, record)
write_json(OUT, report)

print(f"Report written to: {OUT}")
print(f"Runtime closeout written to: {RUNTIME_OUT}")
print(f"Closeout file written to: {closeout_file}")
print(f"safe_mode_active={safe_mode}")
print(f"archive_safety_closeout_passed={archive_safety_closeout_passed}")
print(f"phase20_status={phase20_status}")
print(f"phase21_status={phase21_status}")
print("phase22_status=archive_safety_closeout_complete")
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
