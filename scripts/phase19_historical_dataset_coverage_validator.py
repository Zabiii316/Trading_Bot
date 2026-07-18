import json, os, subprocess, time
from pathlib import Path

OUT = Path("data/processed/phase19_historical_dataset_coverage_validator.json")
RUNTIME_OUT = Path("runtime/phase19_historical_dataset_coverage_validator_state.json")
VALIDATOR_DIR = Path("data/processed/phase19_strategy_rework")

QUALITY_REPORT = Path("data/processed/phase19_historical_data_quality_rules_builder.json")
QUALITY_RULES = Path("data/processed/phase19_strategy_rework/historical_data_quality_rules.json")
MANIFEST_REPORT = Path("data/processed/phase19_historical_data_expansion_manifest_builder.json")
MANIFEST_FILE = Path("data/processed/phase19_strategy_rework/historical_data_expansion_manifest.json")
PLAN = Path("data/processed/phase19_historical_data_expansion_plan.json")
PHASE19_DECISION = Path("data/processed/phase19_strategy_rework_historical_data_expansion_decision.json")
PHASE18_CLOSEOUT = Path("data/processed/phase18_final_safety_closeout.json")

DATASET_DIR = Path("data/processed/backtest_datasets")

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

def detect_symbol_from_name(path, symbols):
    name = path.name.lower()
    for symbol in symbols:
        if symbol.lower() in name:
            return symbol
    return "UNKNOWN"

def detect_timeframe_from_name(path, timeframes):
    name = path.name.lower()
    for timeframe in timeframes:
        if f"_{timeframe}_" in name or f"-{timeframe}-" in name or name.endswith(f"_{timeframe}.jsonl"):
            return timeframe
    return "UNKNOWN"

def count_jsonl_rows(path, max_rows=None):
    rows = 0
    try:
        with path.open("r", encoding="utf-8") as f:
            for _ in f:
                rows += 1
                if max_rows and rows >= max_rows:
                    break
    except Exception:
        return 0
    return rows

flags = {
    "BINANCE_TESTNET": os.getenv("BINANCE_TESTNET", ""),
    "BINANCE_USE_TESTNET": os.getenv("BINANCE_USE_TESTNET", ""),
    "BINANCE_ENABLE_LIVE_TRADING": os.getenv("BINANCE_ENABLE_LIVE_TRADING", ""),
    "LIVE_TRADING_ALLOWED": os.getenv("LIVE_TRADING_ALLOWED", ""),
}

safe_mode = flags["BINANCE_ENABLE_LIVE_TRADING"] == "false" and flags["LIVE_TRADING_ALLOWED"] == "false"
git_clean_before_outputs = git_clean()
current_git_head = git_head()

quality_report = load_json(QUALITY_REPORT)
quality_rules = load_json(QUALITY_RULES)
manifest_report = load_json(MANIFEST_REPORT)
manifest = load_json(MANIFEST_FILE)
plan = load_json(PLAN)
phase19_decision = load_json(PHASE19_DECISION)
phase18_closeout = load_json(PHASE18_CLOSEOUT)

selected_option = (
    quality_report.get("selected_option")
    or manifest_report.get("selected_option")
    or manifest.get("selected_option")
    or plan.get("selected_option")
    or phase19_decision.get("selected_option")
    or phase18_closeout.get("selected_option")
)

selected_path = (
    quality_report.get("selected_phase19_path")
    or manifest_report.get("selected_phase19_path")
    or manifest.get("selected_phase19_path")
    or plan.get("selected_phase19_path")
    or phase19_decision.get("selected_phase19_path")
)

quality_rules_ready = (
    quality_report.get("quality_rules_ready") is True
    or quality_rules.get("quality_rules_ready") is True
)

manifest_ready = (
    manifest_report.get("manifest_ready") is True
    or manifest.get("manifest_ready") is True
)

plan_ready = plan.get("historical_data_expansion_plan_ready") is True
phase19_decision_ready = phase19_decision.get("phase19_decision_ready") is True
phase18_closed_safely = phase18_closeout.get("phase18_closed_safely") is True

required_targets = manifest.get("required_manifest_targets", [])
optional_targets = manifest.get("optional_manifest_targets", [])

all_symbols = sorted(set([t.get("symbol") for t in required_targets + optional_targets if t.get("symbol")]))
all_timeframes = sorted(set([t.get("timeframe") for t in required_targets + optional_targets if t.get("timeframe")]))

dataset_files = sorted(DATASET_DIR.glob("*.jsonl")) if DATASET_DIR.exists() else []

dataset_inventory = []
for file in dataset_files:
    symbol = detect_symbol_from_name(file, all_symbols)
    timeframe = detect_timeframe_from_name(file, all_timeframes)
    dataset_inventory.append({
        "file": str(file),
        "size_bytes": file.stat().st_size,
        "row_count_sample_or_total": count_jsonl_rows(file),
        "detected_symbol": symbol,
        "detected_timeframe": timeframe,
        "exists": file.exists()
    })

covered_pairs = set()
covered_symbols = set()
for item in dataset_inventory:
    if item["detected_symbol"] != "UNKNOWN":
        covered_symbols.add(item["detected_symbol"])
    if item["detected_symbol"] != "UNKNOWN" and item["detected_timeframe"] != "UNKNOWN":
        covered_pairs.add((item["detected_symbol"], item["detected_timeframe"]))

missing_required_targets = []
covered_required_targets = []

for target in required_targets:
    symbol = target.get("symbol")
    timeframe = target.get("timeframe")
    expected_processed_output = target.get("expected_processed_output")
    expected_file_exists = Path(expected_processed_output).exists() if expected_processed_output else False
    pair_covered = (symbol, timeframe) in covered_pairs

    coverage_status = "covered" if expected_file_exists or pair_covered else "missing"

    record = {
        "symbol": symbol,
        "timeframe": timeframe,
        "priority": target.get("priority"),
        "expected_processed_output": expected_processed_output,
        "expected_file_exists": expected_file_exists,
        "pair_covered_by_inventory": pair_covered,
        "coverage_status": coverage_status
    }

    if coverage_status == "covered":
        covered_required_targets.append(record)
    else:
        missing_required_targets.append(record)

missing_optional_targets = []
for target in optional_targets:
    symbol = target.get("symbol")
    timeframe = target.get("timeframe")
    expected_processed_output = target.get("expected_processed_output")
    expected_file_exists = Path(expected_processed_output).exists() if expected_processed_output else False
    pair_covered = (symbol, timeframe) in covered_pairs

    if not expected_file_exists and not pair_covered:
        missing_optional_targets.append({
            "symbol": symbol,
            "timeframe": timeframe,
            "priority": target.get("priority"),
            "expected_processed_output": expected_processed_output,
            "coverage_status": "missing_optional"
        })

target_coverage_complete = len(required_targets) > 0 and len(missing_required_targets) == 0

coverage_checks = {
    "safe_mode_active": safe_mode,
    "quality_report_present": QUALITY_REPORT.exists(),
    "quality_rules_present": QUALITY_RULES.exists(),
    "manifest_report_present": MANIFEST_REPORT.exists(),
    "manifest_file_present": MANIFEST_FILE.exists(),
    "plan_present": PLAN.exists(),
    "phase19_decision_present": PHASE19_DECISION.exists(),
    "phase18_closeout_present": PHASE18_CLOSEOUT.exists(),
    "selected_option_is_remain_on_hold": selected_option == "remain_on_hold",
    "selected_path_is_data_expansion_first": selected_path == "historical_data_expansion_first_then_strategy_rework",
    "quality_rules_ready": quality_rules_ready,
    "manifest_ready": manifest_ready,
    "historical_data_expansion_plan_ready": plan_ready,
    "phase19_decision_ready": phase19_decision_ready,
    "phase18_closed_safely": phase18_closed_safely,
    "required_targets_present": len(required_targets) > 0,
    "paper_shadow_not_started": quality_report.get("paper_shadow_started") is False,
    "paper_shadow_start_not_approved": quality_report.get("approved_for_paper_shadow_start") is False,
    "exchange_order_submission_disabled": quality_report.get("exchange_order_submission") is False,
    "micro_live_not_approved": quality_report.get("approved_for_micro_live_execution") is False,
    "real_live_not_approved": quality_report.get("approved_for_real_live_trading") is False,
}

blockers = [k for k, v in coverage_checks.items() if v is not True]
coverage_validation_ready = all(coverage_checks.values())

if coverage_validation_ready and target_coverage_complete:
    decision = "PHASE_19_HISTORICAL_DATASET_COVERAGE_VALIDATION_COMPLETE_FULL_COVERAGE_NOT_APPROVED_FOR_EXECUTION"
    next_phase = "Phase 19.6 — Historical Dataset Quality Validator"
elif coverage_validation_ready:
    decision = "PHASE_19_HISTORICAL_DATASET_COVERAGE_VALIDATION_COMPLETE_DATA_GAPS_IDENTIFIED_NOT_APPROVED_FOR_EXECUTION"
    next_phase = "Phase 19.6 — Historical Data Gap Fill Plan"
else:
    decision = "PHASE_19_HISTORICAL_DATASET_COVERAGE_VALIDATION_BLOCKED_REVIEW_REQUIRED"
    next_phase = "Phase 19.6 — Historical Dataset Coverage Review"

VALIDATOR_DIR.mkdir(parents=True, exist_ok=True)

coverage_record = {
    "phase": "phase_19_5_historical_dataset_coverage_validator_record",
    "created_at_unix": int(time.time()),
    "git_head": current_git_head,
    "system_state": "HOLD",
    "selected_option": selected_option,
    "selected_phase19_path": selected_path,
    "coverage_validation_ready": coverage_validation_ready,
    "target_coverage_complete": target_coverage_complete,
    "coverage_checks": coverage_checks,
    "blockers": blockers,
    "dataset_inventory": dataset_inventory,
    "covered_symbols": sorted(covered_symbols),
    "covered_symbol_timeframe_pairs": sorted([f"{s}:{tf}" for s, tf in covered_pairs]),
    "required_target_count": len(required_targets),
    "covered_required_target_count": len(covered_required_targets),
    "missing_required_target_count": len(missing_required_targets),
    "missing_optional_target_count": len(missing_optional_targets),
    "covered_required_targets": covered_required_targets,
    "missing_required_targets": missing_required_targets,
    "missing_optional_targets": missing_optional_targets,
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

coverage_file = VALIDATOR_DIR / "historical_dataset_coverage_validator.json"
missing_required_file = VALIDATOR_DIR / "historical_dataset_missing_required_targets.json"
inventory_file = VALIDATOR_DIR / "historical_dataset_inventory.json"

write_json(coverage_file, coverage_record)
write_json(missing_required_file, {
    "phase": "phase_19_5_missing_required_targets",
    "created_at_unix": int(time.time()),
    "missing_required_target_count": len(missing_required_targets),
    "missing_required_targets": missing_required_targets,
    "download_now": False,
    "execution_allowed": False
})
write_json(inventory_file, {
    "phase": "phase_19_5_dataset_inventory",
    "created_at_unix": int(time.time()),
    "dataset_file_count": len(dataset_inventory),
    "dataset_inventory": dataset_inventory
})
write_json(RUNTIME_OUT, coverage_record)

report = {
    "phase": "phase_19_5_historical_dataset_coverage_validator",
    "generated_at_unix": int(time.time()),
    "scope": "coverage_validation_only_no_download_no_execution",
    "git_head": current_git_head,
    "safety_flags": flags,
    "safe_mode_active": safe_mode,
    "git_working_tree_clean": git_clean_before_outputs,
    "selected_option": selected_option,
    "selected_phase19_path": selected_path,
    "coverage_validation_ready": coverage_validation_ready,
    "target_coverage_complete": target_coverage_complete,
    "coverage_checks": coverage_checks,
    "blockers": blockers,
    "dataset_file_count": len(dataset_inventory),
    "required_target_count": len(required_targets),
    "covered_required_target_count": len(covered_required_targets),
    "missing_required_target_count": len(missing_required_targets),
    "missing_optional_target_count": len(missing_optional_targets),
    "coverage_file": str(coverage_file),
    "missing_required_file": str(missing_required_file),
    "inventory_file": str(inventory_file),
    "runtime_coverage_file": str(RUNTIME_OUT),
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
        "This phase validates historical dataset coverage only.",
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
print(f"Runtime coverage written to: {RUNTIME_OUT}")
print(f"Coverage file written to: {coverage_file}")
print(f"Missing required file written to: {missing_required_file}")
print(f"Inventory file written to: {inventory_file}")
print(f"safe_mode_active={safe_mode}")
print(f"selected_option={selected_option}")
print(f"selected_phase19_path={selected_path}")
print(f"coverage_validation_ready={coverage_validation_ready}")
print(f"target_coverage_complete={target_coverage_complete}")
print(f"dataset_file_count={len(dataset_inventory)}")
print(f"required_target_count={len(required_targets)}")
print(f"missing_required_target_count={len(missing_required_targets)}")
print("paper_shadow_started=False")
print("approved_for_paper_shadow_start=False")
print("exchange_order_submission=False")
print("approved_for_micro_live_execution=False")
print("approved_for_real_live_trading=False")
print(f"decision={decision}")
