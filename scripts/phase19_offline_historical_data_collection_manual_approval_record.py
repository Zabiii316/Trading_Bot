import json, os, subprocess, time
from pathlib import Path

OUT = Path("data/processed/phase19_offline_historical_data_collection_manual_approval_record.json")
RUNTIME_OUT = Path("runtime/phase19_offline_historical_data_collection_manual_approval_record_state.json")
RECORD_DIR = Path("data/processed/phase19_strategy_rework")

APPROVAL_GATE_REPORT = Path("data/processed/phase19_offline_historical_data_collection_approval_gate.json")
APPROVAL_GATE_RUNTIME = Path("runtime/phase19_offline_historical_data_collection_approval_gate_state.json")
APPROVAL_GATE_FILE = Path("data/processed/phase19_strategy_rework/offline_historical_data_collection_approval_gate.json")
APPROVAL_TEMPLATE = Path("data/processed/phase19_strategy_rework/offline_historical_data_collection_manual_approval_template.json")
COLLECTION_CONFIG = Path("data/processed/phase19_strategy_rework/offline_historical_data_collection_config.json")
DRY_RUN_REPORT = Path("data/processed/phase19_offline_historical_data_collection_dry_run.json")
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

gate_report = load_json(APPROVAL_GATE_REPORT)
gate_runtime = load_json(APPROVAL_GATE_RUNTIME)
gate_file = load_json(APPROVAL_GATE_FILE)
template = load_json(APPROVAL_TEMPLATE)
collection_config = load_json(COLLECTION_CONFIG)
dry_run = load_json(DRY_RUN_REPORT)
phase18_closeout = load_json(PHASE18_CLOSEOUT)

selected_option = (
    gate_report.get("selected_option")
    or gate_runtime.get("selected_option")
    or gate_file.get("selected_option")
    or dry_run.get("selected_option")
    or phase18_closeout.get("selected_option")
)

selected_path = (
    gate_report.get("selected_phase19_path")
    or gate_runtime.get("selected_phase19_path")
    or gate_file.get("selected_phase19_path")
    or dry_run.get("selected_phase19_path")
)

approval_gate_ready = (
    gate_report.get("approval_gate_ready") is True
    or gate_runtime.get("approval_gate_ready") is True
    or gate_file.get("approval_gate_ready") is True
)

dry_run_passed = dry_run.get("dry_run_passed") is True
phase18_closed_safely = phase18_closeout.get("phase18_closed_safely") is True

target_count = (
    gate_report.get("target_count")
    or gate_runtime.get("target_count")
    or gate_file.get("target_count")
    or template.get("target_count")
    or len(collection_config.get("targets", []))
)

manual_collection_approval_granted = False

approval_record_checks = {
    "safe_mode_active": safe_mode,
    "approval_gate_report_present": APPROVAL_GATE_REPORT.exists(),
    "approval_gate_runtime_present": APPROVAL_GATE_RUNTIME.exists(),
    "approval_gate_file_present": APPROVAL_GATE_FILE.exists(),
    "approval_template_present": APPROVAL_TEMPLATE.exists(),
    "collection_config_present": COLLECTION_CONFIG.exists(),
    "dry_run_report_present": DRY_RUN_REPORT.exists(),
    "phase18_closeout_present": PHASE18_CLOSEOUT.exists(),
    "selected_option_is_remain_on_hold": selected_option == "remain_on_hold",
    "selected_path_is_data_expansion_first": selected_path == "historical_data_expansion_first_then_strategy_rework",
    "approval_gate_ready": approval_gate_ready,
    "dry_run_passed": dry_run_passed,
    "phase18_closed_safely": phase18_closed_safely,
    "manual_collection_approval_not_granted": manual_collection_approval_granted is False,
    "download_not_allowed": gate_report.get("download_allowed") is False,
    "network_download_not_allowed": gate_report.get("network_download_allowed") is False,
    "execution_not_allowed": gate_report.get("execution_allowed") is False,
    "paper_shadow_not_started": gate_report.get("paper_shadow_started") is False,
    "paper_shadow_start_not_approved": gate_report.get("approved_for_paper_shadow_start") is False,
    "exchange_order_submission_disabled": gate_report.get("exchange_order_submission") is False,
    "micro_live_not_approved": gate_report.get("approved_for_micro_live_execution") is False,
    "real_live_not_approved": gate_report.get("approved_for_real_live_trading") is False,
}

blockers = [k for k, v in approval_record_checks.items() if v is not True]
approval_record_ready = all(approval_record_checks.values())

if approval_record_ready:
    decision = "PHASE_19_OFFLINE_HISTORICAL_DATA_COLLECTION_MANUAL_APPROVAL_RECORDED_NOT_APPROVED_FOR_COLLECTION"
    next_phase = "Phase 19.11 — Offline Historical Data Collection Start Gate"
else:
    decision = "PHASE_19_OFFLINE_HISTORICAL_DATA_COLLECTION_MANUAL_APPROVAL_RECORD_BLOCKED_REVIEW_REQUIRED"
    next_phase = "Phase 19.11 — Offline Historical Data Collection Manual Approval Review"

RECORD_DIR.mkdir(parents=True, exist_ok=True)

manual_record = {
    "phase": "phase_19_10_offline_historical_data_collection_manual_approval_record",
    "created_at_unix": int(time.time()),
    "git_head": current_git_head,
    "system_state": "HOLD",
    "selected_option": selected_option,
    "selected_phase19_path": selected_path,
    "approval_record_ready": approval_record_ready,
    "manual_collection_approval_granted": False,
    "approved_by": None,
    "approved_at_unix": None,
    "approval_scope": "offline_historical_data_collection_or_import_only",
    "target_count": target_count,
    "approval_record_checks": approval_record_checks,
    "blockers": blockers,
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
    "allowed_actions": [
        "manual_review_only",
        "approval_template_review_only",
        "documentation_only"
    ],
    "decision": decision,
    "next_phase": next_phase
}

record_file = RECORD_DIR / "offline_historical_data_collection_manual_approval_record.json"

write_json(record_file, manual_record)
write_json(RUNTIME_OUT, manual_record)

report = {
    "phase": "phase_19_10_offline_historical_data_collection_manual_approval_record",
    "generated_at_unix": int(time.time()),
    "scope": "manual_approval_record_only_no_collection_no_download_no_execution",
    "git_head": current_git_head,
    "safety_flags": flags,
    "safe_mode_active": safe_mode,
    "git_working_tree_clean": git_clean_before_outputs,
    "selected_option": selected_option,
    "selected_phase19_path": selected_path,
    "approval_record_ready": approval_record_ready,
    "manual_collection_approval_granted": False,
    "target_count": target_count,
    "approval_record_checks": approval_record_checks,
    "blockers": blockers,
    "record_file": str(record_file),
    "runtime_record_file": str(RUNTIME_OUT),
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
        "This phase records that manual offline data collection approval has not been granted.",
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
print(f"Runtime record written to: {RUNTIME_OUT}")
print(f"Manual record written to: {record_file}")
print(f"safe_mode_active={safe_mode}")
print(f"selected_option={selected_option}")
print(f"selected_phase19_path={selected_path}")
print(f"approval_record_ready={approval_record_ready}")
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
