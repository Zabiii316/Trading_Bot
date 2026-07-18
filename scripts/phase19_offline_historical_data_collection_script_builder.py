import json, os, subprocess, time
from pathlib import Path

OUT = Path("data/processed/phase19_offline_historical_data_collection_script_builder.json")
RUNTIME_OUT = Path("runtime/phase19_offline_historical_data_collection_script_builder_state.json")
BUILDER_DIR = Path("data/processed/phase19_strategy_rework")

GAP_PLAN_REPORT = Path("data/processed/phase19_historical_data_gap_fill_plan.json")
GAP_PLAN_FILE = Path("data/processed/phase19_strategy_rework/historical_data_gap_fill_plan.json")
MISSING_REQUIRED = Path("data/processed/phase19_strategy_rework/historical_dataset_missing_required_targets.json")
MANIFEST_FILE = Path("data/processed/phase19_strategy_rework/historical_data_expansion_manifest.json")
QUALITY_RULES = Path("data/processed/phase19_strategy_rework/historical_data_quality_rules.json")
PHASE18_CLOSEOUT = Path("data/processed/phase18_final_safety_closeout.json")

GENERATED_COLLECTOR = Path("scripts/phase19_offline_historical_data_collector_dry_run.py")
COLLECTION_CONFIG = BUILDER_DIR / "offline_historical_data_collection_config.json"

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

gap_report = load_json(GAP_PLAN_REPORT)
gap_plan = load_json(GAP_PLAN_FILE)
missing_required = load_json(MISSING_REQUIRED)
manifest = load_json(MANIFEST_FILE)
quality_rules = load_json(QUALITY_RULES)
phase18_closeout = load_json(PHASE18_CLOSEOUT)

selected_option = (
    gap_report.get("selected_option")
    or gap_plan.get("selected_option")
    or manifest.get("selected_option")
    or phase18_closeout.get("selected_option")
)

selected_path = (
    gap_report.get("selected_phase19_path")
    or gap_plan.get("selected_phase19_path")
    or manifest.get("selected_phase19_path")
)

gap_fill_plan_ready = (
    gap_report.get("gap_fill_plan_ready") is True
    or gap_plan.get("gap_fill_plan_ready") is True
)

quality_rules_ready = quality_rules.get("quality_rules_ready") is True
phase18_closed_safely = phase18_closeout.get("phase18_closed_safely") is True

missing_required_targets = (
    gap_report.get("gap_fill_plan_items")
    or gap_plan.get("gap_fill_plan_items")
    or missing_required.get("missing_required_targets")
    or []
)

collection_config = {
    "phase": "phase_19_7_offline_historical_data_collection_config",
    "created_at_unix": int(time.time()),
    "mode": "dry_run_only",
    "download_now": False,
    "execution_allowed": False,
    "network_download_allowed": False,
    "paper_shadow_allowed": False,
    "live_trading_allowed": False,
    "exchange_order_submission_allowed": False,
    "targets": missing_required_targets,
    "raw_output_dir": "data/raw/historical",
    "processed_output_dir": "data/processed/backtest_datasets",
    "quality_rules_file": str(QUALITY_RULES),
    "required_validation_before_use": [
        "schema_required_columns",
        "timestamps_no_duplicates",
        "timestamps_monotonic",
        "prices_positive",
        "ohlc_consistency",
        "volume_non_negative",
        "minimum_history_window"
    ]
}

collector_source = '''import json, time
from pathlib import Path

CONFIG = Path("data/processed/phase19_strategy_rework/offline_historical_data_collection_config.json")
OUT = Path("data/processed/phase19_strategy_rework/offline_historical_data_collection_dry_run_preview.json")

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

config = load_json(CONFIG)
targets = config.get("targets", [])

preview = {
    "phase": "phase_19_7_offline_historical_data_collector_dry_run",
    "created_at_unix": int(time.time()),
    "mode": "dry_run_only",
    "download_started": False,
    "download_completed": False,
    "execution_allowed": False,
    "network_download_allowed": False,
    "paper_shadow_allowed": False,
    "live_trading_allowed": False,
    "exchange_order_submission_allowed": False,
    "target_count": len(targets),
    "targets": targets,
    "next_step": "manual_review_before_any_offline_data_import_or_collection"
}

write_json(OUT, preview)

print(f"Dry-run preview written to: {OUT}")
print("mode=dry_run_only")
print("download_started=False")
print("execution_allowed=False")
print("paper_shadow_allowed=False")
print("live_trading_allowed=False")
print("exchange_order_submission_allowed=False")
print(f"target_count={len(targets)}")
'''

builder_checks = {
    "safe_mode_active": safe_mode,
    "gap_plan_report_present": GAP_PLAN_REPORT.exists(),
    "gap_plan_file_present": GAP_PLAN_FILE.exists(),
    "missing_required_file_present": MISSING_REQUIRED.exists(),
    "manifest_file_present": MANIFEST_FILE.exists(),
    "quality_rules_present": QUALITY_RULES.exists(),
    "phase18_closeout_present": PHASE18_CLOSEOUT.exists(),
    "selected_option_is_remain_on_hold": selected_option == "remain_on_hold",
    "selected_path_is_data_expansion_first": selected_path == "historical_data_expansion_first_then_strategy_rework",
    "gap_fill_plan_ready": gap_fill_plan_ready,
    "quality_rules_ready": quality_rules_ready,
    "phase18_closed_safely": phase18_closed_safely,
    "paper_shadow_not_started": gap_report.get("paper_shadow_started") is False,
    "paper_shadow_start_not_approved": gap_report.get("approved_for_paper_shadow_start") is False,
    "exchange_order_submission_disabled": gap_report.get("exchange_order_submission") is False,
    "micro_live_not_approved": gap_report.get("approved_for_micro_live_execution") is False,
    "real_live_not_approved": gap_report.get("approved_for_real_live_trading") is False,
}

blockers = [k for k, v in builder_checks.items() if v is not True]
collector_script_builder_ready = all(builder_checks.values())

if collector_script_builder_ready:
    decision = "PHASE_19_OFFLINE_HISTORICAL_DATA_COLLECTION_SCRIPT_CREATED_NOT_APPROVED_FOR_EXECUTION"
    next_phase = "Phase 19.8 — Offline Historical Data Collection Dry Run"
else:
    decision = "PHASE_19_OFFLINE_HISTORICAL_DATA_COLLECTION_SCRIPT_BLOCKED_REVIEW_REQUIRED"
    next_phase = "Phase 19.8 — Offline Historical Data Collection Script Review"

BUILDER_DIR.mkdir(parents=True, exist_ok=True)
write_json(COLLECTION_CONFIG, collection_config)
GENERATED_COLLECTOR.write_text(collector_source)
GENERATED_COLLECTOR.chmod(0o755)

builder_record = {
    "phase": "phase_19_7_offline_historical_data_collection_script_builder_record",
    "created_at_unix": int(time.time()),
    "git_head": current_git_head,
    "system_state": "HOLD",
    "selected_option": selected_option,
    "selected_phase19_path": selected_path,
    "collector_script_builder_ready": collector_script_builder_ready,
    "builder_checks": builder_checks,
    "blockers": blockers,
    "missing_required_target_count": len(missing_required_targets),
    "generated_collector_script": str(GENERATED_COLLECTOR),
    "collection_config_file": str(COLLECTION_CONFIG),
    "download_now": False,
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

builder_file = BUILDER_DIR / "offline_historical_data_collection_script_builder.json"
write_json(builder_file, builder_record)
write_json(RUNTIME_OUT, builder_record)

report = {
    "phase": "phase_19_7_offline_historical_data_collection_script_builder",
    "generated_at_unix": int(time.time()),
    "scope": "collection_script_builder_only_no_download_no_execution",
    "git_head": current_git_head,
    "safety_flags": flags,
    "safe_mode_active": safe_mode,
    "git_working_tree_clean": git_clean_before_outputs,
    "selected_option": selected_option,
    "selected_phase19_path": selected_path,
    "collector_script_builder_ready": collector_script_builder_ready,
    "builder_checks": builder_checks,
    "blockers": blockers,
    "missing_required_target_count": len(missing_required_targets),
    "generated_collector_script": str(GENERATED_COLLECTOR),
    "collection_config_file": str(COLLECTION_CONFIG),
    "builder_file": str(builder_file),
    "runtime_builder_file": str(RUNTIME_OUT),
    "download_now": False,
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
        "This phase creates an offline historical data collection dry-run script only.",
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
print(f"Runtime builder written to: {RUNTIME_OUT}")
print(f"Builder file written to: {builder_file}")
print(f"Collection config written to: {COLLECTION_CONFIG}")
print(f"Generated collector written to: {GENERATED_COLLECTOR}")
print(f"safe_mode_active={safe_mode}")
print(f"selected_option={selected_option}")
print(f"selected_phase19_path={selected_path}")
print(f"collector_script_builder_ready={collector_script_builder_ready}")
print(f"missing_required_target_count={len(missing_required_targets)}")
print("download_now=False")
print("execution_allowed=False")
print("paper_shadow_started=False")
print("approved_for_paper_shadow_start=False")
print("exchange_order_submission=False")
print("approved_for_micro_live_execution=False")
print("approved_for_real_live_trading=False")
print(f"decision={decision}")
