import json, os, subprocess, time
from pathlib import Path

OUT = Path("data/processed/phase22_project_final_archive_lock_record.json")
RUNTIME_OUT = Path("runtime/phase22_project_final_archive_lock_record_state.json")
PHASE22_DIR = Path("data/processed/phase22_project_archive")

ARCHIVE_COMPLETION_REVIEW = Path("data/processed/phase22_project_final_archive_completion_review.json")
ARCHIVE_COMPLETION_REVIEW_RUNTIME = Path("runtime/phase22_project_final_archive_completion_review_state.json")
ARCHIVE_COMPLETION_REVIEW_FILE = Path("data/processed/phase22_project_archive/project_final_archive_completion_review.json")

ARCHIVE_COMPLETION_RECORD = Path("data/processed/phase22_project_final_archive_completion_record.json")
REPOSITORY_EVIDENCE_REVIEW = Path("data/processed/phase22_project_final_repository_evidence_review.json")
REPOSITORY_EVIDENCE_CONSOLIDATION = Path("data/processed/phase22_project_final_repository_evidence_consolidation.json")
FINAL_CLOSEOUT_REVIEW = Path("data/processed/phase22_project_final_closeout_review.json")
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

review = load_json(ARCHIVE_COMPLETION_REVIEW)
review_runtime = load_json(ARCHIVE_COMPLETION_REVIEW_RUNTIME)
review_file = load_json(ARCHIVE_COMPLETION_REVIEW_FILE)
completion_record = load_json(ARCHIVE_COMPLETION_RECORD)
repo_review = load_json(REPOSITORY_EVIDENCE_REVIEW)
repo_consolidation = load_json(REPOSITORY_EVIDENCE_CONSOLIDATION)
final_closeout_review = load_json(FINAL_CLOSEOUT_REVIEW)
seal = load_json(FINAL_EVIDENCE_SEAL)
manifest = load_json(ARCHIVE_MANIFEST)
archive_index = load_json(ARCHIVE_INDEX)

archive_completion_review_passed = (
    review.get("archive_completion_review_passed") is True
    or review_runtime.get("archive_completion_review_passed") is True
    or review_file.get("archive_completion_review_passed") is True
)

archive_completion_record_created = completion_record.get("project_final_archive_completion_record_created") is True
repository_evidence_review_passed = repo_review.get("repository_evidence_review_passed") is True
repository_evidence_consolidated = repo_consolidation.get("repository_evidence_consolidated") is True
project_final_closeout_review_passed = final_closeout_review.get("project_final_closeout_review_passed") is True
final_evidence_seal_ready = seal.get("final_evidence_seal_ready") is True

project_status = review.get("project_status") or review_file.get("project_status")
phase20_status = review.get("phase20_status") or review_file.get("phase20_status")
phase21_status = review.get("phase21_status") or review_file.get("phase21_status")
phase22_previous_status = review.get("phase22_status") or review_file.get("phase22_status")
selected_phase21_next_action = review.get("selected_phase21_next_action") or review_file.get("selected_phase21_next_action")

evidence_count = review.get("evidence_file_count") or manifest.get("evidence_file_count", 0)
runtime_count = review.get("runtime_file_count") or manifest.get("runtime_file_count", 0)
doc_count = review.get("documentation_file_count") or manifest.get("documentation_file_count", 0)

archive_index_has_content = len(archive_index.keys()) > 0 if isinstance(archive_index, dict) else False

lock_checks = {
    "safe_mode_active": safe_mode,
    "git_head_present": head is not None and len(head) >= 7,
    "git_branch_present": branch is not None and len(branch) > 0,
    "git_remote_origin_present": remote is not None and len(remote) > 0,
    "git_working_tree_clean_before_outputs": git_working_tree_clean_before_outputs,
    "archive_completion_review_present": ARCHIVE_COMPLETION_REVIEW.exists(),
    "archive_completion_review_runtime_present": ARCHIVE_COMPLETION_REVIEW_RUNTIME.exists(),
    "archive_completion_review_file_present": ARCHIVE_COMPLETION_REVIEW_FILE.exists(),
    "archive_completion_record_present": ARCHIVE_COMPLETION_RECORD.exists(),
    "repository_evidence_review_present": REPOSITORY_EVIDENCE_REVIEW.exists(),
    "repository_evidence_consolidation_present": REPOSITORY_EVIDENCE_CONSOLIDATION.exists(),
    "final_closeout_review_present": FINAL_CLOSEOUT_REVIEW.exists(),
    "final_evidence_seal_present": FINAL_EVIDENCE_SEAL.exists(),
    "archive_manifest_present": ARCHIVE_MANIFEST.exists(),
    "archive_index_present": ARCHIVE_INDEX.exists(),
    "archive_index_has_content": archive_index_has_content,
    "archive_completion_review_passed": archive_completion_review_passed,
    "archive_completion_record_created": archive_completion_record_created,
    "repository_evidence_review_passed": repository_evidence_review_passed,
    "repository_evidence_consolidated": repository_evidence_consolidated,
    "project_final_closeout_review_passed": project_final_closeout_review_passed,
    "final_evidence_seal_ready": final_evidence_seal_ready,
    "project_status_remain_on_hold": project_status == "remain_on_hold_not_approved_for_execution",
    "phase20_status_closed_remain_on_hold": phase20_status == "closed_remain_on_hold",
    "phase21_status_closed_final_remain_on_hold": phase21_status == "closed_final_remain_on_hold",
    "phase22_previous_status_archive_completion_review_complete": phase22_previous_status == "project_final_archive_completion_review_complete",
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

blockers = [key for key, value in lock_checks.items() if value is not True]
project_final_archive_lock_record_created = all(lock_checks.values())

if project_final_archive_lock_record_created:
    decision = "PHASE_22_PROJECT_FINAL_ARCHIVE_LOCK_RECORD_CREATED_REMAIN_ON_HOLD_NOT_APPROVED_FOR_EXECUTION"
    next_phase = "Phase 22.21 — Project Final Archive Lock Review"
else:
    decision = "PHASE_22_PROJECT_FINAL_ARCHIVE_LOCK_RECORD_FAILED_REVIEW_REQUIRED"
    next_phase = "Phase 22.21 — Project Final Archive Lock Record Fix"

lock_file = PHASE22_DIR / "project_final_archive_lock_record.json"

record = {
    "phase": "phase_22_20_project_final_archive_lock_record",
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
    "phase22_status": "project_final_archive_lock_record_created",
    "selected_phase21_next_action": selected_phase21_next_action,
    "archive_lock_type": "logical_record_only",
    "os_file_locking_applied": False,
    "project_final_archive_lock_record_created": project_final_archive_lock_record_created,
    "lock_checks": lock_checks,
    "blockers": blockers,
    "evidence_file_count": evidence_count,
    "runtime_file_count": runtime_count,
    "documentation_file_count": doc_count,
    "final_archive_lock_state": {
        "archive_status": "logically_locked_record_created",
        "system_state": "HOLD_RESEARCH_ONLY",
        "project_status": "remain_on_hold_not_approved_for_execution",
        "phase20_status": phase20_status,
        "phase21_status": phase21_status,
        "phase22_status": "project_final_archive_lock_record_created",
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
    "phase": "phase_22_20_project_final_archive_lock_record",
    "generated_at_unix": int(time.time()),
    "scope": "archive_lock_record_only_no_os_file_lock_no_monitoring_no_dry_run_no_backtest_no_execution",
    "git_head": head,
    "git_branch": branch,
    "git_remote_origin": remote,
    "safety_flags": flags,
    "safe_mode_active": safe_mode,
    "git_working_tree_clean_before_outputs": git_working_tree_clean_before_outputs,
    "project_status": "remain_on_hold_not_approved_for_execution",
    "phase20_status": phase20_status,
    "phase21_status": phase21_status,
    "phase22_status": "project_final_archive_lock_record_created",
    "selected_phase21_next_action": selected_phase21_next_action,
    "archive_lock_type": "logical_record_only",
    "os_file_locking_applied": False,
    "project_final_archive_lock_record_created": project_final_archive_lock_record_created,
    "evidence_file_count": evidence_count,
    "runtime_file_count": runtime_count,
    "documentation_file_count": doc_count,
    "lock_checks": lock_checks,
    "blockers": blockers,
    "lock_file": str(lock_file),
    "runtime_lock_file": str(RUNTIME_OUT),
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

write_json(lock_file, record)
write_json(RUNTIME_OUT, record)
write_json(OUT, report)

print(f"Report written to: {OUT}")
print(f"Runtime lock written to: {RUNTIME_OUT}")
print(f"Lock file written to: {lock_file}")
print(f"safe_mode_active={safe_mode}")
print(f"project_final_archive_lock_record_created={project_final_archive_lock_record_created}")
print(f"git_working_tree_clean_before_outputs={git_working_tree_clean_before_outputs}")
print("project_status=remain_on_hold_not_approved_for_execution")
print(f"phase20_status={phase20_status}")
print(f"phase21_status={phase21_status}")
print("phase22_status=project_final_archive_lock_record_created")
print(f"selected_phase21_next_action={selected_phase21_next_action}")
print("archive_lock_type=logical_record_only")
print("os_file_locking_applied=False")
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
