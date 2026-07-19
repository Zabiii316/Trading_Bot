import json, os, subprocess, time
from pathlib import Path

OUT = Path("data/processed/phase22_project_hold_state_archive_consolidation.json")
RUNTIME_OUT = Path("runtime/phase22_project_hold_state_archive_consolidation_state.json")
PHASE22_DIR = Path("data/processed/phase22_project_archive")

REVIEW = Path("data/processed/phase22_project_hold_state_archive_review.json")
REVIEW_RUNTIME = Path("runtime/phase22_project_hold_state_archive_review_state.json")
REVIEW_FILE = Path("data/processed/phase22_project_archive/project_hold_state_archive_review.json")

ARCHIVE_REPORT = Path("data/processed/phase22_project_hold_state_archive_and_evidence_index.json")
ARCHIVE_RUNTIME = Path("runtime/phase22_project_hold_state_archive_and_evidence_index_state.json")
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

review = load_json(REVIEW)
review_runtime = load_json(REVIEW_RUNTIME)
review_file = load_json(REVIEW_FILE)
archive_report = load_json(ARCHIVE_REPORT)
archive_runtime = load_json(ARCHIVE_RUNTIME)
manifest = load_json(MANIFEST)
index = load_json(INDEX)
phase21 = load_json(PHASE21_FINAL)

archive_review_passed = (
    review.get("archive_review_passed") is True
    or review_runtime.get("archive_review_passed") is True
    or review_file.get("archive_review_passed") is True
)

archive_index_ready = (
    archive_report.get("archive_index_ready") is True
    or archive_runtime.get("archive_index_ready") is True
    or index.get("archive_index_ready") is True
)

phase20_status = (
    review.get("phase20_status")
    or review_runtime.get("phase20_status")
    or review_file.get("phase20_status")
    or archive_report.get("phase20_status")
    or index.get("phase20_status")
)

phase21_status = (
    review.get("phase21_status")
    or review_runtime.get("phase21_status")
    or review_file.get("phase21_status")
    or archive_report.get("phase21_status")
    or index.get("phase21_status")
)

selected_phase21_next_action = (
    review.get("selected_phase21_next_action")
    or review_runtime.get("selected_phase21_next_action")
    or review_file.get("selected_phase21_next_action")
    or archive_report.get("selected_phase21_next_action")
    or index.get("selected_phase21_next_action")
)

evidence_count = review.get("evidence_file_count") or archive_report.get("evidence_file_count") or manifest.get("evidence_file_count", 0)
runtime_count = review.get("runtime_file_count") or archive_report.get("runtime_file_count") or manifest.get("runtime_file_count", 0)
doc_count = review.get("documentation_file_count") or archive_report.get("documentation_file_count") or manifest.get("documentation_file_count", 0)

consolidation_checks = {
    "safe_mode_active": safe_mode,
    "review_present": REVIEW.exists(),
    "review_runtime_present": REVIEW_RUNTIME.exists(),
    "review_file_present": REVIEW_FILE.exists(),
    "archive_report_present": ARCHIVE_REPORT.exists(),
    "archive_runtime_present": ARCHIVE_RUNTIME.exists(),
    "manifest_present": MANIFEST.exists(),
    "index_present": INDEX.exists(),
    "phase21_final_present": PHASE21_FINAL.exists(),
    "archive_review_passed": archive_review_passed,
    "archive_index_ready": archive_index_ready,
    "phase20_status_closed_remain_on_hold": phase20_status == "closed_remain_on_hold",
    "phase21_status_closed_final_remain_on_hold": phase21_status == "closed_final_remain_on_hold",
    "selected_phase21_next_action_is_remain_on_hold": selected_phase21_next_action == "remain_on_hold",
    "evidence_files_indexed": evidence_count > 0,
    "runtime_files_indexed": runtime_count > 0,
    "documentation_files_indexed": doc_count > 0,
    "manifest_evidence_files_indexed": manifest.get("evidence_file_count", 0) > 0,
    "manifest_runtime_files_indexed": manifest.get("runtime_file_count", 0) > 0,
    "manifest_documentation_files_indexed": manifest.get("documentation_file_count", 0) > 0,
    "monitoring_not_started": review.get("monitoring_started") is False,
    "run_dry_run_now_false": review.get("run_dry_run_now") is False,
    "run_backtest_now_false": review.get("run_backtest_now") is False,
    "execution_allowed_false": review.get("execution_allowed") is False,
    "approved_for_execution_false": review.get("approved_for_execution") is False,
    "approved_for_paper_shadow_false": review.get("approved_for_paper_shadow") is False,
    "approved_for_live_false": review.get("approved_for_live") is False,
    "paper_shadow_not_started": review.get("paper_shadow_started") is False,
    "paper_shadow_start_not_approved": review.get("approved_for_paper_shadow_start") is False,
    "exchange_order_submission_disabled": review.get("exchange_order_submission") is False,
    "micro_live_not_approved": review.get("approved_for_micro_live_execution") is False,
    "real_live_not_approved": review.get("approved_for_real_live_trading") is False,
}

blockers = [k for k, v in consolidation_checks.items() if v is not True]
archive_consolidated = all(consolidation_checks.values())

if archive_consolidated:
    decision = "PHASE_22_PROJECT_HOLD_STATE_ARCHIVE_CONSOLIDATED_REMAIN_ON_HOLD_NOT_APPROVED_FOR_EXECUTION"
    next_phase = "Phase 22.4 — Project Hold State Archive Safety Closeout"
else:
    decision = "PHASE_22_PROJECT_HOLD_STATE_ARCHIVE_CONSOLIDATION_FAILED_REVIEW_REQUIRED"
    next_phase = "Phase 22.4 — Project Archive Consolidation Fix"

consolidation_file = PHASE22_DIR / "project_hold_state_archive_consolidation.json"

record = {
    "phase": "phase_22_3_project_hold_state_archive_consolidation_record",
    "created_at_unix": int(time.time()),
    "git_head": current_git_head,
    "system_state": "HOLD_RESEARCH_ONLY",
    "phase20_status": phase20_status,
    "phase21_status": phase21_status,
    "selected_phase21_next_action": selected_phase21_next_action,
    "archive_consolidated": archive_consolidated,
    "consolidation_checks": consolidation_checks,
    "blockers": blockers,
    "evidence_file_count": evidence_count,
    "runtime_file_count": runtime_count,
    "documentation_file_count": doc_count,
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
    "phase": "phase_22_3_project_hold_state_archive_consolidation",
    "generated_at_unix": int(time.time()),
    "scope": "archive_consolidation_only_no_monitoring_no_dry_run_no_backtest_no_execution",
    "git_head": current_git_head,
    "safety_flags": flags,
    "safe_mode_active": safe_mode,
    "git_working_tree_clean": git_working_tree_clean,
    "phase20_status": phase20_status,
    "phase21_status": phase21_status,
    "selected_phase21_next_action": selected_phase21_next_action,
    "archive_consolidated": archive_consolidated,
    "evidence_file_count": evidence_count,
    "runtime_file_count": runtime_count,
    "documentation_file_count": doc_count,
    "consolidation_checks": consolidation_checks,
    "blockers": blockers,
    "consolidation_file": str(consolidation_file),
    "runtime_consolidation_file": str(RUNTIME_OUT),
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

write_json(consolidation_file, record)
write_json(RUNTIME_OUT, record)
write_json(OUT, report)

print(f"Report written to: {OUT}")
print(f"Runtime consolidation written to: {RUNTIME_OUT}")
print(f"Consolidation file written to: {consolidation_file}")
print(f"safe_mode_active={safe_mode}")
print(f"archive_consolidated={archive_consolidated}")
print(f"phase20_status={phase20_status}")
print(f"phase21_status={phase21_status}")
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
