import json, os, subprocess, time
from pathlib import Path

OUT = Path("data/processed/phase19_offline_historical_data_collection_safety_closeout.json")
RUNTIME_OUT = Path("runtime/phase19_offline_historical_data_collection_safety_closeout_state.json")
CLOSEOUT_DIR = Path("data/processed/phase19_strategy_rework")

CONSOLIDATION = Path("data/processed/phase19_offline_historical_data_collection_hold_state_consolidation.json")
CONSOLIDATION_RUNTIME = Path("runtime/phase19_offline_historical_data_collection_hold_state_consolidation_state.json")
DECISION_REVIEW = Path("data/processed/phase19_offline_historical_data_collection_manual_approval_decision_review.json")
DECISION_POINT = Path("data/processed/phase19_offline_historical_data_collection_manual_approval_decision_point.json")
BLOCKED_REVIEW = Path("data/processed/phase19_offline_historical_data_collection_blocked_start_review.json")
START_GATE = Path("data/processed/phase19_offline_historical_data_collection_start_gate.json")
MANUAL_RECORD = Path("data/processed/phase19_offline_historical_data_collection_manual_approval_record.json")
APPROVAL_GATE = Path("data/processed/phase19_offline_historical_data_collection_approval_gate.json")
DRY_RUN = Path("data/processed/phase19_offline_historical_data_collection_dry_run.json")
GAP_PLAN = Path("data/processed/phase19_historical_data_gap_fill_plan.json")
PHASE18_CLOSEOUT = Path("data/processed/phase18_final_safety_closeout.json")

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
current_git_head = git_head()
git_clean_before_outputs = git_clean()

consolidation = load_json(CONSOLIDATION)
consolidation_runtime = load_json(CONSOLIDATION_RUNTIME)
decision_review = load_json(DECISION_REVIEW)
decision_point = load_json(DECISION_POINT)
blocked_review = load_json(BLOCKED_REVIEW)
start_gate = load_json(START_GATE)
manual_record = load_json(MANUAL_RECORD)
approval_gate = load_json(APPROVAL_GATE)
dry_run = load_json(DRY_RUN)
gap_plan = load_json(GAP_PLAN)
phase18_closeout = load_json(PHASE18_CLOSEOUT)

selected_option = (
    consolidation.get("selected_option")
    or consolidation_runtime.get("selected_option")
    or decision_review.get("selected_option")
    or decision_point.get("selected_option")
    or start_gate.get("selected_option")
    or phase18_closeout.get("selected_option")
)

selected_path = (
    consolidation.get("selected_phase19_path")
    or consolidation_runtime.get("selected_phase19_path")
    or decision_review.get("selected_phase19_path")
    or decision_point.get("selected_phase19_path")
    or start_gate.get("selected_phase19_path")
)

hold_state_consolidated = (
    consolidation.get("hold_state_consolidated") is True
    or consolidation_runtime.get("hold_state_consolidated") is True
)

decision_review_passed = decision_review.get("decision_review_passed") is True
decision_point_ready = decision_point.get("decision_point_ready") is True
blocked_start_review_passed = blocked_review.get("blocked_start_review_passed") is True
start_gate_ready = start_gate.get("start_gate_ready") is True
approval_record_ready = manual_record.get("approval_record_ready") is True
approval_gate_ready = approval_gate.get("approval_gate_ready") is True
dry_run_passed = dry_run.get("dry_run_passed") is True
gap_fill_plan_ready = gap_plan.get("gap_fill_plan_ready") is True
phase18_closed_safely = phase18_closeout.get("phase18_closed_safely") is True

manual_collection_approval_granted = False
collection_start_allowed = False
download_allowed = False
network_download_allowed = False
execution_allowed = False

target_count = (
    consolidation.get("target_count")
    or decision_review.get("target_count")
    or decision_point.get("target_count")
    or blocked_review.get("target_count")
    or start_gate.get("target_count")
    or manual_record.get("target_count")
    or approval_gate.get("target_count")
    or dry_run.get("target_count")
    or 0
)

closeout_checks = {
    "safe_mode_active": safe_mode,
    "consolidation_present": CONSOLIDATION.exists(),
    "consolidation_runtime_present": CONSOLIDATION_RUNTIME.exists(),
    "decision_review_present": DECISION_REVIEW.exists(),
    "decision_point_present": DECISION_POINT.exists(),
    "blocked_review_present": BLOCKED_REVIEW.exists(),
    "start_gate_present": START_GATE.exists(),
    "manual_record_present": MANUAL_RECORD.exists(),
    "approval_gate_present": APPROVAL_GATE.exists(),
    "dry_run_present": DRY_RUN.exists(),
    "gap_plan_present": GAP_PLAN.exists(),
    "phase18_closeout_present": PHASE18_CLOSEOUT.exists(),
    "selected_option_is_remain_on_hold": selected_option == "remain_on_hold",
    "selected_path_is_data_expansion_first": selected_path == "historical_data_expansion_first_then_strategy_rework",
    "hold_state_consolidated": hold_state_consolidated,
    "decision_review_passed": decision_review_passed,
    "decision_point_ready": decision_point_ready,
    "blocked_start_review_passed": blocked_start_review_passed,
    "start_gate_ready": start_gate_ready,
    "approval_record_ready": approval_record_ready,
    "approval_gate_ready": approval_gate_ready,
    "dry_run_passed": dry_run_passed,
    "gap_fill_plan_ready": gap_fill_plan_ready,
    "phase18_closed_safely": phase18_closed_safely,
    "manual_collection_approval_not_granted": manual_collection_approval_granted is False,
    "collection_start_blocked": collection_start_allowed is False,
    "download_blocked": download_allowed is False,
    "network_download_blocked": network_download_allowed is False,
    "execution_blocked": execution_allowed is False,
    "paper_shadow_not_started": consolidation.get("paper_shadow_started") is False,
    "paper_shadow_start_not_approved": consolidation.get("approved_for_paper_shadow_start") is False,
    "exchange_order_submission_disabled": consolidation.get("exchange_order_submission") is False,
    "micro_live_not_approved": consolidation.get("approved_for_micro_live_execution") is False,
    "real_live_not_approved": consolidation.get("approved_for_real_live_trading") is False,
}

blockers = [k for k, v in closeout_checks.items() if v is not True]
collection_safety_closeout_passed = all(closeout_checks.values())

if collection_safety_closeout_passed:
    decision = "PHASE_19_OFFLINE_HISTORICAL_DATA_COLLECTION_SAFETY_CLOSEOUT_COMPLETE_COLLECTION_NOT_APPROVED"
    next_phase = "Phase 19.17 — Historical Data Expansion Next Action Options"
else:
    decision = "PHASE_19_OFFLINE_HISTORICAL_DATA_COLLECTION_SAFETY_CLOSEOUT_FAILED_REVIEW_REQUIRED"
    next_phase = "Phase 19.17 — Offline Collection Safety Closeout Fix"

CLOSEOUT_DIR.mkdir(parents=True, exist_ok=True)

closeout_record = {
    "phase": "phase_19_16_offline_historical_data_collection_safety_closeout_record",
    "created_at_unix": int(time.time()),
    "git_head": current_git_head,
    "system_state": "HOLD",
    "selected_option": selected_option,
    "selected_phase19_path": selected_path,
    "collection_safety_closeout_passed": collection_safety_closeout_passed,
    "manual_collection_approval_granted": False,
    "collection_start_allowed": False,
    "download_allowed": False,
    "network_download_allowed": False,
    "execution_allowed": False,
    "target_count": target_count,
    "closeout_checks": closeout_checks,
    "blockers": blockers,
    "final_collection_state": {
        "offline_collection_state": "closed_blocked_manual_approval_required",
        "manual_collection_approval_granted": False,
        "collection_start_allowed": False,
        "download_allowed": False,
        "network_download_allowed": False,
        "execution_allowed": False,
        "paper_shadow_started": False,
        "approved_for_paper_shadow_start": False,
        "exchange_order_submission": False,
        "real_capital_allowed": False,
        "live_trading_enabled": False,
        "approved_for_micro_live_execution": False,
        "approved_for_real_live_trading": False
    },
    "allowed_next_actions": [
        "historical_data_expansion_next_action_review",
        "manual_data_source_review_only",
        "manual_approval_process_review_only",
        "documentation_only"
    ],
    "blocked_actions": [
        "historical_data_download",
        "historical_data_import",
        "paper_shadow_start",
        "micro_live_execution",
        "real_live_trading",
        "exchange_order_submission",
        "real_capital_usage",
        "production_api_key_usage"
    ],
    "decision": decision,
    "next_phase": next_phase
}

closeout_file = CLOSEOUT_DIR / "offline_historical_data_collection_safety_closeout.json"

write_json(closeout_file, closeout_record)
write_json(RUNTIME_OUT, closeout_record)

report = {
    "phase": "phase_19_16_offline_historical_data_collection_safety_closeout",
    "generated_at_unix": int(time.time()),
    "scope": "collection_safety_closeout_only_no_collection_no_download_no_execution",
    "git_head": current_git_head,
    "safety_flags": flags,
    "safe_mode_active": safe_mode,
    "git_working_tree_clean": git_clean_before_outputs,
    "selected_option": selected_option,
    "selected_phase19_path": selected_path,
    "collection_safety_closeout_passed": collection_safety_closeout_passed,
    "manual_collection_approval_granted": False,
    "collection_start_allowed": False,
    "download_allowed": False,
    "network_download_allowed": False,
    "execution_allowed": False,
    "target_count": target_count,
    "closeout_checks": closeout_checks,
    "blockers": blockers,
    "closeout_file": str(closeout_file),
    "runtime_closeout_file": str(RUNTIME_OUT),
    "paper_shadow_started": False,
    "approved_for_paper_shadow_start": False,
    "exchange_order_submission": False,
    "real_capital_allowed": False,
    "live_trading_enabled": False,
    "approved_for_micro_live_execution": False,
    "approved_for_real_live_trading": False,
    "decision": decision,
    "next_phase": next_phase,
    "safety_notes": [
        "This phase safely closes the offline historical data collection branch.",
        "Manual collection approval remains false.",
        "This phase does not approve historical data download.",
        "This phase does not import historical data.",
        "This phase does not start paper shadow execution.",
        "This phase does not approve micro-live execution.",
        "This phase does not approve real live trading.",
        "This phase does not submit Binance orders.",
        "Real capital and exchange order submission remain disabled."
    ]
}

write_json(OUT, report)

print(f"Report written to: {OUT}")
print(f"Runtime closeout written to: {RUNTIME_OUT}")
print(f"Closeout file written to: {closeout_file}")
print(f"safe_mode_active={safe_mode}")
print(f"selected_option={selected_option}")
print(f"selected_phase19_path={selected_path}")
print(f"collection_safety_closeout_passed={collection_safety_closeout_passed}")
print("manual_collection_approval_granted=False")
print("collection_start_allowed=False")
print("download_allowed=False")
print("network_download_allowed=False")
print("execution_allowed=False")
print("paper_shadow_started=False")
print("approved_for_paper_shadow_start=False")
print("exchange_order_submission=False")
print("approved_for_micro_live_execution=False")
print("approved_for_real_live_trading=False")
print(f"decision={decision}")
