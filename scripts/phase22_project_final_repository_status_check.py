import json, os, subprocess, time
from pathlib import Path

OUT = Path("data/processed/phase22_project_final_repository_status_check.json")
RUNTIME_OUT = Path("runtime/phase22_project_final_repository_status_check_state.json")
PHASE22_DIR = Path("data/processed/phase22_project_archive")

FINAL_REVIEW = Path("data/processed/phase22_project_final_closeout_review.json")
FINAL_REVIEW_RUNTIME = Path("runtime/phase22_project_final_closeout_review_state.json")
FINAL_REVIEW_FILE = Path("data/processed/phase22_project_archive/project_final_closeout_review.json")

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

def git_status_short():
    r = run(["git", "status", "--short"])
    return r.stdout.strip() if r.returncode == 0 else ""

def git_remote_url():
    r = run(["git", "remote", "get-url", "origin"])
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

head = git_head()
branch = git_branch()
remote = git_remote_url()
status_before_outputs = git_status_short()
git_working_tree_clean_before_outputs = status_before_outputs == ""

review = load_json(FINAL_REVIEW)
review_runtime = load_json(FINAL_REVIEW_RUNTIME)
review_file = load_json(FINAL_REVIEW_FILE)
manifest = load_json(ARCHIVE_MANIFEST)
index = load_json(ARCHIVE_INDEX)

final_review_passed = (
    review.get("project_final_closeout_review_passed") is True
    or review_runtime.get("project_final_closeout_review_passed") is True
    or review_file.get("project_final_closeout_review_passed") is True
)

project_status = review.get("project_status") or review_file.get("project_status")
phase20_status = review.get("phase20_status") or review_file.get("phase20_status")
phase21_status = review.get("phase21_status") or review_file.get("phase21_status")
phase22_status = review.get("phase22_status") or review_file.get("phase22_status")
selected_phase21_next_action = review.get("selected_phase21_next_action") or review_file.get("selected_phase21_next_action")

evidence_count = review.get("evidence_file_count") or manifest.get("evidence_file_count", 0)
runtime_count = review.get("runtime_file_count") or manifest.get("runtime_file_count", 0)
doc_count = review.get("documentation_file_count") or manifest.get("documentation_file_count", 0)

repo_checks = {
    "safe_mode_active": safe_mode,
    "git_head_present": head is not None and len(head) >= 7,
    "git_branch_present": branch is not None and len(branch) > 0,
    "git_remote_origin_present": remote is not None and len(remote) > 0,
    "git_working_tree_clean_before_outputs": git_working_tree_clean_before_outputs,
    "final_review_present": FINAL_REVIEW.exists(),
    "final_review_runtime_present": FINAL_REVIEW_RUNTIME.exists(),
    "final_review_file_present": FINAL_REVIEW_FILE.exists(),
    "archive_manifest_present": ARCHIVE_MANIFEST.exists(),
    "archive_index_present": ARCHIVE_INDEX.exists(),
    "project_final_closeout_review_passed": final_review_passed,
    "project_status_remain_on_hold": project_status == "remain_on_hold_not_approved_for_execution",
    "phase20_status_closed_remain_on_hold": phase20_status == "closed_remain_on_hold",
    "phase21_status_closed_final_remain_on_hold": phase21_status == "closed_final_remain_on_hold",
    "phase22_status_project_final_closeout_review_complete": phase22_status == "project_final_closeout_review_complete",
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

blockers = [key for key, value in repo_checks.items() if value is not True]
repository_status_check_passed = all(repo_checks.values())

if repository_status_check_passed:
    decision = "PHASE_22_PROJECT_FINAL_REPOSITORY_STATUS_CHECK_COMPLETE_REMAIN_ON_HOLD_NOT_APPROVED_FOR_EXECUTION"
    next_phase = "Phase 22.15 — Project Final Repository Status Review"
else:
    decision = "PHASE_22_PROJECT_FINAL_REPOSITORY_STATUS_CHECK_FAILED_REVIEW_REQUIRED"
    next_phase = "Phase 22.15 — Project Final Repository Status Fix"

status_file = PHASE22_DIR / "project_final_repository_status_check.json"

record = {
    "phase": "phase_22_14_project_final_repository_status_check_record",
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
    "phase22_status": "project_final_repository_status_check_complete",
    "selected_phase21_next_action": selected_phase21_next_action,
    "repository_status_check_passed": repository_status_check_passed,
    "repo_checks": repo_checks,
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
    "phase": "phase_22_14_project_final_repository_status_check",
    "generated_at_unix": int(time.time()),
    "scope": "repository_status_check_only_no_monitoring_no_dry_run_no_backtest_no_execution",
    "git_head": head,
    "git_branch": branch,
    "git_remote_origin": remote,
    "safety_flags": flags,
    "safe_mode_active": safe_mode,
    "git_working_tree_clean_before_outputs": git_working_tree_clean_before_outputs,
    "project_status": "remain_on_hold_not_approved_for_execution",
    "phase20_status": phase20_status,
    "phase21_status": phase21_status,
    "phase22_status": "project_final_repository_status_check_complete",
    "selected_phase21_next_action": selected_phase21_next_action,
    "repository_status_check_passed": repository_status_check_passed,
    "evidence_file_count": evidence_count,
    "runtime_file_count": runtime_count,
    "documentation_file_count": doc_count,
    "repo_checks": repo_checks,
    "blockers": blockers,
    "status_file": str(status_file),
    "runtime_status_file": str(RUNTIME_OUT),
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

write_json(status_file, record)
write_json(RUNTIME_OUT, record)
write_json(OUT, report)

print(f"Report written to: {OUT}")
print(f"Runtime status written to: {RUNTIME_OUT}")
print(f"Status file written to: {status_file}")
print(f"safe_mode_active={safe_mode}")
print(f"repository_status_check_passed={repository_status_check_passed}")
print(f"git_working_tree_clean_before_outputs={git_working_tree_clean_before_outputs}")
print("project_status=remain_on_hold_not_approved_for_execution")
print(f"phase20_status={phase20_status}")
print(f"phase21_status={phase21_status}")
print("phase22_status=project_final_repository_status_check_complete")
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
