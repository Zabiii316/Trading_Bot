import json, os, subprocess, time
from pathlib import Path

OUT = Path("data/processed/phase19_historical_data_expansion_manifest_builder.json")
RUNTIME_OUT = Path("runtime/phase19_historical_data_expansion_manifest_builder_state.json")
MANIFEST_DIR = Path("data/processed/phase19_strategy_rework")

PLAN = Path("data/processed/phase19_historical_data_expansion_plan.json")
RUNTIME_PLAN = Path("runtime/phase19_historical_data_expansion_plan_state.json")
PHASE19_DECISION = Path("data/processed/phase19_strategy_rework_historical_data_expansion_decision.json")
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
git_clean_before_outputs = git_clean()
current_git_head = git_head()

plan = load_json(PLAN)
runtime_plan = load_json(RUNTIME_PLAN)
phase19_decision = load_json(PHASE19_DECISION)
phase18_closeout = load_json(PHASE18_CLOSEOUT)

selected_option = plan.get("selected_option") or phase19_decision.get("selected_option") or phase18_closeout.get("selected_option")
selected_path = plan.get("selected_phase19_path") or phase19_decision.get("selected_phase19_path")
plan_ready = plan.get("historical_data_expansion_plan_ready") is True or runtime_plan.get("historical_data_expansion_plan_ready") is True
phase19_decision_ready = phase19_decision.get("phase19_decision_ready") is True
phase18_closed_safely = phase18_closeout.get("phase18_closed_safely") is True

requirements = (
    load_json(MANIFEST_DIR / "historical_data_expansion_plan.json")
    .get("historical_data_requirements", {})
)

target_symbols = requirements.get("minimum_target_symbols", ["BTCUSDT", "ETHUSDT", "BNBUSDT"])
optional_symbols = requirements.get("optional_extra_symbols", ["SOLUSDT", "XRPUSDT", "ADAUSDT"])
timeframes = requirements.get("minimum_timeframes", ["1m", "5m", "15m", "1h"])
history_days = requirements.get("preferred_history_window_days", 180)

existing_dataset_dir = Path("data/processed/backtest_datasets")
existing_files = sorted(existing_dataset_dir.glob("*.jsonl")) if existing_dataset_dir.exists() else []

existing_dataset_inventory = []
for file in existing_files:
    name = file.name.lower()
    detected_symbol = None
    for symbol in target_symbols + optional_symbols:
        if symbol.lower() in name:
            detected_symbol = symbol
            break

    existing_dataset_inventory.append({
        "file": str(file),
        "detected_symbol": detected_symbol or "UNKNOWN",
        "detected_timeframe": "UNKNOWN",
        "size_bytes": file.stat().st_size,
        "source": "existing_phase17_dataset"
    })

required_manifest_targets = []
for symbol in target_symbols:
    for timeframe in timeframes:
        required_manifest_targets.append({
            "symbol": symbol,
            "timeframe": timeframe,
            "history_window_days": history_days,
            "priority": "required",
            "mode": "offline_dataset_expansion",
            "download_now": False,
            "execution_allowed": False,
            "expected_raw_output": f"data/raw/historical/{symbol.lower()}_{timeframe}_{history_days}d.jsonl",
            "expected_processed_output": f"data/processed/backtest_datasets/{symbol.lower()}_{timeframe}_phase19_expanded_dataset.jsonl"
        })

optional_manifest_targets = []
for symbol in optional_symbols:
    for timeframe in timeframes:
        optional_manifest_targets.append({
            "symbol": symbol,
            "timeframe": timeframe,
            "history_window_days": history_days,
            "priority": "optional",
            "mode": "offline_dataset_expansion",
            "download_now": False,
            "execution_allowed": False,
            "expected_raw_output": f"data/raw/historical/{symbol.lower()}_{timeframe}_{history_days}d.jsonl",
            "expected_processed_output": f"data/processed/backtest_datasets/{symbol.lower()}_{timeframe}_phase19_expanded_dataset.jsonl"
        })

manifest_checks = {
    "safe_mode_active": safe_mode,
    "phase19_plan_present": PLAN.exists(),
    "runtime_plan_present": RUNTIME_PLAN.exists(),
    "phase19_decision_present": PHASE19_DECISION.exists(),
    "phase18_closeout_present": PHASE18_CLOSEOUT.exists(),
    "selected_option_is_remain_on_hold": selected_option == "remain_on_hold",
    "selected_path_is_data_expansion_first": selected_path == "historical_data_expansion_first_then_strategy_rework",
    "historical_data_expansion_plan_ready": plan_ready,
    "phase19_decision_ready": phase19_decision_ready,
    "phase18_closed_safely": phase18_closed_safely,
    "required_targets_created": len(required_manifest_targets) > 0,
    "paper_shadow_not_started": plan.get("paper_shadow_started") is False,
    "paper_shadow_start_not_approved": plan.get("approved_for_paper_shadow_start") is False,
    "exchange_order_submission_disabled": plan.get("exchange_order_submission") is False,
    "micro_live_not_approved": plan.get("approved_for_micro_live_execution") is False,
    "real_live_not_approved": plan.get("approved_for_real_live_trading") is False,
}

blockers = [k for k, v in manifest_checks.items() if v is not True]
manifest_ready = all(manifest_checks.values())

if manifest_ready:
    decision = "PHASE_19_HISTORICAL_DATA_EXPANSION_MANIFEST_CREATED_NOT_APPROVED_FOR_EXECUTION"
    next_phase = "Phase 19.4 — Historical Data Quality Rules Builder"
else:
    decision = "PHASE_19_HISTORICAL_DATA_EXPANSION_MANIFEST_BLOCKED_REVIEW_REQUIRED"
    next_phase = "Phase 19.4 — Historical Data Manifest Review"

manifest = {
    "phase": "phase_19_3_historical_data_expansion_manifest_record",
    "created_at_unix": int(time.time()),
    "git_head": current_git_head,
    "system_state": "HOLD",
    "selected_option": selected_option,
    "selected_phase19_path": selected_path,
    "manifest_ready": manifest_ready,
    "manifest_checks": manifest_checks,
    "blockers": blockers,
    "target_symbols": target_symbols,
    "optional_symbols": optional_symbols,
    "timeframes": timeframes,
    "history_window_days": history_days,
    "existing_dataset_inventory": existing_dataset_inventory,
    "required_manifest_targets": required_manifest_targets,
    "optional_manifest_targets": optional_manifest_targets,
    "summary": {
        "existing_dataset_file_count": len(existing_dataset_inventory),
        "required_target_count": len(required_manifest_targets),
        "optional_target_count": len(optional_manifest_targets),
        "download_now": False,
        "execution_allowed": False
    },
    "status_summary": {
        "paper_shadow_started": False,
        "approved_for_paper_shadow_start": False,
        "exchange_order_submission": False,
        "real_capital_allowed": False,
        "live_trading_enabled": False,
        "approved_for_micro_live_execution": False,
        "approved_for_real_live_trading": False
    },
    "decision": decision,
    "next_phase": next_phase
}

manifest_file = MANIFEST_DIR / "historical_data_expansion_manifest.json"
missing_targets_file = MANIFEST_DIR / "historical_data_expansion_missing_targets.json"

write_json(manifest_file, manifest)
write_json(missing_targets_file, {
    "phase": "phase_19_3_missing_targets",
    "created_at_unix": int(time.time()),
    "required_missing_targets": required_manifest_targets,
    "optional_missing_targets": optional_manifest_targets,
    "download_now": False,
    "execution_allowed": False
})
write_json(RUNTIME_OUT, manifest)

report = {
    "phase": "phase_19_3_historical_data_expansion_manifest_builder",
    "generated_at_unix": int(time.time()),
    "scope": "manifest_builder_only_no_download_no_execution",
    "git_head": current_git_head,
    "safety_flags": flags,
    "safe_mode_active": safe_mode,
    "git_working_tree_clean": git_clean_before_outputs,
    "selected_option": selected_option,
    "selected_phase19_path": selected_path,
    "manifest_ready": manifest_ready,
    "manifest_checks": manifest_checks,
    "blockers": blockers,
    "existing_dataset_file_count": len(existing_dataset_inventory),
    "required_target_count": len(required_manifest_targets),
    "optional_target_count": len(optional_manifest_targets),
    "manifest_file": str(manifest_file),
    "missing_targets_file": str(missing_targets_file),
    "runtime_manifest_file": str(RUNTIME_OUT),
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
        "This phase builds an offline historical data expansion manifest only.",
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
print(f"Runtime manifest written to: {RUNTIME_OUT}")
print(f"Manifest written to: {manifest_file}")
print(f"Missing targets written to: {missing_targets_file}")
print(f"safe_mode_active={safe_mode}")
print(f"selected_option={selected_option}")
print(f"selected_phase19_path={selected_path}")
print(f"manifest_ready={manifest_ready}")
print(f"required_target_count={len(required_manifest_targets)}")
print(f"optional_target_count={len(optional_manifest_targets)}")
print("paper_shadow_started=False")
print("approved_for_paper_shadow_start=False")
print("exchange_order_submission=False")
print("approved_for_micro_live_execution=False")
print("approved_for_real_live_trading=False")
print(f"decision={decision}")
