import json, os, subprocess, time
from pathlib import Path

OUT = Path("data/processed/phase22_project_final_evidence_seal_consolidation.json")
RUNTIME_OUT = Path("runtime/phase22_project_final_evidence_seal_consolidation_state.json")
PHASE22_DIR = Path("data/processed/phase22_project_archive")

SEAL_REVIEW = Path("data/processed/phase22_project_final_evidence_seal_review.json")
SEAL_REVIEW_RUNTIME = Path("runtime/phase22_project_final_evidence_seal_review_state.json")
SEAL_REVIEW_FILE = Path("data/processed/phase22_project_archive/project_final_evidence_seal_review.json")

SEAL_REPORT = Path("data/processed/phase22_project_final_evidence_seal.json")
SEAL_FILE = Path("data/processed/phase22_project_archive/project_final_evidence_seal.json")
FINAL_CLOSEOUT = Path("data/processed/phase22_project_final_hold_state_closeout.json")
FINAL_SUMMARY = Path("data/processed/phase22_project_hold_state_final_summary.json")
ARCHIVE_MANIFEST = Path("data/processed/phase22_project_archive/project_hold_state_archive_manifest.json")
ARCHIVE_INDEX = Path("data/processed/phase22_project_archive/project_hold_state_evidence_index.json")

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
git_head_value = git_head()
git_clean_value = git_clean()

review = load_json(SEAL_REVIEW)
review_runtime = load_json(SEAL_REVIEW_RUNTIME)
review_file = load_json(SEAL_REVIEW_FILE)
seal = load_json(SEAL_REPORT)
seal_file = load_json(SEAL_FILE)
final_closeout = load_json(FINAL_CLOSEOUT)
final_summary = load_json(FINAL_SUMMARY)
manifest = load_json(ARCHIVE_MANIFEST)
index = load_json(ARCHIVE_INDEX)

review_passed = (
    review.get("final_evidence_seal_review_passed") is True
    or review_runtime.get("final_evidence_seal_review_passed") is True
    or review_file.get("final_evidence_seal_review_passed") is True
)

seal_ready = (
    seal.get("final_evidence_seal_ready") is True
    or seal_file.get("final_evidence_seal_ready") is True
)

final_closeout_passed = final_closeout.get("final_hold_state_closeout_passed") is True
final_summary_ready = final_summary.get("final_summary_ready") is True

project_status = review.get("project_status") or review_file.get("project_status") or seal.get("project_status")
phase20_status = review.get("phase20_status") or review_file.get("phase20_status") or seal.get("phase20_status")
phase21_status = review.get("phase21_status") or review_file.get("phase21_status") or seal.get("phase21_status")
selected_phase21_next_action = review.get("selected_phase21_next_action") or review_file.get("selected_phase21_next_action") or seal.get("selected_phase21_next_action")

evidence_count = review.get("evidence_file_count") or seal.get("evidence_file_count") or manifest.get("evidence_file_count", 0)
runtime_count = review.get("runtime_file_count") or seal.get("runtime_file_count") or manifest.get("runtime_file_count", 0)
doc_count = review.get("documentation_file_count") or seal.get("documentation_file_count") or manifest.get("documentation_file_count", 0)

sealed_evidence_count = len(seal_file.get("sealed_evidence_files", []))
sealed_runtime_count = len(seal_file.get("sealed_runtime_files", []))
sealed_doc_count = len(seal_file.get("sealed_documentation_files", []))

consolidation_checks = {
    "safe_mode_active": safe_mode,
    "seal_review_present": SEAL_REVIEW.exists(),
    "seal_review_runtime_present": SEAL_REVIEW_RUNTIME.exists(),
    "seal_review_file_present": SEAL_REVIEW_FILE.exists(),
    "seal_report_present": SEAL_REPORT.exists(),
    "seal_file_present": SEAL_FILE.exists(),
    "final_closeout_present": FINAL_CLOSEOUT.exists(),
    "final_summary_present": FINAL_SUMMARY.exists(),
    "archive_manifest_present": ARCHIVE_MANIFEST.exists(),
    "archive_index_present": ARCHIVE_INDEX.exists(),
    "final_evidence_seal_review_passed": review_passed,
    "final_evidence_seal_ready": seal_ready,
    "final_hold_state_closeout_passed": final_closeout_passed,
    "final_summary_ready": final_summary_ready,
    "project_status_remain_on_hold": project_status == "remain_on_hold_not_approved_for_execution",
    "phase20_status_closed_remain_on_hold": phase20_status == "closed_remain_on_hold",
    "phase21_status_closed_final_remain_on_hold": phase21_status == "closed_final_remain_on_hold",
    "selected_phase21_next_action_is_remain_on_hold": selected_phase21_next_action == "remain_on_hold",
    "evidence_files_count_valid": evidence_count > 0,
    "runtime_files_count_valid": runtime_count > 0,
    "documentation_files_count_valid": doc_count > 0,
    "sealed_evidence_entries_present": sealed_evidence_count > 0,
    "sealed_runtime_entries_present": sealed_runtime_count > 0,
    "sealed_documentation_entries_present": sealed_doc_count > 0,
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
final_evidence_seal_consolidated = all(consolidation_checks.values())

if final_evidence_seal_consolidated:
    decision = "PHASE_22_PROJECT_FINAL_EVIDENCE_SEAL_CONSOLIDATED_REMAIN_ON_HOLD_NOT_APPROVED_FOR_EXECUTION"
    next_phase = "Phase 22.10 — Project Final Safety Closeout"
else:
    decision = "PHASE_22_PROJECT_FINAL_EVIDENCE_SEAL_CONSOLIDATION_FAILED_REVIEW_REQUIRED"
    next_phase = "Phase 22.10 — Project Final Evidence Seal Consolidation Fix"

consolidation_file = PHASE22_DIR / "project_final_evidence_seal_consolidation.json"

record = {
    "phase": "phase_22_9_project_final_evidence_seal_consolidation_record",
    "created_at_unix": int(time.time()),
    "git_head": git_head_value,
    "system_state": "HOLD_RESEARCH_ONLY",
    "project_status": "remain_on_hold_not_approved_for_execution",
    "phase20_status": phase20_status,
    "phase21_status": phase21_status,
    "phase22_status": "final_evidence_seal_consolidated",
    "selected_phase21_next_action": selected_phase21_next_action,
    "final_evidence_seal_consolidated": final_evidence_seal_consolidated,
    "consolidation_checks": consolidation_checks,
    "blockers": blockers,
    "evidence_file_count": evidence_count,
    "runtime_file_count": runtime_count,
    "documentation_file_count": doc_count,
    "sealed_evidence_entry_count": sealed_evidence_count,
    "sealed_runtime_entry_count": sealed_runtime_count,
    "sealed_documentation_entry_count": sealed_doc_count,
    "final_consolidated_state": {
        "system_state": "HOLD_RESEARCH_ONLY",
        "project_status": "remain_on_hold_not_approved_for_execution",
        "phase20_status": phase20_status,
        "phase21_status": phase21_status,
        "phase22_status": "final_evidence_seal_consolidated",
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
    "phase": "phase_22_9_project_final_evidence_seal_consolidation",
    "generated_at_unix": int(time.time()),
    "scope": "final_evidence_seal_consolidation_only_no_monitoring_no_dry_run_no_backtest_no_execution",
    "git_head": git_head_value,
    "safety_flags": flags,
    "safe_mode_active": safe_mode,
    "git_working_tree_clean": git_clean_value,
    "project_status": "remain_on_hold_not_approved_for_execution",
    "phase20_status": phase20_status,
    "phase21_status": phase21_status,
    "phase22_status": "final_evidence_seal_consolidated",
    "selected_phase21_next_action": selected_phase21_next_action,
    "final_evidence_seal_consolidated": final_evidence_seal_consolidated,
    "evidence_file_count": evidence_count,
    "runtime_file_count": runtime_count,
    "documentation_file_count": doc_count,
    "sealed_evidence_entry_count": sealed_evidence_count,
    "sealed_runtime_entry_count": sealed_runtime_count,
    "sealed_documentation_entry_count": sealed_doc_count,
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
print(f"final_evidence_seal_consolidated={final_evidence_seal_consolidated}")
print("project_status=remain_on_hold_not_approved_for_execution")
print(f"phase20_status={phase20_status}")
print(f"phase21_status={phase21_status}")
print("phase22_status=final_evidence_seal_consolidated")
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
