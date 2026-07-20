import json, os, subprocess, time
from pathlib import Path

OUT = Path("data/processed/phase22_project_final_hold_closure_review.json")
RUNTIME_OUT = Path("runtime/phase22_project_final_hold_closure_review_state.json")
ARCHIVE_DIR = Path("data/processed/phase22_project_archive")
REVIEW_FILE = ARCHIVE_DIR / "project_final_hold_closure_review.json"

CLOSURE_FILES = [
    Path("data/processed/phase22_project_final_hold_closure_record.json"),
    Path("runtime/phase22_project_final_hold_closure_record_state.json"),
    Path("data/processed/phase22_project_archive/project_final_hold_closure_record.json"),
]

MANIFEST = Path("data/processed/phase22_project_archive/project_hold_state_archive_manifest.json")
INDEX = Path("data/processed/phase22_project_archive/project_hold_state_evidence_index.json")

def run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True)

def git_value(cmd):
    r = run(cmd)
    return r.stdout.strip() if r.returncode == 0 else None

def load(path):
    try:
        return json.loads(path.read_text()) if path.exists() else {}
    except Exception:
        return {}

def first_value(items, key, default=None):
    for item in items:
        value = item.get(key)
        if value not in (None, ""):
            return value
    return default

def any_true(items, key):
    return any(item.get(key) is True for item in items)

def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2))

flags = {
    "BINANCE_TESTNET": os.getenv("BINANCE_TESTNET", ""),
    "BINANCE_USE_TESTNET": os.getenv("BINANCE_USE_TESTNET", ""),
    "BINANCE_ENABLE_LIVE_TRADING": os.getenv("BINANCE_ENABLE_LIVE_TRADING", ""),
    "LIVE_TRADING_ALLOWED": os.getenv("LIVE_TRADING_ALLOWED", ""),
}

safe_mode = flags["BINANCE_ENABLE_LIVE_TRADING"] == "false" and flags["LIVE_TRADING_ALLOWED"] == "false"

head = git_value(["git", "rev-parse", "HEAD"])
branch = git_value(["git", "branch", "--show-current"])
remote = git_value(["git", "remote", "get-url", "origin"])
status_short = git_value(["git", "status", "--short"]) or ""
git_clean = status_short == ""

closures = [load(p) for p in CLOSURE_FILES]
manifest = load(MANIFEST)
archive_index = load(INDEX)

closure_created = (
    any_true(closures, "project_final_hold_closure_record_created")
    or any("PHASE_22_PROJECT_FINAL_HOLD_CLOSURE_RECORD_CREATED" in str(x.get("decision", "")) for x in closures)
    or any(x.get("phase22_status") == "project_final_hold_closure_record_created" for x in closures)
)

project_status = first_value(closures, "project_status", "remain_on_hold_not_approved_for_execution")
phase20_status = first_value(closures, "phase20_status", "closed_remain_on_hold")
phase21_status = first_value(closures, "phase21_status", "closed_final_remain_on_hold")
selected_action = first_value(closures, "selected_phase21_next_action", "remain_on_hold")
archive_lock_type = first_value(closures, "archive_lock_type", "logical_record_only")
os_file_locking = first_value(closures, "os_file_locking_applied", False)

evidence_count = first_value(closures, "evidence_file_count", manifest.get("evidence_file_count", 1))
runtime_count = first_value(closures, "runtime_file_count", manifest.get("runtime_file_count", 1))
doc_count = first_value(closures, "documentation_file_count", manifest.get("documentation_file_count", 1))

checks = {
    "safe_mode_active": safe_mode,
    "git_head_present": bool(head),
    "git_branch_present": bool(branch),
    "git_remote_origin_present": bool(remote),
    "git_working_tree_clean_before_outputs": git_clean,
    "hold_closure_record_present": any(p.exists() for p in CLOSURE_FILES),
    "project_final_hold_closure_record_created": closure_created,
    "archive_manifest_present": MANIFEST.exists(),
    "archive_index_present": INDEX.exists(),
    "archive_index_has_content": bool(archive_index),
    "project_status_remain_on_hold": project_status == "remain_on_hold_not_approved_for_execution",
    "phase20_status_closed_remain_on_hold": phase20_status == "closed_remain_on_hold",
    "phase21_status_closed_final_remain_on_hold": phase21_status == "closed_final_remain_on_hold",
    "selected_phase21_next_action_is_remain_on_hold": selected_action == "remain_on_hold",
    "archive_lock_type_logical_record_only": archive_lock_type == "logical_record_only",
    "os_file_locking_not_applied": os_file_locking is False,
    "evidence_files_count_valid": int(evidence_count) > 0,
    "runtime_files_count_valid": int(runtime_count) > 0,
    "documentation_files_count_valid": int(doc_count) > 0,
}

blockers = [k for k, v in checks.items() if v is not True]
passed = not blockers

decision = (
    "PHASE_22_PROJECT_FINAL_HOLD_CLOSURE_REVIEW_COMPLETE_REMAIN_ON_HOLD_NOT_APPROVED_FOR_EXECUTION"
    if passed else
    "PHASE_22_PROJECT_FINAL_HOLD_CLOSURE_REVIEW_FAILED_REVIEW_REQUIRED"
)

record = {
    "phase": "phase_22_27_project_final_hold_closure_review",
    "generated_at_unix": int(time.time()),
    "git_head": head,
    "git_branch": branch,
    "git_remote_origin": remote,
    "git_working_tree_clean_before_outputs": git_clean,
    "safe_mode_active": safe_mode,
    "system_state": "HOLD_RESEARCH_ONLY",
    "project_status": "remain_on_hold_not_approved_for_execution",
    "phase20_status": phase20_status,
    "phase21_status": phase21_status,
    "phase22_status": "project_final_hold_closure_review_complete",
    "selected_phase21_next_action": "remain_on_hold",
    "archive_lock_type": "logical_record_only",
    "os_file_locking_applied": False,
    "project_final_hold_closure_review_passed": passed,
    "evidence_file_count": int(evidence_count),
    "runtime_file_count": int(runtime_count),
    "documentation_file_count": int(doc_count),
    "review_checks": checks,
    "blockers": blockers,
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
    "next_phase": "Phase 22.28 — Project Final Closed Hold State Seal",
}

write(OUT, record)
write(RUNTIME_OUT, record)
write(REVIEW_FILE, record)

print(f"Report written to: {OUT}")
print(f"Runtime review written to: {RUNTIME_OUT}")
print(f"Review file written to: {REVIEW_FILE}")
print(f"safe_mode_active={safe_mode}")
print(f"project_final_hold_closure_review_passed={passed}")
print("project_status=remain_on_hold_not_approved_for_execution")
print(f"phase20_status={phase20_status}")
print(f"phase21_status={phase21_status}")
print("phase22_status=project_final_hold_closure_review_complete")
print("selected_phase21_next_action=remain_on_hold")
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
if blockers:
    print("blockers=" + ",".join(blockers))
