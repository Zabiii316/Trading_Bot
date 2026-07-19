import json, os, subprocess, time
from pathlib import Path

OUT = Path("data/processed/phase22_project_final_archive_completion_review.json")
RUNTIME_OUT = Path("runtime/phase22_project_final_archive_completion_review_state.json")
PHASE22_DIR = Path("data/processed/phase22_project_archive")

ARCHIVE_COMPLETION = Path("data/processed/phase22_project_final_archive_completion_record.json")
ARCHIVE_COMPLETION_RUNTIME = Path("runtime/phase22_project_final_archive_completion_record_state.json")
ARCHIVE_COMPLETION_FILE = Path("data/processed/phase22_project_archive/project_final_archive_completion_record.json")

REPOSITORY_EVIDENCE_REVIEW = Path("data/processed/phase22_project_final_repository_evidence_review.json")
REPOSITORY_EVIDENCE_CONSOLIDATION = Path("data/processed/phase22_project_final_repository_evidence_consolidation.json")
REPOSITORY_STATUS_REVIEW = Path("data/processed/phase22_project_final_repository_status_review.json")
FINAL_CLOSEOUT_REVIEW = Path("data/processed/phase22_project_final_closeout_review.json")
FINAL_SAFETY_CLOSEOUT_REVIEW = Path("data/processed/phase22_project_final_safety_closeout_review.json")
FINAL_EVIDENCE_SEAL_REVIEW = Path("data/processed/phase22_project_final_evidence_seal_review.json")
FINAL_EVIDENCE_SEAL = Path("data/processed/phase22_project_final_evidence_seal.json")

ARCHIVE_MANIFEST = Path("data/processed/phase22_project_archive/project_hold_state_archive_manifest.json")
ARCHIVE_INDEX = Path("data/processed/phase22_project_archive/project_hold_state_evidence_index.json")

def run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True)

def git_head():
    result = run(["git", "rev-parse", "HEAD"])
    return result.stdout.strip() if result.returncode == 0 else None

def git_branch():
    result = run(["git", "branch", "--show-current"])
    return result.stdout.strip() if result.returncode == 0 else None

def git_remote_url():
    result = run(["git", "remote", "get-url", "origin"])
    return result.stdout.strip() if result.returncode == 0 else None

def git_status_short():
    result = run(["git", "status", "--short"])
    return result.stdout.strip() if result.returncode == 0 else ""

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

completion = load_json(ARCHIVE_COMPLETION)
completion_runtime = load_json(ARCHIVE_COMPLETION_RUNTIME)
completion_file = load_json(ARCHIVE_COMPLETION_FILE)
repo_review = load_json(REPOSITORY_EVIDENCE_REVIEW)
repo_consolidation = load_json(REPOSITORY_EVIDENCE_CONSOLIDATION)
repo_status_review = load_json(REPOSITORY_STATUS_REVIEW)
final_closeout_review = load_json(FINAL_CLOSEOUT_REVIEW)
safety_review = load_json(FINAL_SAFETY_CLOSEOUT_REVIEW)
seal_review = load_json(FINAL_EVIDENCE_SEAL_REVIEW)
seal = load_json(FINAL_EVIDENCE_SEAL)
manifest = load_json(ARCHIVE_MANIFEST)
archive_index = load_json(ARCHIVE_INDEX)

archive_completion_created = (
    completion.get("project_final_archive_completion_record_created") is True
    or completion_runtime.get("project_final_archive_completion_record_created") is True
    or completion_file.get("project_final_archive_completion_record_created") is True
)

repository_evidence_review_passed = repo_review.get("repository_evidence_review_passed") is True
repository_evidence_consolidated = repo_consolidation.get("repository_evidence_consolidated") is True
repository_status_review_passed = repo_status_review.get("repository_status_review_passed") is True
project_final_closeout_review_passed = final_closeout_review.get("project_final_closeout_review_passed") is True
project_final_safety_closeout_review_passed = safety_review.get("project_final_safety_closeout_review_passed") is True
final_evidence_seal_review_passed = seal_review.get("final_evidence_seal_review_passed") is True
final_evidence_seal_ready = seal.get("final_evidence_seal_ready") is True

project_status = completion.get("project_status") or completion_file.get("project_status")
phase20_status = completion.get("phase20_status") or completion_file.get("phase20_status")
phase21_status = completion.get("phase21_status") or completion_file.get("phase21_status")
phase22_previous_status = completion.get("phase22_status") or completion_file.get("phase22_status")
selected_phase21_next_action = completion.get("selected_phase21_next_action") or completion_file.get("selected_phase21_next_action")

evidence_count = completion.get("evidence_file_count") or manifest.get("evidence_file_count", 0)
runtime_count = completion.get("runtime_file_count") or manifest.get("runtime_file_count", 0)
doc_count = completion.get("documentation_file_count") or manifest.get("documentation_file_count", 0)

archive_index_has_content = len(archive_index.keys()) > 0 if isinstance(archive_index, dict) else False

review_checks = {
    "safe_mode_active": safe_mode,
    "git_head_present": head is not None and len(head) >= 7,
    "git_branch_present": branch is not None and len(branch) > 0,
    "git_remote_origin_present": remote is not None and len(remote) > 0,
    "git_working_tree_clean_before_outputs": git_working_tree_clean_before_outputs,
    "archive_completion_present": ARCHIVE_COMPLETION.exists(),
    "archive_completion_runtime_present": ARCHIVE_COMPLETION_RUNTIME.exists(),
    "archive_completion_file_present": ARCHIVE_COMPLETION_FILE.exists(),
    "repository_evidence_review_present": REPOSITORY_EVIDENCE_REVIEW.exists(),
    "repository_evidence_consolidation_present": REPOSITORY_EVIDENCE_CONSOLIDATION.exists(),
    "repository_status_review_present": REPOSITORY_STATUS_REVIEW.exists(),
    "final_closeout_review_present": FINAL_CLOSEOUT_REVIEW.exists(),
    "final_safety_closeout_review_present": FINAL_SAFETY_CLOSEOUT_REVIEW.exists(),
    "final_evidence_seal_review_present": FINAL_EVIDENCE_SEAL_REVIEW.exists(),
    "final_evidence_seal_present": FINAL_EVIDENCE_SEAL.exists(),
    "archive_manifest_present": ARCHIVE_MANIFEST.exists(),
    "archive_index_present": ARCHIVE_INDEX.exists(),
    "archive_index_has_content": archive_index_has_content,
    "archive_completion_created": archive_completion_created,
    "repository_evidence_review_passed": repository_evidence_review_passed,
    "repository_evidence_consolidated": repository_evidence_consolidated,
    "repository_status_review_passed": repository_status_review_passed,
    "project_final_closeout_review_passed": project_final_closeout_review_passed,
    "project_final_safety_closeout_review_passed": project_final_safety_closeout_review_passed,
    "final_evidence_seal_review_passed": final_evidence_seal_review_passed,
    "final_evidence_seal_ready": final_evidence_seal_ready,
    "project_status_remain_on_hold": project_status == "remain_on_hold_not_approved_for_execution",
    "phase20_status_closed_remain_on_hold": phase20_status == "closed_remain_on_hold",
    "phase21_status_closed_final_remain_on_hold": phase21_status == "closed_final_remain_on_hold",
    "phase22_previous_status_archive_completion_record_created": phase22_previous_status == "project_final_archive_completion_record_created",
    "selected_phase21_next_action_is_remain_on_hold": selected_phase21_next_action == "remain_on_hold",
    "evidence_files_count_valid": evidence_count > 0,
    "runtime_files_count_valid": runtime_count > 0,
    "documentation_files_count_valid": doc_count > 0,
    "monitoring_not_started": completion.get("monitoring_started") is False,
    "run_dry_run_now_false": completion.get("run_dry_run_now") is False,
    "run_backtest_now_false": completion.get("run_backtest_now") is False,
    "execution_allowed_false": completion.get("execution_allowed") is False,
    "approved_for_execution_false": completion.get("approved_for_execution") is False,
    "approved_for_paper_shadow_false": completion.get("approved_for_paper_shadow") is False,
    "approved_for_live_false": completion.get("approved_for_live") is False,
    "paper_shadow_not_started": completion.get("paper_shadow_started") is False,
    "paper_shadow_start_not_approved": completion.get("approved_for_paper_shadow_start") is False,
    "exchange_order_submission_disabled": completion.get("exchange_order_submission") is False,
    "micro_live_not_approved": completion.get("approved_for_micro_live_execution") is False,
    "real_live_not_approved": completion.get("approved_for_real_live_trading") is False,
}

blockers = [key for key, value in review_checks.items() if value is not True]
archive_completion_review_passed = all(review_checks.values())

if archive_completion_review_passed:
    decision = "PHASE_22_PROJECT_FINAL_ARCHIVE_COMPLETION_REVIEW_COMPLETE_REMAIN_ON_HOLD_NOT_APPROVED_FOR_EXECUTION"
    next_phase = "Phase 22.20 — Project Final Archive Lock Record"
else:
    decision = "PHASE_22_PROJECT_FINAL_ARCHIVE_COMPLETION_REVIEW_FAILED_REVIEW_REQUIRED"
    next_phase = "Phase 22.20 — Project Final Archive Completion Review Fix"

review_file = PHASE22_DIR / "project_final_archive_completion_review.json"

record = {
    "phase": "phase_22_19_project_final_archive_completion_review_record",
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
    "phase22_status": "project_final_archive_completion_review_complete",
    "selected_phase21_next_action": selected_phase21_next_action,
    "archive_completion_review_passed": archive_completion_review_passed,
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
    "phase": "phase_22_19_project_final_archive_completion_review",
    "generated_at_unix": int(time.time()),
    "scope": "archive_completion_review_only_no_monitoring_no_dry_run_no_backtest_no_execution",
    "git_head": head,
    "git_branch": branch,
    "git_remote_origin": remote,
    "safety_flags": flags,
    "safe_mode_active": safe_mode,
    "git_working_tree_clean_before_outputs": git_working_tree_clean_before_outputs,
    "project_status": "remain_on_hold_not_approved_for_execution",
    "phase20_status": phase20_status,
    "phase21_status": phase21_status,
    "phase22_status": "project_final_archive_completion_review_complete",
    "selected_phase21_next_action": selected_phase21_next_action,
    "archive_completion_review_passed": archive_completion_review_passed,
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
print(f"archive_completion_review_passed={archive_completion_review_passed}")
print(f"git_working_tree_clean_before_outputs={git_working_tree_clean_before_outputs}")
print("project_status=remain_on_hold_not_approved_for_execution")
print(f"phase20_status={phase20_status}")
print(f"phase21_status={phase21_status}")
print("phase22_status=project_final_archive_completion_review_complete")
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
