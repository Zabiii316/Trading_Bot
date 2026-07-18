import json, os, subprocess, time
from pathlib import Path

OUT = Path("data/processed/phase19_offline_historical_data_collection_manual_approval_decision_point.json")
RUNTIME_OUT = Path("runtime/phase19_offline_historical_data_collection_manual_approval_decision_point_state.json")
DECISION_DIR = Path("data/processed/phase19_strategy_rework")

BLOCKED_REVIEW = Path("data/processed/phase19_offline_historical_data_collection_blocked_start_review.json")
BLOCKED_REVIEW_RUNTIME = Path("runtime/phase19_offline_historical_data_collection_blocked_start_review_state.json")
BLOCKED_REVIEW_FILE = Path("data/processed/phase19_strategy_rework/offline_historical_data_collection_blocked_start_review.json")
START_GATE = Path("data/processed/phase19_offline_historical_data_collection_start_gate.json")
MANUAL_RECORD = Path("data/processed/phase19_offline_historical_data_collection_manual_approval_record.json")
APPROVAL_TEMPLATE = Path("data/processed/phase19_strategy_rework/offline_historical_data_collection_manual_approval_template.json")
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

blocked_review = load_json(BLOCKED_REVIEW)
blocked_runtime = load_json(BLOCKED_REVIEW_RUNTIME)
blocked_file = load_json(BLOCKED_REVIEW_FILE)
start_gate = load_json(START_GATE)
manual_record = load_json(MANUAL_RECORD)
approval_template = load_json(APPROVAL_TEMPLATE)
collection_config = load_json(COLLECTION_CONFIG)
phase18_closeout = load_json(PHASE18_CLOSEOUT)

selected_option = (
    blocked_review.get("selected_option")
    or blocked_runtime.get("selected_option")
    or blocked_file.get("selected_option")
    or start_gate.get("selected_option")
    or manual_record.get("selected_option")
    or phase18_closeout.get("selected_option")
)

selected_path = (
    blocked_review.get("selected_phase19_path")
    or blocked_runtime.get("selected_phase19_path")
    or blocked_file.get("selected_phase19_path")
    or start_gate.get("selected_phase19_path")
    or manual_record.get("selected_phase19_path")
)

blocked_start_review_passed = (
    blocked_review.get("blocked_start_review_passed") is True
    or blocked_runtime.get("blocked_start_review_passed") is True
    or blocked_file.get("blocked_start_review_passed") is True
)

start_gate_ready = start_gate.get("start_gate_ready") is True
approval_record_ready = manual_record.get("approval_record_ready") is True
phase18_closed_safely = phase18_closeout.get("phase18_closed_safely") is True

manual_collection_approval_granted = False
collection_start_allowed = False
download_allowed = False
network_download_allowed = False
execution_allowed = False

target_count = (
    blocked_review.get("target_count")
    or start_gate.get("target_count")
    or manual_record.get("target_count")
    or approval_template.get("target_count")
    or len(collection_config.get("targets", []))
)

decision_checks = {
    "safe_mode_active": safe_mode,
    "blocked_review_present": BLOCKED_REVIEW.exists(),
    "blocked_review_runtime_present": BLOCKED_REVIEW_RUNTIME.exists(),
    "blocked_review_file_present": BLOCKED_REVIEW_FILE.exists(),
    "start_gate_present": START_GATE.exists(),
    "manual_record_present": MANUAL_RECORD.exists(),
    "approval_template_present": APPROVAL_TEMPLATE.exists(),
    "collection_config_present": COLLECTION_CONFIG.exists(),
    "phase18_closeout_present": PHASE18_CLOSEOUT.exists(),
    "selected_option_is_remain_on_hold": selected_option == "remain_on_hold",
    "selected_path_is_data_expansion_first": selected_path == "historical_data_expansion_first_then_strategy_rework",
    "blocked_start_review_passed": blocked_start_review_passed,
    "start_gate_ready": start_gate_ready,
    "approval_record_ready": approval_record_ready,
    "phase18_closed_safely": phase18_closed_safely,
    "manual_collection_approval_not_granted": manual_collection_approval_granted is False,
    "collection_start_blocked": collection_start_allowed is False,
    "download_blocked": download_allowed is False,
    "network_download_blocked": network_download_allowed is False,
    "execution_blocked": execution_allowed is False,
    "paper_shadow_not_started": blocked_review.get("paper_shadow_started") is False,
    "paper_shadow_start_not_approved": blocked_review.get("approved_for_paper_shadow_start") is False,
    "exchange_order_submission_disabled": blocked_review.get("exchange_order_submission") is False,
    "micro_live_not_approved": blocked_review.get("approved_for_micro_live_execution") is False,
    "real_live_not_approved": blocked_review.get("approved_for_real_live_trading") is False,
}

blockers = [k for k, v in decision_checks.items() if v is not True]
decision_point_ready = all(decision_checks.values())

if decision_point_ready:
    decision = "PHASE_19_OFFLINE_HISTORICAL_DATA_COLLECTION_MANUAL_APPROVAL_DECISION_POINT_CREATED_HOLD_NOT_APPROVED_FOR_COLLECTION"
    next_phase = "Phase 19.14 — Offline Historical Data Collection Manual Approval Decision Review"
else:
    decision = "PHASE_19_OFFLINE_HISTORICAL_DATA_COLLECTION_MANUAL_APPROVAL_DECISION_POINT_BLOCKED_REVIEW_REQUIRED"
    next_phase = "Phase 19.14 — Offline Historical Data Collection Decision Point Fix"

DECISION_DIR.mkdir(parents=True, exist_ok=True)

decision_record = {
    "phase": "phase_19_13_offline_historical_data_collection_manual_approval_decision_point_record",
    "created_at_unix": int(time.time()),
    "git_head": current_git_head,
    "system_state": "HOLD",
    "selected_option": selected_option,
    "selected_phase19_path": selected_path,
    "decision_point_ready": decision_point_ready,
    "manual_collection_approval_granted": False,
    "collection_start_allowed": False,
    "download_allowed": False,
    "network_download_allowed": False,
    "execution_allowed": False,
    "target_count": target_count,
    "decision_checks": decision_checks,
    "blockers": blockers,
    "decision_state": "hold_not_approved_for_collection",
    "approval_required_before_any_collection": True,
    "paper_shadow_started": False,
    "approved_for_paper_shadow_start": False,
    "exchange_order_submission": False,
    "real_capital_allowed": False,
    "live_trading_enabled": False,
    "approved_for_micro_live_execution": False,
    "approved_for_real_live_trading": False,
    "allowed_actions": [
        "manual_approval_review_only",
        "collection_target_review_only",
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

decision_file = DECISION_DIR / "offline_historical_data_collection_manual_approval_decision_point.json"

write_json(decision_file, decision_record)
write_json(RUNTIME_OUT, decision_record)

report = {
    "phase": "phase_19_13_offline_historical_data_collection_manual_approval_decision_point",
    "generated_at_unix": int(time.time()),
    "scope": "manual_approval_decision_point_only_no_collection_no_download_no_execution",
    "git_head": current_git_head,
    "safety_flags": flags,
    "safe_mode_active": safe_mode,
    "git_working_tree_clean": git_clean_before_outputs,
    "selected_option": selected_option,
    "selected_phase19_path": selected_path,
    "decision_point_ready": decision_point_ready,
    "manual_collection_approval_granted": False,
    "collection_start_allowed": False,
    "download_allowed": False,
    "network_download_allowed": False,
    "execution_allowed": False,
    "target_count": target_count,
    "decision_checks": decision_checks,
    "blockers": blockers,
    "decision_file": str(decision_file),
    "runtime_decision_file": str(RUNTIME_OUT),
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
        "This phase creates the manual approval decision point only.",
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
print(f"Runtime decision written to: {RUNTIME_OUT}")
print(f"Decision file written to: {decision_file}")
print(f"safe_mode_active={safe_mode}")
print(f"selected_option={selected_option}")
print(f"selected_phase19_path={selected_path}")
print(f"decision_point_ready={decision_point_ready}")
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
