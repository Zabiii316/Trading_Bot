import json, os, subprocess, time
from pathlib import Path

OUT = Path("data/processed/phase19_offline_historical_data_collection_start_gate.json")
RUNTIME_OUT = Path("runtime/phase19_offline_historical_data_collection_start_gate_state.json")
GATE_DIR = Path("data/processed/phase19_strategy_rework")

MANUAL_RECORD_REPORT = Path("data/processed/phase19_offline_historical_data_collection_manual_approval_record.json")
MANUAL_RECORD_RUNTIME = Path("runtime/phase19_offline_historical_data_collection_manual_approval_record_state.json")
MANUAL_RECORD_FILE = Path("data/processed/phase19_strategy_rework/offline_historical_data_collection_manual_approval_record.json")
APPROVAL_GATE_REPORT = Path("data/processed/phase19_offline_historical_data_collection_approval_gate.json")
DRY_RUN_REPORT = Path("data/processed/phase19_offline_historical_data_collection_dry_run.json")
COLLECTION_CONFIG = Path("data/processed/phase19_strategy_rework/offline_historical_data_collection_config.json")
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

manual_report = load_json(MANUAL_RECORD_REPORT)
manual_runtime = load_json(MANUAL_RECORD_RUNTIME)
manual_file = load_json(MANUAL_RECORD_FILE)
approval_gate = load_json(APPROVAL_GATE_REPORT)
dry_run = load_json(DRY_RUN_REPORT)
collection_config = load_json(COLLECTION_CONFIG)
phase18_closeout = load_json(PHASE18_CLOSEOUT)

selected_option = (
    manual_report.get("selected_option")
    or manual_runtime.get("selected_option")
    or manual_file.get("selected_option")
    or approval_gate.get("selected_option")
    or dry_run.get("selected_option")
    or phase18_closeout.get("selected_option")
)

selected_path = (
    manual_report.get("selected_phase19_path")
    or manual_runtime.get("selected_phase19_path")
    or manual_file.get("selected_phase19_path")
    or approval_gate.get("selected_phase19_path")
    or dry_run.get("selected_phase19_path")
)

approval_record_ready = (
    manual_report.get("approval_record_ready") is True
    or manual_runtime.get("approval_record_ready") is True
    or manual_file.get("approval_record_ready") is True
)

approval_gate_ready = approval_gate.get("approval_gate_ready") is True
dry_run_passed = dry_run.get("dry_run_passed") is True
phase18_closed_safely = phase18_closeout.get("phase18_closed_safely") is True

manual_collection_approval_granted = (
    manual_report.get("manual_collection_approval_granted") is True
    or manual_runtime.get("manual_collection_approval_granted") is True
    or manual_file.get("manual_collection_approval_granted") is True
)

collection_start_allowed = False
download_allowed = False
network_download_allowed = False
execution_allowed = False

target_count = (
    manual_report.get("target_count")
    or manual_runtime.get("target_count")
    or manual_file.get("target_count")
    or approval_gate.get("target_count")
    or dry_run.get("target_count")
    or len(collection_config.get("targets", []))
)

start_gate_checks = {
    "safe_mode_active": safe_mode,
    "manual_record_report_present": MANUAL_RECORD_REPORT.exists(),
    "manual_record_runtime_present": MANUAL_RECORD_RUNTIME.exists(),
    "manual_record_file_present": MANUAL_RECORD_FILE.exists(),
    "approval_gate_report_present": APPROVAL_GATE_REPORT.exists(),
    "dry_run_report_present": DRY_RUN_REPORT.exists(),
    "collection_config_present": COLLECTION_CONFIG.exists(),
    "phase18_closeout_present": PHASE18_CLOSEOUT.exists(),
    "selected_option_is_remain_on_hold": selected_option == "remain_on_hold",
    "selected_path_is_data_expansion_first": selected_path == "historical_data_expansion_first_then_strategy_rework",
    "approval_record_ready": approval_record_ready,
    "approval_gate_ready": approval_gate_ready,
    "dry_run_passed": dry_run_passed,
    "phase18_closed_safely": phase18_closed_safely,
    "manual_collection_approval_not_granted": manual_collection_approval_granted is False,
    "collection_start_blocked": collection_start_allowed is False,
    "download_blocked": download_allowed is False,
    "network_download_blocked": network_download_allowed is False,
    "execution_blocked": execution_allowed is False,
    "paper_shadow_not_started": manual_report.get("paper_shadow_started") is False,
    "paper_shadow_start_not_approved": manual_report.get("approved_for_paper_shadow_start") is False,
    "exchange_order_submission_disabled": manual_report.get("exchange_order_submission") is False,
    "micro_live_not_approved": manual_report.get("approved_for_micro_live_execution") is False,
    "real_live_not_approved": manual_report.get("approved_for_real_live_trading") is False,
}

blockers = [k for k, v in start_gate_checks.items() if v is not True]
start_gate_ready = all(start_gate_checks.values())

if start_gate_ready:
    decision = "PHASE_19_OFFLINE_HISTORICAL_DATA_COLLECTION_START_GATE_CREATED_START_BLOCKED_MANUAL_APPROVAL_REQUIRED"
    next_phase = "Phase 19.12 — Offline Historical Data Collection Blocked Start Review"
else:
    decision = "PHASE_19_OFFLINE_HISTORICAL_DATA_COLLECTION_START_GATE_BLOCKED_REVIEW_REQUIRED"
    next_phase = "Phase 19.12 — Offline Historical Data Collection Start Gate Review"

GATE_DIR.mkdir(parents=True, exist_ok=True)

start_gate_record = {
    "phase": "phase_19_11_offline_historical_data_collection_start_gate_record",
    "created_at_unix": int(time.time()),
    "git_head": current_git_head,
    "system_state": "HOLD",
    "selected_option": selected_option,
    "selected_phase19_path": selected_path,
    "start_gate_ready": start_gate_ready,
    "manual_collection_approval_granted": False,
    "collection_start_allowed": False,
    "download_allowed": False,
    "network_download_allowed": False,
    "execution_allowed": False,
    "target_count": target_count,
    "start_gate_checks": start_gate_checks,
    "blockers": blockers,
    "blocked_reason": "manual_collection_approval_required",
    "paper_shadow_started": False,
    "approved_for_paper_shadow_start": False,
    "exchange_order_submission": False,
    "real_capital_allowed": False,
    "live_trading_enabled": False,
    "approved_for_micro_live_execution": False,
    "approved_for_real_live_trading": False,
    "allowed_actions": [
        "review_manual_approval_template",
        "review_collection_targets",
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

gate_file = GATE_DIR / "offline_historical_data_collection_start_gate.json"
write_json(gate_file, start_gate_record)
write_json(RUNTIME_OUT, start_gate_record)

report = {
    "phase": "phase_19_11_offline_historical_data_collection_start_gate",
    "generated_at_unix": int(time.time()),
    "scope": "start_gate_only_no_collection_no_download_no_execution",
    "git_head": current_git_head,
    "safety_flags": flags,
    "safe_mode_active": safe_mode,
    "git_working_tree_clean": git_clean_before_outputs,
    "selected_option": selected_option,
    "selected_phase19_path": selected_path,
    "start_gate_ready": start_gate_ready,
    "manual_collection_approval_granted": False,
    "collection_start_allowed": False,
    "download_allowed": False,
    "network_download_allowed": False,
    "execution_allowed": False,
    "target_count": target_count,
    "start_gate_checks": start_gate_checks,
    "blockers": blockers,
    "gate_file": str(gate_file),
    "runtime_gate_file": str(RUNTIME_OUT),
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
        "This phase creates the offline historical data collection start gate only.",
        "Collection start is blocked because manual approval has not been granted.",
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
print(f"Runtime gate written to: {RUNTIME_OUT}")
print(f"Start gate written to: {gate_file}")
print(f"safe_mode_active={safe_mode}")
print(f"selected_option={selected_option}")
print(f"selected_phase19_path={selected_path}")
print(f"start_gate_ready={start_gate_ready}")
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
