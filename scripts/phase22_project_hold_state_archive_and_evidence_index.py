import json, os, subprocess, time, hashlib
from pathlib import Path

OUT = Path("data/processed/phase22_project_hold_state_archive_and_evidence_index.json")
RUNTIME_OUT = Path("runtime/phase22_project_hold_state_archive_and_evidence_index_state.json")
PHASE22_DIR = Path("data/processed/phase22_project_archive")

PHASE21_FINAL = Path("data/processed/phase21_post_strategy_rework_hold_monitoring_final_safety_closeout.json")
PHASE21_FINAL_RUNTIME = Path("runtime/phase21_post_strategy_rework_hold_monitoring_final_safety_closeout_state.json")
PHASE21_FINAL_FILE = Path("data/processed/phase21_hold_monitoring/post_strategy_rework_hold_monitoring_final_safety_closeout.json")

PHASE20_CLOSEOUT = Path("data/processed/phase20_strategy_rework_safety_closeout.json")
PHASE20_CLOSEOUT_FILE = Path("data/processed/phase20_strategy_rework/strategy_rework_safety_closeout.json")

PHASE19_CLOSEOUT = Path("data/processed/phase19_historical_data_expansion_safety_closeout.json")
PHASE18_CLOSEOUT = Path("data/processed/phase18_final_safety_closeout.json")
PHASE17_CLOSEOUT = Path("data/processed/phase17_safety_closeout_next_action_options.json")

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

def file_sha256(path):
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except Exception:
        return None

def file_entry(path):
    return {
        "path": str(path),
        "exists": path.exists(),
        "size_bytes": path.stat().st_size if path.exists() else 0,
        "sha256": file_sha256(path) if path.exists() else None
    }

def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2))

def collect_files(patterns):
    found = []
    for pattern in patterns:
        for p in sorted(Path(".").glob(pattern)):
            if p.is_file():
                found.append(p)
    unique = []
    seen = set()
    for p in found:
        s = str(p)
        if s not in seen:
            unique.append(p)
            seen.add(s)
    return unique

flags = {
    "BINANCE_TESTNET": os.getenv("BINANCE_TESTNET", ""),
    "BINANCE_USE_TESTNET": os.getenv("BINANCE_USE_TESTNET", ""),
    "BINANCE_ENABLE_LIVE_TRADING": os.getenv("BINANCE_ENABLE_LIVE_TRADING", ""),
    "LIVE_TRADING_ALLOWED": os.getenv("LIVE_TRADING_ALLOWED", ""),
}

safe_mode = flags["BINANCE_ENABLE_LIVE_TRADING"] == "false" and flags["LIVE_TRADING_ALLOWED"] == "false"
current_git_head = git_head()
git_clean_before_outputs = git_clean()

phase21 = load_json(PHASE21_FINAL)
phase21_runtime = load_json(PHASE21_FINAL_RUNTIME)
phase21_file = load_json(PHASE21_FINAL_FILE)
phase20 = load_json(PHASE20_CLOSEOUT)
phase20_file = load_json(PHASE20_CLOSEOUT_FILE)

final_safety_closeout_passed = (
    phase21.get("final_safety_closeout_passed") is True
    or phase21_runtime.get("final_safety_closeout_passed") is True
    or phase21_file.get("final_safety_closeout_passed") is True
)

phase20_closeout_passed = (
    phase20.get("strategy_rework_safety_closeout_passed") is True
    or phase20_file.get("strategy_rework_safety_closeout_passed") is True
)

phase20_status = (
    phase21.get("phase20_status")
    or phase21_runtime.get("phase20_status")
    or phase21_file.get("phase20_status")
    or phase20.get("phase20_status")
    or phase20_file.get("phase20_status")
)

phase21_status = (
    phase21.get("phase21_status")
    or phase21_runtime.get("phase21_status")
    or phase21_file.get("phase21_status")
)

selected_phase21_next_action = (
    phase21.get("selected_phase21_next_action")
    or phase21_runtime.get("selected_phase21_next_action")
    or phase21_file.get("selected_phase21_next_action")
)

evidence_files = collect_files([
    "data/processed/phase17*.json",
    "data/processed/phase18*.json",
    "data/processed/phase19*.json",
    "data/processed/phase20*.json",
    "data/processed/phase21*.json",
    "data/processed/phase20_strategy_rework/*.json",
    "data/processed/phase21_hold_monitoring/*.json",
])

runtime_files = collect_files([
    "runtime/phase17*.json",
    "runtime/phase18*.json",
    "runtime/phase19*.json",
    "runtime/phase20*.json",
    "runtime/phase21*.json",
])

doc_files = collect_files([
    "docs/PHASE_17*.md",
    "docs/PHASE_18*.md",
    "docs/PHASE_19*.md",
    "docs/PHASE_20*.md",
    "docs/PHASE_21*.md",
])

archive_manifest = {
    "manifest_id": "phase22_project_hold_state_archive_manifest_v1",
    "created_at_unix": int(time.time()),
    "git_head": current_git_head,
    "archive_mode": "index_only_no_file_copy_no_execution",
    "system_state": "HOLD_RESEARCH_ONLY",
    "phase20_status": phase20_status,
    "phase21_status": phase21_status,
    "selected_phase21_next_action": selected_phase21_next_action,
    "evidence_file_count": len(evidence_files),
    "runtime_file_count": len(runtime_files),
    "documentation_file_count": len(doc_files),
    "evidence_files": [file_entry(p) for p in evidence_files],
    "runtime_files": [file_entry(p) for p in runtime_files],
    "documentation_files": [file_entry(p) for p in doc_files],
}

archive_index = {
    "index_id": "phase22_project_hold_state_evidence_index_v1",
    "created_at_unix": int(time.time()),
    "git_head": current_git_head,
    "system_state": "HOLD_RESEARCH_ONLY",
    "final_project_state": {
        "phase20_status": phase20_status,
        "phase21_status": "closed_final_remain_on_hold",
        "selected_phase21_next_action": selected_phase21_next_action,
        "monitoring_started": False,
        "run_dry_run_now": False,
        "run_backtest_now": False,
        "execution_allowed": False,
        "approved_for_execution": False,
       1",
    "created_at_unix": int(time.time()),
    "git_head": current_git_head,
    "system_state": "HOLD_RESEARCH_ONLY",
    "final_project_state": {
        "phase20_status": phase20_status,
        "phase21_status": "closed_final_remain_on_hold",
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
    "key_closeout_files": {
        "phase17": file_entry(PHASE17_CLOSEOUT),
        "phase18": file_entry(PHASE18_CLOSEOUT),
        "phase19": file_entry(PHASE19_CLOSEOUT),
        "phase20": file_entry(PHASE20_CLOSEOUT),
        "phase21": file_entry(PHASE21_FINAL)
    },
    "archive_manifest_file": "data/processed/phase22_project_archive/project_hold_state_archive_manifest.json"
}

archive_checks = {
    "safe_mode_active": safe_mode,
    "phase21_final_present": PHASE21_FINAL.exists(),
    "phase21_final_runtime_present": PHASE21_FINAL_RUNTIME.exists(),
    "phase21_final_file_present": PHASE21_FINAL_FILE.exists(),
    "phase20_closeout_present": PHASE20_CLOSEOUT.exists(),
    "phase20_closeout_file_present": PHASE20_CLOSEOUT_FILE.exists(),
    "phase21_final_safety_closeout_passed": final_safety_closeout_passed,
    "phase20_closeout_passed": phase20_closeout_passed,
    "phase20_status_closed_remain_on_hold": phase20_status == "closed_remain_on_hold",
    "phase21_status_closed_final_remain_on_hold": phase21_status == "closed_final_remain_on_hold",
    "selected_phase21_next_action_is_remain_on_hold": selected_phase21_next_action == "remain_on_hold",
    "evidence_files_indexed": len(evidence_files) > 0,
    "runtime_files_indexed": len(runtime_files) > 0,
    "documentation_files_indexed": len(doc_files) > 0,
    "monitoring_not_started": phase21.get("monitoring_started") is False,
    "run_dry_run_now_false": phase21.get("run_dry_run_now") is False,
    "run_backtest_now_false": phase21.get("run_backtest_now") is False,
    "execution_allowed_false": phase21.get("execution_allowed") is False,
    "approved_for_execution_false": phase21.get("approved_for_execution") is False,
    "approved_for_paper_shadow_false": phase21.get("approved_for_paper_shadow") is False,
    "approved_for_live_false": phase21.get("approved_for_live") is False,
    "paper_shadow_not_started": phase21.get("paper_shadow_started") is False,
    "paper_shadow_start_not_approved": phase21.get("approved_for_paper_shadow_start") is False,
    "exchange_order_submission_disabled": phase21.get("exchange_order_submission") is False,
    "micro_live_not_approved": phase21.get("approved_for_micro_live_execution") is False,
    "real_live_not_approved": phase21.get("approved_for_real_live_trading") is False,
}

blockers = [k for k, v in archive_checks.items() if v is not True]
archive_index_ready = all(archive_checks.values())

if archive_index_ready:
    decision = "PHASE_22_PROJECT_HOLD_STATE_ARCHIVE_AND_EVIDENCE_INDEX_CREATED_REMAIN_ON_HOLD_NOT_APPROVED_FOR_EXECUTION"
    next_phase = "Phase 22.2 — Project Hold State Archive Review"
else:
    decision = "PHASE_22_PROJECT_HOLD_STATE_ARCHIVE_AND_EVIDENCE_INDEX_BLOCKED_REVIEW_REQUIRED"
    next_phase = "Phase 22.2 — Project Archive Index Fix"

manifest_file = PHASE22_DIR / "project_hold_state_archive_manifest.json"
index_file = PHASE22_DIR / "project_hold_state_evidence_index.json"

archive_index["archive_checks"] = archive_checks
archive_index["blockers"] = blockers
archive_index["archive_index_ready"] = archive_index_ready
archive_index["decision"] = decision
archive_index["next_phase"] = next_phase

write_json(manifest_file, archive_manifest)
write_json(index_file, archive_index)

runtime_record = {
    "phase": "phase_22_1_project_hold_state_archive_and_evidence_index_record",
    "created_at_unix": int(time.time()),
    "git_head": current_git_head,
    "system_state": "HOLD_RESEARCH_ONLY",
    "phase20_status": phase20_status,
    "phase21_status": phase21_status,
    "selected_phase21_next_action": selected_phase21_next_action,
    "archive_index_ready": archive_index_ready,
    "archive_checks": archive_checks,
    "blockers": blockers,
    "manifest_file": str(manifest_file),
    "index_file": str(index_file),
    "evidence_file_count": len(evidence_files),
    "runtime_file_count": len(runtime_files),
    "documentation_file_count": len(doc_files),
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

write_json(RUNTIME_OUT, runtime_record)

report = {
    "phase": "phase_22_1_project_hold_state_archive_and_evidence_index",
    "generated_at_unix": int(time.time()),
    "scope": "archive_index_only_no_monitoring_no_dry_run_no_backtest_no_execution",
    "git_head": current_git_head,
    "safety_flags": flags,
    "safe_mode_active": safe_mode,
    "git_working_tree_clean": git_clean_before_outputs,
    "phase20_status": phase20_status,
    "phase21_status": phase21_status,
    "selected_phase21_next_action": selected_phase21_next_action,
    "archive_index_ready": archive_index_ready,
    "evidence_file_count": len(evidence_files),
    "runtime_file_count": len(runtime_files),
    "documentation_file_count": len(doc_files),
    "archive_checks": archive_checks,
    "blockers": blockers,
    "manifest_file": str(manifest_file),
    "index_file": str(index_file),
    "runtime_record_file": str(RUNTIME_OUT),
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
    "safety_notes": [
        "This phase creates a project hold-state archive index only.",
        "This phase does not copy secrets.",
        "This phase does not start monitoring jobs.",
        "This phase does not execute a dry run.",
        "This phase does not run a backtest.",
        "This phase does not start paper shadow execution.",
        "This phase does not approve micro-live execution.",
        "This phase does not approve real live trading.",
        "This phase does not submit exchange orders."
    ]
}

write_json(OUT, report)

print(f"Report written to: {OUT}")
print(f"Runtime record written to: {RUNTIME_OUT}")
print(f"Manifest written to: {manifest_file}")
print(f"Index written to: {index_file}")
print(f"safe_mode_active={safe_mode}")
print(f"archive_index_ready={archive_index_ready}")
print(f"phase20_status={phase20_status}")
print(f"phase21_status={phase21_status}")
print(f"selected_phase21_next_action={selected_phase21_next_action}")
print(f"evidence_file_count={len(evidence_files)}")
print(f"runtime_file_count={len(runtime_files)}")
print(f"documentation_file_count={len(doc_files)}")
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
