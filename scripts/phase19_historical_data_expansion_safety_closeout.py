import json, os, subprocess, time
from pathlib import Path

OUT = Path("data/processed/phase19_historical_data_expansion_safety_closeout.json")
RUNTIME_OUT = Path("runtime/phase19_historical_data_expansion_safety_closeout_state.json")
CLOSEOUT_DIR = Path("data/processed/phase19_strategy_rework")

HOLD_CONSOLIDATION = Path("data/processed/phase19_historical_data_expansion_hold_state_consolidation.json")
HOLD_CONSOLIDATION_RUNTIME = Path("runtime/phase19_historical_data_expansion_hold_state_consolidation_state.json")
NEXT_ACTION_SELECTION = Path("data/processed/phase19_historical_data_expansion_next_action_selection.json")
NEXT_ACTION_OPTIONS = Path("data/processed/phase19_historical_data_expansion_next_action_options.json")
COLLECTION_CLOSEOUT = Path("data/processed/phase19_offline_historical_data_collection_safety_closeout.json")
GAP_PLAN = Path("data/processed/phase19_historical_data_gap_fill_plan.json")
COVERAGE_VALIDATOR = Path("data/processed/phase19_historical_dataset_coverage_validator.json")
QUALITY_RULES = Path("data/processed/phase19_historical_data_quality_rules_builder.json")
MANIFEST = Path("data/processed/phase19_historical_data_expansion_manifest_builder.json")
PLAN = Path("data/processed/phase19_historical_data_expansion_plan.json")
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

hold = load_json(HOLD_CONSOLIDATION)
hold_runtime = load_json(HOLD_CONSOLIDATION_RUNTIME)
selection = load_json(NEXT_ACTION_SELECTION)
options = load_json(NEXT_ACTION_OPTIONS)
collection_closeout = load_json(COLLECTION_CLOSEOUT)
gap_plan = load_json(GAP_PLAN)
coverage = load_json(COVERAGE_VALIDATOR)
quality = load_json(QUALITY_RULES)
manifest = load_json(MANIFEST)
plan = load_json(PLAN)
phase18 = load_json(PHASE18_CLOSEOUT)

selected_option = (
    hold.get("selected_option")
    or hold_runtime.get("selected_option")
    or selection.get("selected_option")
    or options.get("selected_option")
    or collection_closeout.get("selected_option")
    or phase18.get("selected_option")
)

selected_path = (
    hold.get("selected_phase19_path")
    or hold_runtime.get("selected_phase19_path")
    or selection.get("selected_phase19_path")
    or options.get("selected_phase19_path")
    or collection_closeout.get("selected_phase19_path")
)

selected_next_action = (
    hold.get("selected_next_action")
    or hold_runtime.get("selected_next_action")
    or selection.get("selected_next_action")
    or options.get("selected_next_action")
)

hold_state_consolidated = (
    hold.get("hold_state_consolidated") is True
    or hold_runtime.get("hold_state_consolidated") is True
)

next_action_selection_ready = selection.get("next_action_selection_ready") is True
next_action_options_ready = options.get("next_action_options_ready") is True
collection_safety_closeout_passed = collection_closeout.get("collection_safety_closeout_passed") is True
gap_fill_plan_ready = gap_plan.get("gap_fill_plan_ready") is True
coverage_validation_ready = coverage.get("coverage_validation_ready") is True
quality_rules_ready = quality.get("quality_rules_ready") is True
manifest_ready = manifest.get("manifest_ready") is True
plan_ready = plan.get("historical_data_expansion_plan_ready") is True
phase18_closed_safely = phase18.get("phase18_closed_safely") is True

manual_collection_approval_granted = False
collection_start_allowed = False
download_allowed = False
network_download_allowed = False
execution_allowed = False

missing_required_target_count = (
    hold.get("missing_required_target_count")
    or selection.get("missing_required_target_count")
    or options.get("missing_required_target_count")
    or gap_plan.get("missing_required_target_count")
    or coverage.get("missing_required_target_count")
    or 0
)

target_count = (
    hold.get("target_count")
    or selection.get("target_count")
    or options.get("target_count")
    or collection_closeout.get("target_count")
    or coverage.get("required_target_count")
    or 0
)

closeout_checks = {
    "safe_mode_active": safe_mode,
    "hold_consolidation_present": HOLD_CONSOLIDATION.exists(),
    "hold_consolidation_runtime_present": HOLD_CONSOLIDATION_RUNTIME.exists(),
    "next_action_selection_present": NEXT_ACTION_SELECTION.exists(),
    "next_action_options_present": NEXT_ACTION_OPTIONS.exists(),
    "collection_closeout_present": COLLECTION_CLOSEOUT.exists(),
    "gap_plan_present": GAP_PLAN.exists(),
    "coverage_validator_present": COVERAGE_VALIDATOR.exists(),
    "quality_rules_present": QUALITY_RULES.exists(),
    "manifest_present": MANIFEST.exists(),
    "plan_present": PLAN.exists(),
    "phase18_closeout_present": PHASE18_CLOSEOUT.exists(),
    "selected_option_is_remain_on_hold": selected_option == "remain_on_hold",
    "selected_path_is_data_expansion_first": selected_path == "historical_data_expansion_first_then_strategy_rework",
    "selected_next_action_is_remain_on_hold": selected_next_action == "remain_on_hold",
    "hold_state_consolidated": hold_state_consolidated,
    "next_action_selection_ready": next_action_selection_ready,
    "next_action_options_ready": next_action_options_ready,
    "collection_safety_closeout_passed": collection_safety_closeout_passed,
    "gap_fill_plan_ready": gap_fill_plan_ready,
    "coverage_validation_ready": coverage_validation_ready,
    "quality_rules_ready": quality_rules_ready,
    "manifest_ready": manifest_ready,
    "historical_data_expansion_plan_ready": plan_ready,
    "phase18_closed_safely": phase18_closed_safely,
    "manual_collection_approval_not_granted": manual_collection_approval_granted is False,
    "collection_start_blocked": collection_start_allowed is False,
    "download_blocked": download_allowed is False,
    "network_download_blocked": network_download_allowed is False,
    "execution_blocked": execution_allowed is False,
    "paper_shadow_not_started": hold.get("paper_shadow_started") is False,
    "paper_shadow_start_not_approved": hold.get("approved_for_paper_shadow_start") is False,
    "exchange_order_submission_disabled": hold.get("exchange_order_submission") is False,
    "micro_live_not_approved": hold.get("approved_for_micro_live_execution") is False,
    "real_live_not_approved": hold.get("approved_for_real_live_trading") is False,
}

blockers = [k for k, v in closeout_checks.items() if v is not True]
phase19_safety_closeout_passed = all(closeout_checks.values())

if phase19_safety_closeout_passed:
    decision = "PHASE_19_HISTORICAL_DATA_EXPANSION_SAFETY_CLOSEOUT_COMPLETE_REMAIN_ON_HOLD_COLLECTION_NOT_APPROVED"
    next_phase = "Phase 20.1 — Strategy Rework Readiness Review"
else:
    decision = "PHASE_19_HISTORICAL_DATA_EXPANSION_SAFETY_CLOSEOUT_FAILED_REVIEW_REQUIRED"
    next_phase = "Phase 20.1 — Phase 19 Safety Closeout Fix"

CLOSEOUT_DIR.mkdir(parents=True, exist_ok=True)

closeout_record = {
    "phase": "phase_19_20_historical_data_expansion_safety_closeout_record",
    "created_at_unix": int(time.time()),
    "git_head": current_git_head,
    "system_state": "HOLD",
    "selected_option": selected_option,
    "selected_phase19_path": selected_path,
    "selected_next_action": selected_next_action,
    "phase19_safety_closeout_passed": phase19_safety_closeout_passed,
    "closeout_checks": closeout_checks,
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
    "final_phase19_state": {
        "phase19_status": "closed_safely",
        "historical_data_expansion_state": "remain_on_hold",
        "offline_collection_state": "closed_blocked_manual_approval_required",
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
        "approved_for_real_live_trading": False
    },
    "allowed_next_actions": [
        "strategy_rework_readiness_review",
        "manual_data_source_review_only",
        "documentation_only",
        "hold_state_monitoring"
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

closeout_file = CLOSEOUT_DIR / "historical_data_expansion_safety_closeout.json"

write_json(closeout_file, closeout_record)
write_json(RUNTIME_OUT, closeout_record)

report = {
    "phase": "phase_19_20_historical_data_expansion_safety_closeout",
    "generated_at_unix": int(time.time()),
    "scope": "phase19_safety_closeout_only_no_collection_no_download_no_execution",
    "git_head": current_git_head,
    "safety_flags": flags,
    "safe_mode_active": safe_mode,
    "git_working_tree_clean": git_clean_before_outputs,
    "selected_option": selected_option,
    "selected_phase19_path": selected_path,
    "selected_next_action": selected_next_action,
    "phase19_safety_closeout_passed": phase19_safety_closeout_passed,
    "closeout_checks": closeout_checks,
    "blockers": blockers,
    "missing_required_target_count": missing_required_target_count,
    "target_count": target_count,
    "closeout_file": str(closeout_file),
    "runtime_closeout_file": str(RUNTIME_OUT),
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
        "This phase safely closes Phase 19 historical data expansion.",
        "Phase 19 remains on hold.",
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
print(f"Runtime closeout written to: {RUNTIME_OUT}")
print(f"Closeout file written to: {closeout_file}")
print(f"safe_mode_active={safe_mode}")
print(f"selected_option={selected_option}")
print(f"selected_phase19_path={selected_path}")
print(f"selected_next_action={selected_next_action}")
print(f"phase19_safety_closeout_passed={phase19_safety_closeout_passed}")
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
