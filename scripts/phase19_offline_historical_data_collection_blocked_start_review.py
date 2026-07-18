import json, os, subprocess, time
from pathlib import Path

OUT = Path("data/processed/phase19_offline_historical_data_collection_blocked_start_review.json")
RUNTIME_OUT = Path("runtime/phase19_offline_historical_data_collection_blocked_start_review_state.json")
REVIEW_DIR = Path("data/processed/phase19_strategy_rework")

START_GATE_REPORT = Path("data/processed/phase19_offline_historical_data_collection_start_gate.json")
START_GATE_RUNTIME = Path("runtime/phase19_offline_historical_data_collection_start_gate_state.json")
START_GATE_FILE = Path("data/processed/phase19_strategy_rework/offline_historical_data_collection_start_gate.json")
MANUAL_RECORD = Path("data/processed/phase19_offline_historical_data_collection_manual_approval_record.json")
APPROVAL_GATE = Path("data/processed/phase19_offline_historical_data_collection_approval_gate.json")
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

start_gate = load_json(START_GATE_REPORT)
start_gate_runtime = load_json(START_GATE_RUNTIME)
start_gate_file = load_json(START_GATE_FILE)
manual_record = load_json(MANUAL_RECORD)
approval_gate = load_json(APPROVAL_GATE)
dry_run = load_json(DRY_RUN_REPORT)
collection_config = load_json(COLLECTION_CONFIG)
phase18_closeout = load_json(PHASE18_CLOSEOUT)

selected_option = (
    start_gate.get("selected_option")
    or start_gate_runtime.get("selected_option")
    or start_gate_file.get("selected_option")
    or manual_record.get("selected_option")
    or phase18_closeout.get("selected_option")
)

selected_path = (
    start_gate.get("selected_phase19_path")
    or start_gate_runtime.get("selected_phase19_path")
    or start_gate_file.get("selected_phase19_path")
    or manual_record.get("selected_phase19_path")
)

start_gate_ready = (
    start_gate.get("start_gate_ready") is True
    or start_gate_runtime.get("start_gate_ready") is True
    or start_gate_file.get("start_gate_ready") is True
)

manual_collection_approval_granted = (
    start_gate.get("manual_collection_approval_granted") is True
    or start_gate_runtime.get("manual_collection_approval_granted") is True
    or start_gate_file.get("manual_collection_approval_granted") is True
    or manual_record.get("manual_collection_approval_granted") is True
)

collection_start_allowed = (
    start_gate.get("collection_start_allowed") is True
    or start_gate_runtime.get("collection_start_allowed") is True
    or start_gate_file.get("collection_start_allowed") is True
)

download_allowed = (
    start_gate.get("download_allowed") is True
    or start_gate_runtime.get("download_allowed") is True
    or start_gate_file.get("download_allowed") is True
)

network_download_allowed = (
    start_gate.get("network_download_allowed") is True
    or start_gate_runtime.get("network_download_allowed") is True
    or start_gate_file.get("network_download_allowed") is True
)

execution_allowed = (
    start_gate.get("execution_allowed") is True
    or start_gate_runtime.get("execution_allowed") is True
    or start_gate_file.get("execution_allowed") is True
)

approval_record_ready = manual_record.get("approval_record_ready") is True
approval_gate_ready = approval_gate.get("approval_gate_ready") is True
dry_run_passed = dry_run.get("dry_run_passed") is True
phase18_closed_safely = phase18_closeout.get("phase18_closed_safely") is True

target_count = (
    start_gate.get("target_count")
    or start_gate_runtime.get("target_count")
    or start_gate_file.get("target_count")
    or manual_record.get("target_count")
    or approval_gate.get("target_count")
    or dry_run.get("target_count")
    or len(collection_config.get("targets", []))
)

review_checks = {
    "safe_mode_active": safe_mode,
    "start_gate_report_present": START_GATE_REPORT.exists(),
    "start_gate_runtime_present": START_GATE_RUNTIME.exists(),
    "start_gate_file_present": START_GATE_FILE.exists(),
    "manual_record_present": MANUAL_RECORD.exists(),
    "approval_gate_present": APPROVAL_GATE.exists(),
    "dry_run_report_present": DRY_RUN_REPORT.exists(),
    "collection_config_present": COLLECTION_CONFIG.exists(),
    "phase18_closeout_present": PHASE18_CLOSEOUT.exists(),
    "selected_option_is_remain_on_hold": selected_option == "remain_on_hold",
    "selected_path_is_data_expansion_first": selected_path == "historical_data_expansion_first_then_strategy_rework",
    "start_gate_ready": start_gate_ready,
    "approval_record_ready": approval_record_ready,
    "approval_gate_ready": approval_gate_ready,
    "dry_run_passed": dry_run_passed,
    "phase18_closed_safely": phase18_closed_safely,
    "manual_collection_approval_not_granted": manual_collection_approval_granted is False,
    "collection_start_blocked": collection_start_allowed is False,
    "download_blocked": download_allowed is False,
    "network_download_blocked": network_download_allowed is False,
    "execution_blocked": execution_allowed is False,
    "paper_shadow_not_started": start_gate.get("paper_shadow_started") is False,
    "paper_shadow_start_not_approved": start_gate.get("approved_for_paper_shadow_start") is False,
    "exchange_order_submission_disabled": start_gate.get("exchange_order_submission") is False,
    "micro_live_not_approved": start_gate.get("approved_for_micro_live_execution") is False,
    "real_live_not_approved": start_gate.get("approved_for_real_live_trading") is False,
}

blockers = [k for k, v in review_checks.items() if v is not True]
blocked_start_review_passed = all(review_checks.values())

if blocked_start_review_passed:
    decision = "PHASE_19_OFFLINE_HISTORICAL_DATA_COLLECTION_BLOCKED_START_REVIEW_COMPLETE_MANUAL_APPROVAL_REQUIRED"
    next_phase = "Phase 19.13 — Offline Historical Data Collection Manual Approval Decision Point"
else:
    decision = "PHASE_19_OFFLINE_HISTORICAL_DATA_COLLECTION_BLOCKED_START_REVIEW_FAILED_REVIEW_REQUIRED"
    next_phase = "Phase 19.13 — Offline Historical Data Collection Blocked Start Fix"

REVIEW_DIR.mkdir(parents=True, exist_ok=True)

review_record = {
    "phase": "phase_19_12_offline_historical_data_collection_blocked_start_review_record",
    "created_at_unix": int(time.time()),
    "git_head": current_git_head,
    "system_state": "HOLD",
    "selected_option": selected_option,
    "selected_phase19_path": selected_path,
    "blocked_start_review_passed": blocked_start_review_passed,
    "review_checks": review_checks,
    "blockers": blockers,
    "target_count": target_count,
    "blocked_reason": "manual_collection_approval_required",
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
    "approved_for_real_live_trading": False,
    "allowed_actions": [
        "manual_approval_decision_review",
        "offline_collection_target_review",
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

review_file = REVIEW_DIR / "offline_historical_data_collection_blocked_start_review.json"
write_json(review_file, review_record)
write_json(RUNTIME_OUT, review_record)

report = {
    "phase": "phase_19_12_offline_historical_data_collection_blocked_start_review",
    "generated_at_unix": int(time.time()),
    "scope": "blocked_start_review_only_no_collection_no_download_no_execution",
    "git_head": current_git_head,
    "safety_flags": flags,
    "safe_mode_active": safe_mode,
    "git_working_tree_clean": git_clean_before_outputs,
    "selected_option": selected_option,
    "selected_phase19_path": selected_path,
    "blocked_start_review_passed": blocked_start_review_passed,
    "review_checks": review_checks,
    "blockers": blockers,
    "target_count": target_count,
    "blocked_reason": "manual_collection_approval_required",
    "manual_collection_approval_granted": False,
    "collection_start_allowed": False,
    "download_allowed": False,
    "network_download_allowed": False,
    "execution_allowed": False,
    "review_file": str(review_file),
    "runtime_review_file": str(RUNTIME_OUT),
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
        "This phase reviews the blocked offline historical data collection start only.",
        "Collection remains blocked because manual collection approval has not been granted.",
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
print(f"Runtime review written to: {RUNTIME_OUT}")
print(f"Blocked start review written to: {review_file}")
print(f"safe_mode_active={safe_mode}")
print(f"selected_option={selected_option}")
print(f"selected_phase19_path={selected_path}")
print(f"blocked_start_review_passed={blocked_start_review_passed}")
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
