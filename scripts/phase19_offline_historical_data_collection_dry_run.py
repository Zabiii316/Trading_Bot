import json, os, subprocess, sys, time
from pathlib import Path

OUT = Path("data/processed/phase19_offline_historical_data_collection_dry_run.json")
RUNTIME_OUT = Path("runtime/phase19_offline_historical_data_collection_dry_run_state.json")
DRY_RUN_DIR = Path("data/processed/phase19_strategy_rework")

BUILDER_REPORT = Path("data/processed/phase19_offline_historical_data_collection_script_builder.json")
RUNTIME_BUILDER = Path("runtime/phase19_offline_historical_data_collection_script_builder_state.json")
BUILDER_FILE = Path("data/processed/phase19_strategy_rework/offline_historical_data_collection_script_builder.json")
COLLECTION_CONFIG = Path("data/processed/phase19_strategy_rework/offline_historical_data_collection_config.json")
GENERATED_COLLECTOR = Path("scripts/phase19_offline_historical_data_collector_dry_run.py")
PREVIEW_FILE = Path("data/processed/phase19_strategy_rework/offline_historical_data_collection_dry_run_preview.json")
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

builder_report = load_json(BUILDER_REPORT)
runtime_builder = load_json(RUNTIME_BUILDER)
builder_file = load_json(BUILDER_FILE)
collection_config = load_json(COLLECTION_CONFIG)
gap_plan = load_json(GAP_PLAN)
phase18_closeout = load_json(PHASE18_CLOSEOUT)

selected_option = (
    builder_report.get("selected_option")
    or runtime_builder.get("selected_option")
    or builder_file.get("selected_option")
    or gap_plan.get("selected_option")
    or phase18_closeout.get("selected_option")
)

selected_path = (
    builder_report.get("selected_phase19_path")
    or runtime_builder.get("selected_phase19_path")
    or builder_file.get("selected_phase19_path")
    or gap_plan.get("selected_phase19_path")
)

collector_script_builder_ready = (
    builder_report.get("collector_script_builder_ready") is True
    or runtime_builder.get("collector_script_builder_ready") is True
    or builder_file.get("collector_script_builder_ready") is True
)

phase18_closed_safely = phase18_closeout.get("phase18_closed_safely") is True

pre_checks = {
    "safe_mode_active": safe_mode,
    "builder_report_present": BUILDER_REPORT.exists(),
    "runtime_builder_present": RUNTIME_BUILDER.exists(),
    "builder_file_present": BUILDER_FILE.exists(),
    "collection_config_present": COLLECTION_CONFIG.exists(),
    "generated_collector_present": GENERATED_COLLECTOR.exists(),
    "gap_plan_present": GAP_PLAN.exists(),
    "phase18_closeout_present": PHASE18_CLOSEOUT.exists(),
    "selected_option_is_remain_on_hold": selected_option == "remain_on_hold",
    "selected_path_is_data_expansion_first": selected_path == "historical_data_expansion_first_then_strategy_rework",
    "collector_script_builder_ready": collector_script_builder_ready,
    "collection_config_dry_run_only": collection_config.get("mode") == "dry_run_only",
    "collection_config_download_disabled": collection_config.get("download_now") is False,
    "collection_config_execution_disabled": collection_config.get("execution_allowed") is False,
    "collection_config_network_download_disabled": collection_config.get("network_download_allowed") is False,
    "phase18_closed_safely": phase18_closed_safely,
    "paper_shadow_not_started": builder_report.get("paper_shadow_started") is False,
    "paper_shadow_start_not_approved": builder_report.get("approved_for_paper_shadow_start") is False,
    "exchange_order_submission_disabled": builder_report.get("exchange_order_submission") is False,
    "micro_live_not_approved": builder_report.get("approved_for_micro_live_execution") is False,
    "real_live_not_approved": builder_report.get("approved_for_real_live_trading") is False,
}

pre_blockers = [k for k, v in pre_checks.items() if v is not True]
pre_checks_passed = all(pre_checks.values())

collector_result = {
    "collector_executed": False,
    "returncode": None,
    "stdout": "",
    "stderr": "",
}

if pre_checks_passed:
    result = run([sys.executable, str(GENERATED_COLLECTOR)])
    collector_result = {
        "collector_executed": True,
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }

preview = load_json(PREVIEW_FILE)

post_checks = {
    "collector_executed": collector_result["collector_executed"] is True,
    "collector_returncode_zero": collector_result["returncode"] == 0,
    "preview_file_present": PREVIEW_FILE.exists(),
    "preview_mode_dry_run_only": preview.get("mode") == "dry_run_only",
    "preview_download_started_false": preview.get("download_started") is False,
    "preview_download_completed_false": preview.get("download_completed") is False,
    "preview_execution_allowed_false": preview.get("execution_allowed") is False,
    "preview_network_download_allowed_false": preview.get("network_download_allowed") is False,
    "preview_paper_shadow_allowed_false": preview.get("paper_shadow_allowed") is False,
    "preview_live_trading_allowed_false": preview.get("live_trading_allowed") is False,
    "preview_exchange_order_submission_allowed_false": preview.get("exchange_order_submission_allowed") is False,
}

post_blockers = [k for k, v in post_checks.items() if v is not True]
dry_run_passed = pre_checks_passed and all(post_checks.values())

if dry_run_passed:
    decision = "PHASE_19_OFFLINE_HISTORICAL_DATA_COLLECTION_DRY_RUN_COMPLETE_NO_DOWNLOAD_NOT_APPROVED_FOR_EXECUTION"
    next_phase = "Phase 19.9 — Offline Historical Data Collection Approval Gate"
else:
    decision = "PHASE_19_OFFLINE_HISTORICAL_DATA_COLLECTION_DRY_RUN_BLOCKED_REVIEW_REQUIRED"
    next_phase = "Phase 19.9 — Offline Historical Data Collection Dry Run Review"

DRY_RUN_DIR.mkdir(parents=True, exist_ok=True)

dry_run_record = {
    "phase": "phase_19_8_offline_historical_data_collection_dry_run_record",
    "created_at_unix": int(time.time()),
    "git_head": current_git_head,
    "system_state": "HOLD",
    "selected_option": selected_option,
    "selected_phase19_path": selected_path,
    "dry_run_passed": dry_run_passed,
    "pre_checks_passed": pre_checks_passed,
    "pre_checks": pre_checks,
    "post_checks": post_checks,
    "blockers": pre_blockers + post_blockers,
    "collector_result": collector_result,
    "preview_file": str(PREVIEW_FILE),
    "preview": preview,
    "target_count": preview.get("target_count", len(collection_config.get("targets", []))),
    "download_started": False,
    "download_completed": False,
    "execution_allowed": False,
    "network_download_allowed": False,
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

dry_run_file = DRY_RUN_DIR / "offline_historical_data_collection_dry_run_result.json"
write_json(dry_run_file, dry_run_record)
write_json(RUNTIME_OUT, dry_run_record)

report = {
    "phase": "phase_19_8_offline_historical_data_collection_dry_run",
    "generated_at_unix": int(time.time()),
    "scope": "dry_run_only_no_download_no_execution",
    "git_head": current_git_head,
    "safety_flags": flags,
    "safe_mode_active": safe_mode,
    "git_working_tree_clean": git_clean_before_outputs,
    "selected_option": selected_option,
    "selected_phase19_path": selected_path,
    "dry_run_passed": dry_run_passed,
    "pre_checks_passed": pre_checks_passed,
    "pre_checks": pre_checks,
    "post_checks": post_checks,
    "blockers": pre_blockers + post_blockers,
    "collector_result": collector_result,
    "target_count": preview.get("target_count", len(collection_config.get("targets", []))),
    "dry_run_file": str(dry_run_file),
    "preview_file": str(PREVIEW_FILE),
    "runtime_dry_run_file": str(RUNTIME_OUT),
    "download_started": False,
    "download_completed": False,
    "execution_allowed": False,
    "network_download_allowed": False,
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
        "This phase runs the offline historical data collector in dry-run mode only.",
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
print(f"Runtime dry-run written to: {RUNTIME_OUT}")
print(f"Dry-run result written to: {dry_run_file}")
print(f"Preview file: {PREVIEW_FILE}")
print(f"safe_mode_active={safe_mode}")
print(f"selected_option={selected_option}")
print(f"selected_phase19_path={selected_path}")
print(f"dry_run_passed={dry_run_passed}")
print(f"target_count={preview.get('target_count', len(collection_config.get('targets', [])))}")
print("download_started=False")
print("download_completed=False")
print("execution_allowed=False")
print("network_download_allowed=False")
print("paper_shadow_started=False")
print("approved_for_paper_shadow_start=False")
print("exchange_order_submission=False")
print("approved_for_micro_live_execution=False")
print("approved_for_real_live_trading=False")
print(f"decision={decision}")
