import json, os, subprocess, time, hashlib
from pathlib import Path

OUT = Path("data/processed/phase22_project_final_evidence_seal.json")
RUNTIME_OUT = Path("runtime/phase22_project_final_evidence_seal_state.json")
PHASE22_DIR = Path("data/processed/phase22_project_archive")

FINAL_CLOSEOUT = Path("data/processed/phase22_project_final_hold_state_closeout.json")
FINAL_CLOSEOUT_RUNTIME = Path("runtime/phase22_project_final_hold_state_closeout_state.json")
FINAL_CLOSEOUT_FILE = Path("data/processed/phase22_project_archive/project_final_hold_state_closeout.json")

FINAL_SUMMARY = Path("data/processed/phase22_project_hold_state_final_summary.json")
ARCHIVE_CLOSEOUT = Path("data/processed/phase22_project_hold_state_archive_safety_closeout.json")
ARCHIVE_MANIFEST = Path("data/processed/phase22_project_archive/project_hold_state_archive_manifest.json")
ARCHIVE_INDEX = Path("data/processed/phase22_project_archive/project_hold_state_evidence_index.json")
PHASE21_FINAL = Path("data/processed/phase21_post_strategy_rework_hold_monitoring_final_safety_closeout.json")
PHASE20_CLOSEOUT = Path("data/processed/phase20_strategy_rework_safety_closeout.json")

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

def sha256(path):
    if not path.exists():
        return None
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def entry(path):
    return {
        "path": str(path),
        "exists": path.exists(),
        "size_bytes": path.stat().st_size if path.exists() else 0,
        "sha256": sha256(path) if path.exists() else None,
    }

def collect(patterns):
    files, seen = [], set()
    for pattern in patterns:
        for p in sorted(Path(".").glob(pattern)):
            if p.is_file() and str(p) not in seen:
                files.append(p)
                seen.add(str(p))
    return files

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

closeout = load_json(FINAL_CLOSEOUT)
closeout_runtime = load_json(FINAL_CLOSEOUT_RUNTIME)
closeout_file = load_json(FINAL_CLOSEOUT_FILE)
manifest = load_json(ARCHIVE_MANIFEST)

final_closeout_passed = (
    closeout.get("final_hold_state_closeout_passed") is True
    or closeout_runtime.get("final_hold_state_closeout_passed") is True
    or closeout_file.get("final_hold_state_closeout_passed") is True
)

project_status = closeout.get("project_status") or closeout_file.get("project_status")
phase20_status = closeout.get("phase20_status") or closeout_file.get("phase20_status")
phase21_status = closeout.get("phase21_status") or closeout_file.get("phase21_status")
phase22_status = closeout.get("phase22_status") or closeout_file.get("phase22_status")
selected_phase21_next_action = closeout.get("selected_phase21_next_action") or closeout_file.get("selected_phase21_next_action")

evidence_files = collect([
    "data/processed/phase17*.json",
    "data/processed/phase18*.json",
    "data/processed/phase19*.json",
    "data/processed/phase20*.json",
    "data/processed/phase21*.json",
    "data/processed/phase22*.json",
    "data/processed/phase20_strategy_rework/*.json",
    "data/processed/phase21_hold_monitoring/*.json",
    "data/processed/phase22_project_archive/*.json",
])

runtime_files = collect([
    "runtime/phase17*.json",
    "runtime/phase18*.json",
    "runtime/phase19*.json",
    "runtime/phase20*.json",
    "runtime/phase21*.json",
    "runtime/phase22*.json",
])

doc_files = collect([
    "docs/PHASE_17*.md",
    "docs/PHASE_18*.md",
    "docs/PHASE_19*.md",
    "docs/PHASE_20*.md",
    "docs/PHASE_21*.md",
    "docs/PHASE_22*.md",
])

seal_checks = {
    "safe_mode_active": safe_mode,
    "final_closeout_present": FINAL_CLOSEOUT.exists(),
    "final_closeout_runtime_present": FINAL_CLOSEOUT_RUNTIME.exists(),
    "final_closeout_file_present": FINAL_CLOSEOUT_FILE.exists(),
    "final_summary_present": FINAL_SUMMARY.exists(),
    "archive_closeout_present": ARCHIVE_CLOSEOUT.exists(),
    "archive_manifest_present": ARCHIVE_MANIFEST.exists(),
    "archive_index_present": ARCHIVE_INDEX.exists(),
    "phase21_final_present": PHASE21_FINAL.exists(),
    "phase20_closeout_present": PHASE20_CLOSEOUT.exists(),
    "final_hold_state_closeout_passed": final_closeout_passed,
    "project_status_remain_on_hold": project_status == "remain_on_hold_not_approved_for_execution",
    "phase20_status_closed_remain_on_hold": phase20_status == "closed_remain_on_hold",
    "phase21_status_closed_final_remain_on_hold": phase21_status == "closed_final_remain_on_hold",
    "phase22_status_project_final_closeout": phase22_status == "project_final_hold_state_closeout_complete",
    "selected_phase21_next_action_is_remain_on_hold": selected_phase21_next_action == "remain_on_hold",
    "evidence_files_sealed": len(evidence_files) > 0,
    "runtime_files_sealed": len(runtime_files) > 0,
    "documentation_files_sealed": len(doc_files) > 0,
    "monitoring_not_started": closeout.get("monitoring_started") is False,
    "run_dry_run_now_false": closeout.get("run_dry_run_now") is False,
    "run_backtest_now_false": closeout.get("run_backtest_now") is False,
    "execution_allowed_false": closeout.get("execution_allowed") is False,
    "approved_for_execution_false": closeout.get("approved_for_execution") is False,
    "approved_for_paper_shadow_false": closeout.get("approved_for_paper_shadow") is False,
    "approved_for_live_false": closeout.get("approved_for_live") is False,
    "paper_shadow_not_started": closeout.get("paper_shadow_started") is False,
    "paper_shadow_start_not_approved": closeout.get("approved_for_paper_shadow_start") is False,
    "exchange_order_submission_disabled": closeout.get("exchange_order_submission") is False,
    "micro_live_not_approved": closeout.get("approved_for_micro_live_execution") is False,
    "real_live_not_approved": closeout.get("approved_for_real_live_trading") is False,
}

blockers = [k for k, v in seal_checks.items() if v is not True]
final_evidence_seal_ready = all(seal_checks.values())

if final_evidence_seal_ready:
    decision = "PHASE_22_PROJECT_FINAL_EVIDENCE_SEAL_CREATED_REMAIN_ON_HOLD_NOT_APPROVED_FOR_EXECUTION"
    next_phase = "Phase 22.8 — Project Final Evidence Seal Review"
else:
    decision = "PHASE_22_PROJECT_FINAL_EVIDENCE_SEAL_FAILED_REVIEW_REQUIRED"
    next_phase = "Phase 22.8 — Project Final Evidence Seal Fix"

seal_file = PHASE22_DIR / "project_final_evidence_seal.json"

seal_record = {
    "phase": "phase_22_7_project_final_evidence_seal_record",
    "created_at_unix": int(time.time()),
    "git_head": git_head_value,
    "system_state": "HOLD_RESEARCH_ONLY",
    "project_status": "remain_on_hold_not_approved_for_execution",
    "phase20_status": phase20_status,
    "phase21_status": phase21_status,
    "phase22_status": "final_evidence_seal_created",
    "selected_phase21_next_action": selected_phase21_next_action,
    "final_evidence_seal_ready": final_evidence_seal_ready,
    "seal_checks": seal_checks,
    "blockers": blockers,
    "evidence_file_count": len(evidence_files),
    "runtime_file_count": len(runtime_files),
    "documentation_file_count": len(doc_files),
    "sealed_evidence_files": [entry(p) for p in evidence_files],
    "sealed_runtime_files": [entry(p) for p in runtime_files],
    "sealed_documentation_files": [entry(p) for p in doc_files],
    "previous_manifest_counts": {
        "evidence_file_count": manifest.get("evidence_file_count"),
        "runtime_file_count": manifest.get("runtime_file_count"),
        "documentation_file_count": manifest.get("documentation_file_count"),
    },
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
    "phase": "phase_22_7_project_final_evidence_seal",
    "generated_at_unix": int(time.time()),
    "scope": "final_evidence_seal_only_no_monitoring_no_dry_run_no_backtest_no_execution",
    "git_head": git_head_value,
    "safety_flags": flags,
    "safe_mode_active": safe_mode,
    "git_working_tree_clean": git_clean_value,
    "project_status": "remain_on_hold_not_approved_for_execution",
    "phase20_status": phase20_status,
    "phase21_status": phase21_status,
    "phase22_status": "final_evidence_seal_created",
    "selected_phase21_next_action": selected_phase21_next_action,
    "final_evidence_seal_ready": final_evidence_seal_ready,
    "evidence_file_count": len(evidence_files),
    "runtime_file_count": len(runtime_files),
    "documentation_file_count": len(doc_files),
    "seal_checks": seal_checks,
    "blockers": blockers,
    "seal_file": str(seal_file),
    "runtime_seal_file": str(RUNTIME_OUT),
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

write_json(seal_file, seal_record)
write_json(RUNTIME_OUT, seal_record)
write_json(OUT, report)

print(f"Report written to: {OUT}")
print(f"Runtime seal written to: {RUNTIME_OUT}")
print(f"Seal file written to: {seal_file}")
print(f"safe_mode_active={safe_mode}")
print(f"final_evidence_seal_ready={final_evidence_seal_ready}")
print("project_status=remain_on_hold_not_approved_for_execution")
print(f"phase20_status={phase20_status}")
print(f"phase21_status={phase21_status}")
print("phase22_status=final_evidence_seal_created")
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
