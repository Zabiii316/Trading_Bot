import json, os, subprocess, time
from pathlib import Path

OUT = Path("data/processed/phase19_historical_data_expansion_next_action_selection.json")
RUNTIME_OUT = Path("runtime/phase19_historical_data_expansion_next_action_selection_state.json")
SELECTION_DIR = Path("data/processed/phase19_strategy_rework")

OPTIONS_REPORT = Path("data/processed/phase19_historical_data_expansion_next_action_options.json")
OPTIONS_RUNTIME = Path("runtime/phase19_historical_data_expansion_next_action_options_state.json")
OPTIONS_FILE = Path("data/processed/phase19_strategy_rework/historical_data_expansion_next_action_options.json")
COLLECTION_CLOSEOUT = Path("data/processed/phase19_offline_historical_data_collection_safety_closeout.json")
GAP_PLAN = Path("data/processed/phase19_historical_data_gap_fill_plan.json")
PHASE18_CLOSEOUT = Path("data/processed/phase18_final_safety_closeout.json")

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

options_report = load_json(OPTIONS_REPORT)
options_runtime = load_json(OPTIONS_RUNTIME)
options_file_data = load_json(OPTIONS_FILE)
collection_closeout = load_json(COLLECTION_CLOSEOUT)
gap_plan = load_json(GAP_PLAN)
phase18 = load_json(PHASE18_CLOSEOUT)

selected_option = (
    options_report.get("selected_option")
    or options_runtime.get("selected_option")
    or options_file_data.get("selected_option")
    or collection_closeout.get("selected_option")
    or phase18.get("selected_option")
)

selected_path = (
    options_report.get("selected_phase19_path")
    or options_runtime.get("selected_phase19_path")
    or options_file_data.get("selected_phase19_path")
    or collection_closeout.get("selected_phase19_path")
)

next_action_options_ready = (
    options_report.get("next_action_options_ready") is True
    or options_runtime.get("next_action_options_ready") is True
    or options_file_data.get("next_action_options_ready") is True
)

collection_safety_closeout_passed = collection_closeout.get("collection_safety_closeout_passed") is True
gap_fill_plan_ready = gap_plan.get("gap_fill_plan_ready") is True
phase18_closed_safely = phase18.get("phase18_closed_safely") is True

selected_next_action = "remain_on_hold"

manual_collection_approval_granted = False
collection_start_allowed = False
download_allowed = False
network_download_allowed = False
execution_allowed = False

missing_required_target_count = (
    options_report.get("missing_required_target_count")
    or options_file_data.get("missing_required_target_count")
    or gap_plan.get("missing_required_target_count")
    or 0
)

target_count = (
    options_report.get("target_count")
    or options_file_data.get("target_count")
    or collection_closeout.get("target_count")
    or 0
)

selection_checks = {
    "safe_mode_active": safe_mode,
    "options_report_present": OPTIONS_REPORT.exists(),
    "options_runtime_present": OPTIONS_RUNTIME.exists(),
    "options_file_present": OPTIONS_FILE.exists(),
    "collection_closeout_present": COLLECTION_CLOSEOUT.exists(),
    "gap_plan_present": GAP_PLAN.exists(),
    "phase18_closeout_present": PHASE18_CLOSEOUT.exists(),
    "selected_option_is_remain_on_hold": selected_option == "remain_on_hold",
    "selected_path_is_data_expansion_first": selected_path == "historical_data_expansion_first_then_strategy_rework",
    "next_action_options_ready": next_action_options_ready,
    "collection_safety_closeout_passed": collection_safety_closeout_passed,
    "gap_fill_plan_ready": gap_fill_plan_ready,
    "phase18_closed_safely": phase18_closed_safely,
    "selected_next_action_is_remain_on_hold": selected_next_action == "remain_on_hold",
    "manual_collection_approval_not_granted": manual_collection_approval_granted is False,
    "collection_start_blocked": collection_start_allowed is False,
    "download_blocked": download_allowed is False,
    "network_download_blocked": network_download_allowed is False,
    "execution_blocked": execution_allowed is False,
    "paper_shadow_not_started": options_report.get("paper_shadow_started") is False,
    "paper_shadow_start_not_approved": options_report.get("approved_for_paper_shadow_start") is False,
    "exchange_order_submission_disabled": options_report.get("exchange_order_submission") is False,
    "micro_live_not_approved": options_report.get("approved_for_micro_live_execution") is False,
    "real_live_not_approved": options_report.get("approved_for_real_live_trading") is False,
}

blockers = [k for k, v in selection_checks.items() if v is not True]
next_action_selection_ready = all(selection_checks.values())

if next_action_selection_ready:
    decision = "PHASE_19_HISTORICAL_DATA_EXPANSION_NEXT_ACTION_SELECTED_REMAIN_ON_HOLD_COLLECTION_NOT_APPROVED"
    next_phase = "Phase 19.19 — Historical Data Expansion Hold State Consolidation"
else:
    decision = "PHASE_19_HISTORICAL_DATA_EXPANSION_NEXT_ACTION_SELECTION_BLOCKED_REVIEW_REQUIRED"
    next_phase = "Phase 19.19 — Historical Data Expansion Selection Review"

SELECTION_DIR.mkdir(parents=True, exist_ok=True)

selection_record = {
    "phase": "phase_19_18_historical_data_expansion_next_action_selection_record",
    "created_at_unix": int(time.time()),
    "git_head": current_git_head,
    "system_state": "HOLD",
    "selected_option": selected_option,
    "selected_phase19_path": selected_path,
    "next_action_selection_ready": next_action_selection_ready,
    "selected_next_action": selected_next_action,
    "selection_checks": selection_checks,
    "blockers": blockers,
    "missing_required_target_count": missing_required_target_count,
    "target_count": target_count,
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
        "continue_hold_state_monitoring",
        "manual_data_source_review_only",
        "documentation_only",
        "phase19_hold_state_consolidation_only"
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

selection_file = SELECTION_DIR / "historical_data_expansion_next_action_selection.json"

write_json(selection_file, selection_record)
write_json(RUNTIME_OUT, selection_record)

report = {
    "phase": "phase_19_18_historical_data_expansion_next_action_selection",
    "generated_at_unix": int(time.time()),
    "scope": "next_action_selection_only_no_collection_no_download_no_execution",
    "git_head": current_git_head,
    "safety_flags": flags,
    "safe_mode_active": safe_mode,
    "git_working_tree_clean": git_clean_before_outputs,
    "selected_option": selected_option,
    "selected_phase19_path": selected_path,
    "next_action_selection_ready": next_action_selection_ready,
    "selected_next_action": selected_next_action,
    "selection_checks": selection_checks,
    "blockers": blockers,
    "missing_required_target_count": missing_required_target_count,
    "target_count": target_count,
    "selection_file": str(selection_file),
    "runtime_selection_file": str(RUNTIME_OUT),
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
    "decision": decision,
    "next_phase": next_phase,
    "safety_notes": [
        "This phase selects remain_on_hold as the next action.",
        "Manual collection approval remains false.",
        "This phase does not approve historical data download.",
        "This phase does not import historical data.",
        "This phase does not start paper shadow execution.",
        "This phase does not approve micro-live execution.",
        "This phase does not approve real live trading.",
        "This phase does not submit Binance orders."
    ]
}

write_json(OUT, report)

print(f"Report written to: {OUT}")
print(f"Runtime selection written to: {RUNTIME_OUT}")
print(f"Selection file written to: {selection_file}")
print(f"safe_mode_active={safe_mode}")
print(f"selected_option={selected_option}")
print(f"selected_phase19_path={selected_path}")
print(f"next_action_selection_ready={next_action_selection_ready}")
print(f"selected_next_action={selected_next_action}")
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
