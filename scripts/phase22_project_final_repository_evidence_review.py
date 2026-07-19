import json, os, subprocess, time
from pathlib import Path

OUT = Path("data/processed/phase22_project_final_repository_evidence_review.json")
RUNTIME_OUT = Path("runtime/phase22_project_final_repository_evidence_review_state.json")
PHASE22_DIR = Path("data/processed/phase22_project_archive")

CONSOLIDATION = Path("data/processed/phase22_project_final_repository_evidence_consolidation.json")
CONSOLIDATION_RUNTIME = Path("runtime/phase22_project_final_repository_evidence_consolidation_state.json")
CONSOLIDATION_FILE = Path("data/processed/phase22_project_archive/project_final_repository_evidence_consolidation.json")

STATUS_REVIEW = Path("data/processed/phase22_project_final_repository_status_review.json")
STATUS_CHECK = Path("data/processed/phase22_project_final_repository_status_check.json")
FINAL_CLOSEOUT_REVIEW = Path("data/processed/phase22_project_final_closeout_review.json")
FINAL_CLOSEOUT_CONSOLIDATION = Path("data/processed/phase22_project_final_closeout_consolidation.json")
ARCHIVE_MANIFEST = Path("data/processed/phase22_project_archive/project_hold_state_archive_manifest.json")
ARCHIVE_INDEX = Path("data/processed/phase22_project_archive/project_hold_state_evidence_index.json")

def run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True)

def git_head():
    r = run(["git", "rev-parse", "HEAD"])
    return r.stdout.strip() if r.returncode == 0 else None

def git_branch():
    r = run(["git", "branch", "--show-current"])
    return r.stdout.strip() if r.returncode == 0 else None

def git_remote_url():
    r = run(["git", "remote", "get-url", "origin"])
    return r.stdout.strip() if r.returncode == 0 else None

def git_status_short():
    r = run(["git", "status", "--short"])
    return r.stdout.strip() if r.returncode == 0 else ""

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

head = git_head()
branch = git_branch()
remote = git_remote_url()
status_before_outputs = git_status_short()
git_working_tree_clean_before_outputs = status_before_outputs == ""

consolidation = load_json(CONSOLIDATION)
consolidation_runtime = load_json(CONSOLIDATION_RUNTIME)
consolidation_file = load_json(CONSOLIDATION_FILE)
status_review = load_json(STATUS_REVIEW)
status_check = load_json(STATUS_CHECK)
final_review = load_json(FINAL_CLOSEOUT_REVIEW)
final_consolidation = load_json(FINAL_CLOSEOUT_CONSOLIDATION)
manifest = load_json(ARCHIVE_MANIFEST)
archive_index = load_json(ARCHIVE_INDEX)

repository_evidence_consolidated = (
    consolidation.get("repository_evidence_consolidated") is True
    or consolidation_runtime.get("repository_evidence_consolidated") is True
    or consolidation_file.get("repository_evidence_consolidated") is True
)

repository_status_review_passed = status_review.get("repository_status_review_passed") is True
repository_status_check_passed = status_check.get("repository_status_check_passed") is True
project_final_closeout_review_passed = final_review.get("project_final_closeout_review_passed") is True
project_final_closeout_consolidated = final_consolidation.get("project_final_closeout_consolidated") is True

project_status = consolidation.get("project_status") or consolidation_file.get("project_status")
phase20_status = consolidation.get("phase20_status") or consolidation_file.get("phase20_status")
phase21_status = consolidation.get("phase21_status") or consolidation_file.get("phase21_status")
phase22_previous_status = consolidation.get("phase22_status") or consolidation_file.get("phase22_status")
selected_phase21_next_action = consolidation.get("selected_phase21_next_action") or consolidation_file.get("selected_phase21_next_action")

evidence_count = consolidation.get("evidence_file_count") or manifest.get("evidence_file_count", 0)
runtime_count = consolidation.get("runtime_file_count") or manifest.get("runtime_file_count", 0)
doc_count = consolidation.get("documentation_file_count") or manifest.get("documentation_file_count", 0)

archive_index_has_content = len(archive_index.keys()) > 0 if isinstance(archive_index, dict) else False

review_checks = {
    "safe_mode_active": safe_mode,
    "git_head_present": head is not None and len(head) >= 7,
    "git_branch_present": branch is not None and len(branch) > 0,
    "git_remote_origin_present": remote is not None and len(remote) > 0,
    "git_working_tree_clean_before_outputs": git_working_tree_clean_before_outputs,
    "consolidation_present": CONSOLIDATION.exists(),
    "consolidation_runtime_present": CONSOLIDATION_RUNTIME.exists(),
    "consolidation_file_present": CONSOLIDATION_FILE.exists(),
    "status_review_present": STATUS_REVIEW.exists(),
    "status_check_present": STATUS_CHECK.exists(),
    "final_closeout_review_present": FINAL_CLOSEOUT_REVIEW.exists(),
    "final_closeout_consolidation_present": FINAL_CLOSEOUT_CONSOLIDATION.exists(),
    "archive_manifest_present": ARCHIVE_MANIFEST.exists(),
    "archive_index_present": ARCHIVE_INDEX.exists(),
    "archive_index_has_content": archive_index_has_content,
    "repository_evidence_consolidated": repository_evidence_consolidated,
    "repository_status_review_passed": repository_status_review_passed,
    "repository_status_check_passed": repository_status_check_passed,
    "project_final_closeout_review_passed": project_final_closeout_review_passed,
    "project_final_closeout_consolidated": project_final_closeout_consolidated,
    "project_status_remain_on_hold": project_status == "remain_on_hold_not_approved_for_execution",
    "phase20_status_closed_remain_on_hold": phase20_status == "closed_remain_on_hold",
    "phase21_status_closed_final_remain_on_hold": phase21_status == "closed_final_remain_on_hold",
    "phase22_previous_status_repository_evidence_consolidated": phase22_previous_status == "project_final_repository_evidence_consolidated",
    "selected_phase21_next_action_is_remain_on_hold": selected_phase21_next_action == "remain_on_hold",
    "evidence_files_count_valid": evidence_count > 0,
    "runtime_files_count_valid": runtime_count > 0,
    "documentation_files_count_valid": doc_count > 0,
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

blockers = [key for key, value in review_checks.items() if value is not True]
repository_evidence_review_passed = all(review_checks.values())

if repository_evidence_review_passed:
    decision = "PHASE_22_PROJECT_FINAL_REPOSITORY_EVIDENCE_REVIEW_COMPLETE_REMAIN_ON_HOLD_NOT_APPROVED_FOR_EXECUTION"
    next_phase = "Phase 22.18 — Project Final Archive Completion Record"
else:
    decision = "PHASE_22_PROJECT_FINAL_REPOSITORY_EVIDENCE_REVIEW_FAILED_REVIEW_REQUIRED"
    next_phase = "Phase 22.18 — Project Final Repository Evidence Review Fix"

review_file = PHASE22_DIR / "project_final_repository_evidence_review.json"

record = {
    "phase": "phase_22_17_project_final_repository_evidence_review_record",
    "created_at_unix": int(time.time()),
    "git_head": head,
    "git_branch": branch,
    "git_remote_origin": remote,
    "git_status_short_before_outputs": status_before_outputs,
    "git_working_tree_clean_before_outputs": git_working_tree_clean_before_outputs,
    "system_state": "HOLD_RESEARCH_ONLY",
    "project_status": "remain_on_hold_not_approved_for_execution",
    "phase20_status": phase20_status,
    "phase21_status": phase21_status,
    "phase22_status": "project_final_repository_evidence_review_complete",
    "selected_phase21_next_action": selected_phase21_next_action,
    "repository_evidence_review_passed": repository_evidence_review_passed,
    "review_checks": review_checks,
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
    "phase": "phase_22_17_project_final_repository_evidence_review",
    "generated_at_unix": int(time.time()),
    "scope": "repository_evidence_review_only_no_monitoring_no_dry_run_no_backtest_no_execution",
    "git_head": head,
    "git_branch": branch,
    "git_remote_origin": remote,
    "safety_flags": flags,
    "safe_mode_active": safe_mode,
    "git_working_tree_clean_before_outputs": git_working_tree_clean_before_outputs,
    "project_status": "remain_on_hold_not_approved_for_execution",
    "phase20_status": phase20_status,
    "phase21_status": phase21_status,
    "phase22_status": "project_final_repository_evidence_review_complete",
    "selected_phase21_next_action": selected_phase21_next_action,
    "repository_evidence_review_passed": repository_evidence_review_passed,
    "evidence_file_count": evidence_count,
    "runtime_file_count": runtime_count,
    "documentation_file_count": doc_count,
    "review_checks": review_checks,
    "blockers": blockers,
    "review_file": str(review_file),
    "runtime_review_file": str(RUNTIME_OUT),
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

write_json(review_file, record)
write_json(RUNTIME_OUT, record)
write_json(OUT, report)

print(f"Report written to: {OUT}")
print(f"Runtime review written to: {RUNTIME_OUT}")
print(f"Review file written to: {review_file}")
print(f"safe_mode_active={safe_mode}")
print(f"repository_evidence_review_passed={repository_evidence_review_passed}")
print(f"git_working_tree_clean_before_outputs={git_working_tree_clean_before_outputs}")
print("project_status=remain_on_hold_not_approved_for_execution")
print(f"phase20_status={phase20_status}")
print(f"phase21_status={phase21_status}")
print("phase22_status=project_final_repository_evidence_review_complete")
print(f"selected_phase21_next_action={selected_phase21_next_action}")
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
