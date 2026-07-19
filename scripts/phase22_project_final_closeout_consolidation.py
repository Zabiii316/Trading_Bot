import json, os, subprocess, time
from pathlib import Path

OUT = Path("data/processed/phase22_project_final_closeout_consolidation.json")
RUNTIME_OUT = Path("runtime/phase22_project_final_closeout_consolidation_state.json")
PHASE22_DIR = Path("data/processed/phase22_project_archive")

SAFETY_REVIEW = Path("data/processed/phase22_project_final_safety_closeout_review.json")
SAFETY_REVIEW_RUNTIME = Path("runtime/phase22_project_final_safety_closeout_review_state.json")
SAFETY_REVIEW_FILE = Path("data/processed/phase22_project_archive/project_final_safety_closeout_review.json")

SAFETY_CLOSEOUT = Path("data/processed/phase22_project_final_safety_closeout.json")
SEAL_CONSOLIDATION = Path("data/processed/phase22_project_final_evidence_seal_consolidation.json")
SEAL_REVIEW = Path("data/processed/phase22_project_final_evidence_seal_review.json")
SEAL_REPORT = Path("data/processed/phase22_project_final_evidence_seal.json")
FINAL_HOLD_CLOSEOUT = Path("data/processed/phase22_project_final_hold_state_closeout.json")
FINAL_SUMMARY = Path("data/processed/phase22_project_hold_state_final_summary.json")
ARCHIVE_MANIFEST = Path("data/processed/phase22_project_archive/project_hold_state_archive_manifest.json")
ARCHIVE_INDEX = Path("data/processed/phase22_project_archive/project_hold_state_evidence_index.json")

PHASE21_FINAL = Path("data/processed/phase21_post_strategy_rework_hold_monitoring_final_safety_closeout.json")
PHASE20_CLOSEOUT = Path("data/processed/phase20_strategy_rework_safety_closeout.json")

def run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True)

def git_clean():
    return run(["git", "status", "--short"]).stdout.strip() == ""

def git_head():
    result = run(["git", "rev-parse", "HEAD"])
    return result.stdout.strip() if result.returncode == 0 else None

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

review = load_json(SAFETY_REVIEW)
review_runtime = load_json(SAFETY_REVIEW_RUNTIME)
review_file = load_json(SAFETY_REVIEW_FILE)
safety_closeout = load_json(SAFETY_CLOSEOUT)
seal_consolidation = load_json(SEAL_CONSOLIDATION)
seal_review = load_json(SEAL_REVIEW)
seal_report = load_json(SEAL_REPORT)
final_hold = load_json(FINAL_HOLD_CLOSEOUT)
summary = load_json(FINAL_SUMMARY)
manifest = load_json(ARCHIVE_MANIFEST)
archive_index = load_json(ARCHIVE_INDEX)
phase21 = load_json(PHASE21_FINAL)
phase20 = load_json(PHASE20_CLOSEOUT)

safety_review_passed = (
    review.get("project_final_safety_closeout_review_passed") is True
    or review_runtime.get("project_final_safety_closeout_review_passed") is True
    or review_file.get("project_final_safety_closeout_review_passed") is True
)

safety_closeout_passed = safety_closeout.get("project_final_safety_closeout_passed") is True
seal_consolidated = seal_consolidation.get("final_evidence_seal_consolidated") is True
seal_review_passed = seal_review.get("final_evidence_seal_review_passed") is True
seal_ready = seal_report.get("final_evidence_seal_ready") is True
final_hold_closeout_passed = final_hold.get("final_hold_state_closeout_passed") is True
final_summary_ready = summary.get("final_summary_ready") is True
phase21_final_passed = phase21.get("final_safety_closeout_passed") is True
phase20_closeout_passed = phase20.get("strategy_rework_safety_closeout_passed") is True

project_status = review.get("project_status") or review_file.get("project_status")
phase20_status = review.get("phase20_status") or review_file.get("phase20_status")
phase21_status = review.get("phase21_status") or review_file.get("phase21_status")
phase22_previous_status = review.get("phase22_status") or review_file.get("phase22_status")
selected_phase21_next_action = review.get("selected_phase21_next_action") or review_file.get("selected_phase21_next_action")

evidence_count = review.get("evidence_file_count") or manifest.get("evidence_file_count", 0)
runtime_count = review.get("runtime_file_count") or manifest.get("runtime_file_count", 0)
doc_count = review.get("documentation_file_count") or manifest.get("documentation_file_count", 0)

consolidation_checks = {
    "safe_mode_active": safe_mode,
    "safety_review_present": SAFETY_REVIEW.exists(),
    "safety_review_runtime_present": SAFETY_REVIEW_RUNTIME.exists(),
    "safety_review_file_present": SAFETY_REVIEW_FILE.exists(),
    "safety_closeout_present": SAFETY_CLOSEOUT.exists(),
    "seal_consolidation_present": SEAL_CONSOLIDATION.exists(),
    "seal_review_present": SEAL_REVIEW.exists(),
    "seal_report_present": SEAL_REPORT.exists(),
    "final_hold_closeout_present": FINAL_HOLD_CLOSEOUT.exists(),
    "final_summary_present": FINAL_SUMMARY.exists(),
    "archive_manifest_present": ARCHIVE_MANIFEST.exists(),
    "archive_index_present": ARCHIVE_INDEX.exists(),
    "phase21_final_present": PHASE21_FINAL.exists(),
    "phase20_closeout_present": PHASE20_CLOSEOUT.exists(),
    "safety_review_passed": safety_review_passed,
    "safety_closeout_passed": safety_closeout_passed,
    "final_evidence_seal_consolidated": seal_consolidated,
    "seal_review_passed": seal_review_passed,
    "seal_ready": seal_ready,
    "final_hold_closeout_passed": final_hold_closeout_passed,
    "final_summary_ready": final_summary_ready,
    "phase21_final_passed": phase21_final_passed,
    "phase20_closeout_passed": phase20_closeout_passed,
    "project_status_remain_on_hold": project_status == "remain_on_hold_not_approved_for_execution",
    "phase20_status_closed_remain_on_hold": phase20_status == "closed_remain_on_hold",
    "phase21_status_closed_final_remain_on_hold": phase21_status == "closed_final_remain_on_hold",
    "phase22_previous_status_review_complete": phase22_previous_status == "project_final_safety_closeout_review_complete",
    "selected_phase21_next_action_is_remain_on_hold": selected_phase21_next_action == "remain_on_hold",
    "evidence_files_count_valid": evidence_count > 0,
    "runtime_files_count_valid": runtime_count > 0,
    "documentation_files_count_valid": doc_count > 0,
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

blockers = [key for key, value in consolidation_checks.items() if value is not True]
project_final_closeout_consolidated = all(consolidation_checks.values())

if project_final_closeout_consolidated:
    decision = "PHASE_22_PROJECT_FINAL_CLOSEOUT_CONSOLIDATED_REMAIN_ON_HOLD_NOT_APPROVED_FOR_EXECUTION"
    next_phase = "Phase 22.13 — Project Final Closeout Review"
else:
    decision = "PHASE_22_PROJECT_FINAL_CLOSEOUT_CONSOLIDATION_FAILED_REVIEW_REQUIRED"
    next_phase = "Phase 22.13 — Project Final Closeout Consolidation Fix"

consolidation_file = PHASE22_DIR / "project_final_closeout_consolidation.json"

record = {
    "phase": "phase_22_12_project_final_closeout_consolidation_record",
    "created_at_unix": int(time.time()),
    "git_head": git_head_value,
    "system_state": "HOLD_RESEARCH_ONLY",
    "project_status": "remain_on_hold_not_approved_for_execution",
    "phase20_status": phase20_status,
    "phase21_status": phase21_status,
    "phase22_status": "project_final_closeout_consolidated",
    "selected_phase21_next_action": selected_phase21_next_action,
    "project_final_closeout_consolidated": project_final_closeout_consolidated,
    "consolidation_checks": consolidation_checks,
    "blockers": blockers,
    "evidence_file_count": evidence_count,
    "runtime_file_count": runtime_count,
    "documentation_file_count": doc_count,
    "final_project_closeout_state": {
        "system_state": "HOLD_RESEARCH_ONLY",
        "project_status": "remain_on_hold_not_approved_for_execution",
        "phase20_status": phase20_status,
        "phase21_status": phase21_status,
        "phase22_status": "project_final_closeout_consolidated",
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
    "phase": "phase_22_12_project_final_closeout_consolidation",
    "generated_at_unix": int(time.time()),
    "scope": "project_final_closeout_consolidation_only_no_monitoring_no_dry_run_no_backtest_no_execution",
    "git_head": git_head_value,
    "safety_flags": flags,
    "safe_mode_active": safe_mode,
    "git_working_tree_clean": git_clean_value,
    "project_status": "remain_on_hold_not_approved_for_execution",
    "phase20_status": phase20_status,
    "phase21_status": phase21_status,
    "phase22_status": "project_final_closeout_consolidated",
    "selected_phase21_next_action": selected_phase21_next_action,
    "project_final_closeout_consolidated": project_final_closeout_consolidated,
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
print(f"project_final_closeout_consolidated={project_final_closeout_consolidated}")
print("project_status=remain_on_hold_not_approved_for_execution")
print(f"phase20_status={phase20_status}")
print(f"phase21_status={phase21_status}")
print("phase22_status=project_final_closeout_consolidated")
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
