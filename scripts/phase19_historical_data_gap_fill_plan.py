import json, os, subprocess, time
from pathlib import Path

OUT = Path("data/processed/phase19_historical_data_gap_fill_plan.json")
RUNTIME_OUT = Path("runtime/phase19_historical_data_gap_fill_plan_state.json")
PLAN_DIR = Path("data/processed/phase19_strategy_rework")

COVERAGE_REPORT = Path("data/processed/phase19_historical_dataset_coverage_validator.json")
COVERAGE_FILE = Path("data/processed/phase19_strategy_rework/historical_dataset_coverage_validator.json")
MISSING_REQUIRED = Path("data/processed/phase19_strategy_rework/historical_dataset_missing_required_targets.json")
MANIFEST_FILE = Path("data/processed/phase19_strategy_rework/historical_data_expansion_manifest.json")
QUALITY_RULES = Path("data/processed/phase19_strategy_rework/historical_data_quality_rules.json")
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

coverage_report = load_json(COVERAGE_REPORT)
coverage_file = load_json(COVERAGE_FILE)
missing_required_file = load_json(MISSING_REQUIRED)
manifest = load_json(MANIFEST_FILE)
quality_rules = load_json(QUALITY_RULES)
phase18_closeout = load_json(PHASE18_CLOSEOUT)

selected_option = (
    coverage_report.get("selected_option")
    or coverage_file.get("selected_option")
    or manifest.get("selected_option")
    or phase18_closeout.get("selected_option")
)

selected_path = (
    coverage_report.get("selected_phase19_path")
    or coverage_file.get("selected_phase19_path")
    or manifest.get("selected_phase19_path")
)

coverage_validation_ready = (
    coverage_report.get("coverage_validation_ready") is True
    or coverage_file.get("coverage_validation_ready") is True
)

target_coverage_complete = (
    coverage_report.get("target_coverage_complete") is True
    or coverage_file.get("target_coverage_complete") is True
)

quality_rules_ready = quality_rules.get("quality_rules_ready") is True
phase18_closed_safely = phase18_closeout.get("phase18_closed_safely") is True

missing_required_targets = (
    coverage_report.get("missing_required_targets")
    or coverage_file.get("missing_required_targets")
    or missing_required_file.get("missing_required_targets")
    or []
)

gap_fill_needed = len(missing_required_targets) > 0

gap_fill_plan_items = []
for target in missing_required_targets:
    symbol = target.get("symbol")
    timeframe = target.get("timeframe")
    expected_output = target.get("expected_processed_output")

    gap_fill_plan_items.append({
        "symbol": symbol,
        "timeframe": timeframe,
        "priority": "required",
        "gap_status": "missing",
        "expected_processed_output": expected_output,
        "collection_mode": "offline_historical_dataset_build_only",
        "download_now": False,
        "execution_allowed": False,
        "paper_shadow_allowed": False,
        "live_trading_allowed": False,
        "required_validation_before_use": [
            "schema_required_columns",
            "timestamps_no_duplicates",
            "timestamps_monotonic",
            "prices_positive",
            "ohlc_consistency",
            "volume_non_negative",
            "minimum_history_window"
        ]
    })

gap_fill_checks = {
    "safe_mode_active": safe_mode,
    "coverage_report_present": COVERAGE_REPORT.exists(),
    "coverage_file_present": COVERAGE_FILE.exists(),
    "missing_required_file_present": MISSING_REQUIRED.exists(),
    "manifest_file_present": MANIFEST_FILE.exists(),
    "quality_rules_present": QUALITY_RULES.exists(),
    "phase18_closeout_present": PHASE18_CLOSEOUT.exists(),
    "selected_option_is_remain_on_hold": selected_option == "remain_on_hold",
    "selected_path_is_data_expansion_first": selected_path == "historical_data_expansion_first_then_strategy_rework",
    "coverage_validation_ready": coverage_validation_ready,
    "quality_rules_ready": quality_rules_ready,
    "phase18_closed_safely": phase18_closed_safely,
    "paper_shadow_not_started": coverage_report.get("paper_shadow_started") is False,
    "paper_shadow_start_not_approved": coverage_report.get("approved_for_paper_shadow_start") is False,
    "exchange_order_submission_disabled": coverage_report.get("exchange_order_submission") is False,
    "micro_live_not_approved": coverage_report.get("approved_for_micro_live_execution") is False,
    "real_live_not_approved": coverage_report.get("approved_for_real_live_trading") is False,
}

blockers = [k for k, v in gap_fill_checks.items() if v is not True]
gap_fill_plan_ready = all(gap_fill_checks.values())

if gap_fill_plan_ready and gap_fill_needed:
    decision = "PHASE_19_HISTORICAL_DATA_GAP_FILL_PLAN_CREATED_GAPS_IDENTIFIED_NOT_APPROVED_FOR_EXECUTION"
    next_phase = "Phase 19.7 — Offline Historical Data Collection Script Builder"
elif gap_fill_plan_ready:
    decision = "PHASE_19_HISTORICAL_DATA_GAP_FILL_PLAN_CREATED_NO_REQUIRED_GAPS_NOT_APPROVED_FOR_EXECUTION"
    next_phase = "Phase 19.7 — Historical Dataset Quality Validator"
else:
    decision = "PHASE_19_HISTORICAL_DATA_GAP_FILL_PLAN_BLOCKED_REVIEW_REQUIRED"
    next_phase = "Phase 19.7 — Historical Data Gap Fill Plan Review"

PLAN_DIR.mkdir(parents=True, exist_ok=True)

gap_fill_plan = {
    "phase": "phase_19_6_historical_data_gap_fill_plan_record",
    "created_at_unix": int(time.time()),
    "git_head": current_git_head,
    "system_state": "HOLD",
    "selected_option": selected_option,
    "selected_phase19_path": selected_path,
    "gap_fill_plan_ready": gap_fill_plan_ready,
    "gap_fill_needed": gap_fill_needed,
    "target_coverage_complete": target_coverage_complete,
    "gap_fill_checks": gap_fill_checks,
    "blockers": blockers,
    "missing_required_target_count": len(missing_required_targets),
    "gap_fill_plan_items": gap_fill_plan_items,
    "allowed_actions": [
        "offline_collection_script_build_only",
        "offline_dataset_import_only",
        "offline_dataset_quality_validation_only",
        "offline_manifest_update_only"
    ],
    "blocked_actions": [
        "paper_shadow_start",
        "micro_live_execution",
        "real_live_trading",
        "exchange_order_submission",
        "real_capital_usage",
        "production_api_key_usage"
    ],
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

plan_file = PLAN_DIR / "historical_data_gap_fill_plan.json"
write_json(plan_file, gap_fill_plan)
write_json(RUNTIME_OUT, gap_fill_plan)

report = {
    "phase": "phase_19_6_historical_data_gap_fill_plan",
    "generated_at_unix": int(time.time()),
    "scope": "gap_fill_plan_only_no_download_no_execution",
    "git_head": current_git_head,
    "safety_flags": flags,
    "safe_mode_active": safe_mode,
    "git_working_tree_clean": git_clean_before_outputs,
    "selected_option": selected_option,
    "selected_phase19_path": selected_path,
    "gap_fill_plan_ready": gap_fill_plan_ready,
    "gap_fill_needed": gap_fill_needed,
    "target_coverage_complete": target_coverage_complete,
    "missing_required_target_count": len(missing_required_targets),
    "gap_fill_checks": gap_fill_checks,
    "blockers": blockers,
    "plan_file": str(plan_file),
    "runtime_plan_file": str(RUNTIME_OUT),
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
        "This phase creates a historical data gap-fill plan only.",
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
print(f"Runtime plan written to: {RUNTIME_OUT}")
print(f"Plan written to: {plan_file}")
print(f"safe_mode_active={safe_mode}")
print(f"selected_option={selected_option}")
print(f"selected_phase19_path={selected_path}")
print(f"gap_fill_plan_ready={gap_fill_plan_ready}")
print(f"gap_fill_needed={gap_fill_needed}")
print(f"missing_required_target_count={len(missing_required_targets)}")
print("paper_shadow_started=False")
print("approved_for_paper_shadow_start=False")
print("exchange_order_submission=False")
print("approved_for_micro_live_execution=False")
print("approved_for_real_live_trading=False")
print(f"decision={decision}")
