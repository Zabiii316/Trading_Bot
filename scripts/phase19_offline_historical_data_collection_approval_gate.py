import json, os, subprocess, time
from pathlib import Path

OUT = Path("data/processed/phase19_offline_historical_data_collection_approval_gate.json")
RUNTIME_OUT = Path("runtime/phase19_offline_historical_data_collection_approval_gate_state.json")
GATE_DIR = Path("data/processed/phase19_strategy_rework")

DRY_RUN_REPORT = Path("data/processed/phase19_offline_historical_data_collection_dry_run.json")
DRY_RUN_RUNTIME = Path("runtime/phase19_offline_historical_data_collection_dry_run_state.json")
DRY_RUN_RESULT = Path("data/processed/phase19_strategy_rework/offline_historical_data_collection_dry_run_result.json")
COLLECTION_CONFIG = Path("data/processed/phase19_strategy_rework/offline_historical_data_collection_config.json")
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

dry_run = load_json(DRY_RUN_REPORT)
dry_run_runtime = load_json(DRY_RUN_RUNTIME)
dry_run_result = load_json(DRY_RUN_RESULT)
collection_config = load_json(COLLECTION_CONFIG)
gap_plan = load_json(GAP_PLAN)
phase18_closeout = load_json(PHASE18_CLOSEOUT)

selected_option = (
    dry_run.get("selected_option")
    or dry_run_runtime.get("selected_option")
    or dry_run_result.get("selected_option")
    or gap_plan.get("selected_option")
    or phase18_closeout.get("selected_option")
)

selected_path = (
    dry_run.get("selected_phase19_path")
    or dry_run_runtime.get("selected_phase19_path")
    or dry_run_result.get("selected_phase19_path")
    or gap_plan.get("selected_phase19_path")
)

dry_run_passed = (
    dry_run.get("dry_run_passed") is True
    or dry_run_runtime.get("dry_run_passed") is True
    or dry_run_result.get("dry_run_passed") is True
)

phase18_closed_safely = phase18_closeout.get("phase18_closed_safely") is True
target_count = dry_run.get("target_count") or dry_run_result.get("target_count") or len(collection_config.get("targets", []))

manual_collection_approval_granted = False

gate_checks = {
    "safe_mode_active": safe_mode,
    "dry_run_report_present": DRY_RUN_REPORT.exists(),
    "dry_run_runtime_present": DRY_RUN_RUNTIME.exists(),
    "dry_run_result_present": DRY_RUN_RESULT.exists(),
    "collection_config_present": COLLECTION_CONFIG.exists(),
    "gap_plan_present": GAP_PLAN.exists(),
    "phase18_closeout_present": PHASE18_CLOSEOUT.exists(),
    "selected_option_is_remain_on_hold": selected_option == "remain_on_hold",
    "selected_path_is_data_expansion_first": selected_path == "historical_data_expansion_first_then_strategy_rework",
    "dry_run_passed": dry_run_passed,
    "collection_config_dry_run_only": collection_config.get("mode") == "dry_run_only",
    "download_currently_disabled": collection_config.get("download_now") is False,
    "network_download_currently_disabled": collection_config.get("network_download_allowed") is False,
    "execution_currently_disabled": collection_config.get("execution_allowed") is False,
    "phase18_closed_safely": phase18_closed_safely,
    "paper_shadow_not_started": dry_run.get("paper_shadow_started") is False,
    "paper_shadow_start_not_approved": dry_run.get("approved_for_paper_shadow_start") is False,
    "exchange_order_submission_disabled": dry_run.get("exchange_order_submission") is False,
    "micro_live_not_approved": dry_run.get("approved_for_micro_live_execution") is False,
    "real_live_not_approved": dry_run.get("approved_for_real_live_trading") is False,
}

blockers = [k for k, v in gate_checks.items() if v is not True]
approval_gate_ready = all(gate_checks.values())

if approval_gate_ready:
    decision = "PHASE_19_OFFLINE_HISTORICAL_DATA_COLLECTION_APPROVAL_GATE_CREATED_NOT_APPROVED_FOR_COLLECTION"
    next_phase = "Phase 19.10 — Offline Historical Data Collection Manual Approval Record"
else:
    decision = "PHASE_19_OFFLINE_HISTORICAL_DATA_COLLECTION_APPROVAL_GATE_BLOCKED_REVIEW_REQUIRED"
    next_phase = "Phase 19.10 — Offline Historical Data Collection Approval Gate Review"

GATE_DIR.mkdir(parents=True, exist_ok=True)

approval_template = {
    "phase": "phase_19_9_offline_historical_data_collection_manual_approval_template",
    "created_at_unix": int(time.time()),
    "manual_collection_approval_granted": False,
    "approved_by": None,
    "approved_at_unix": None,
    "approval_scope": "offline_historical_data_collection_or_import_only",
    "target_count": target_count,
    "download_allowed": False,
    "network_download_allowed": False,
    "execution_allowed": False,
    "paper_shadow_allowed": False,
    "live_trading_allowed": False,
    "exchange_order_submission_allowed": False,
    "real_capital_allowed": False,
    "required_manual_fields_before_collection": [
        "approved_by",
        "approved_at_unix",
        "approved_target_symbols",
        "approved_timeframes",
        "approved_source",
        "approval_note"
    ],
    "safety_note": "This template is not an approval. It must be manually reviewed before any offline data collection or import."
}

gate_record = {
    "phase": "phase_19_9_offline_historical_data_collection_approval_gate_record",
    "created_at_unix": int(time.time()),
    "git_head": current_git_head,
    "system_state": "HOLD",
    "selected_option": selected_option,
    "selected_phase19_path": selected_path,
    "approval_gate_ready": approval_gate_ready,
    "manual_collection_approval_granted": manual_collection_approval_granted,
    "gate_checks": gate_checks,
    "blockers": blockers,
    "target_count": target_count,
    "download_allowed": False,
    "network_download_allowed": False,
    "execution_allowed": False,
    "paper_shadow_started": False,
    "approved_for_paper_shadow_start": False,
    "exchange_order_submission": False,
    "real_capital_allowed": False,
    "live_trading_enabled": False,
    "approved_for_micro_live_execution": False,
    "approved_for_real_live_trading": False,
    "decision": decision,
    "next_phase": next_phase
}

gate_file = GATE_DIR / "offline_historical_data_collection_approval_gate.json"
approval_template_file = GATE_DIR / "offline_historical_data_collection_manual_approval_template.json"

write_json(gate_file, gate_record)
write_json(approval_template_file, approval_template)
write_json(RUNTIME_OUT, gate_record)

report = {
    "phase": "phase_19_9_offline_historical_data_collection_approval_gate",
    "generated_at_unix": int(time.time()),
    "scope": "approval_gate_only_no_collection_no_download_no_execution",
    "git_head": current_git_head,
    "safety_flags": flags,
    "safe_mode_active": safe_mode,
    "git_working_tree_clean": git_clean_before_outputs,
    "selected_option": selected_option,
    "selected_phase19_path": selected_path,
    "approval_gate_ready": approval_gate_ready,
    "manual_collection_approval_granted": manual_collection_approval_granted,
    "gate_checks": gate_checks,
    "blockers": blockers,
    "target_count": target_count,
    "gate_file": str(gate_file),
    "approval_template_file": str(approval_template_file),
    "runtime_gate_file": str(RUNTIME_OUT),
    "download_allowed": False,
    "network_download_allowed": False,
    "execution_allowed": False,
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
        "This phase creates an offline data collection approval gate only.",
        "This phase does not approve historical data download.",
        "This phase does not download market data.",
        "This phase does not start paper shadow execution.",
        "This phase does not approve micro-live execution.",
        "This phase does not approve real live trading.",
        "This phase does not submit Binance orders.",
        "Real capital and exchange order submission remain disabled."
    ]
}

write_json(OUT, report)

print(f"Report written to: {OUT}")
print(f"Runtime gate written to: {RUNTIME_OUT}")
print(f"Gate file written to: {gate_file}")
print(f"Approval template written to: {approval_template_file}")
print(f"safe_mode_active={safe_mode}")
print(f"selected_option={selected_option}")
print(f"selected_phase19_path={selected_path}")
print(f"approval_gate_ready={approval_gate_ready}")
print(f"manual_collection_approval_granted={manual_collection_approval_granted}")
print(f"target_count={target_count}")
print("download_allowed=False")
print("network_download_allowed=False")
print("execution_allowed=False")
print("paper_shadow_started=False")
print("approved_for_paper_shadow_start=False")
print("exchange_order_submission=False")
print("approved_for_micro_live_execution=False")
print("approved_for_real_live_trading=False")
print(f"decision={decision}")
