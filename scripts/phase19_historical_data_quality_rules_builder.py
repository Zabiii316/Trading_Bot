import json, os, subprocess, time
from pathlib import Path

OUT = Path("data/processed/phase19_historical_data_quality_rules_builder.json")
RUNTIME_OUT = Path("runtime/phase19_historical_data_quality_rules_builder_state.json")
RULES_DIR = Path("data/processed/phase19_strategy_rework")

MANIFEST_REPORT = Path("data/processed/phase19_historical_data_expansion_manifest_builder.json")
MANIFEST_FILE = Path("data/processed/phase19_strategy_rework/historical_data_expansion_manifest.json")
PLAN = Path("data/processed/phase19_historical_data_expansion_plan.json")
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

manifest_report = load_json(MANIFEST_REPORT)
manifest_file = load_json(MANIFEST_FILE)
plan = load_json(PLAN)
phase19_decision = load_json(PHASE19_DECISION)
phase18_closeout = load_json(PHASE18_CLOSEOUT)

selected_option = (
    manifest_report.get("selected_option")
    or manifest_file.get("selected_option")
    or plan.get("selected_option")
    or phase19_decision.get("selected_option")
    or phase18_closeout.get("selected_option")
)

selected_path = (
    manifest_report.get("selected_phase19_path")
    or manifest_file.get("selected_phase19_path")
    or plan.get("selected_phase19_path")
    or phase19_decision.get("selected_phase19_path")
)

manifest_ready = (
    manifest_report.get("manifest_ready") is True
    or manifest_file.get("manifest_ready") is True
)

plan_ready = plan.get("historical_data_expansion_plan_ready") is True
phase19_decision_ready = phase19_decision.get("phase19_decision_ready") is True
phase18_closed_safely = phase18_closeout.get("phase18_closed_safely") is True

required_targets = manifest_file.get("required_manifest_targets", [])
optional_targets = manifest_file.get("optional_manifest_targets", [])

quality_rules = {
    "schema_rules": [
        {
            "rule_id": "schema_required_columns",
            "description": "Each OHLCV row must include timestamp, open, high, low, close, volume, symbol, and timeframe.",
            "severity": "critical",
            "action": "reject_file"
        },
        {
            "rule_id": "schema_numeric_prices",
            "description": "open, high, low, and close must be numeric values.",
            "severity": "critical",
            "action": "reject_row"
        },
        {
            "rule_id": "schema_numeric_volume",
            "description": "volume must be numeric.",
            "severity": "critical",
            "action": "reject_row"
        }
    ],
    "timestamp_rules": [
        {
            "rule_id": "timestamps_not_empty",
            "description": "timestamp field must not be empty.",
            "severity": "critical",
            "action": "reject_row"
        },
        {
            "rule_id": "timestamps_monotonic",
            "description": "timestamps must be strictly increasing after sorting.",
            "severity": "critical",
            "action": "flag_file"
        },
        {
            "rule_id": "timestamps_no_duplicates",
            "description": "duplicate timestamps for the same symbol and timeframe are not allowed.",
            "severity": "critical",
            "action": "deduplicate_or_reject"
        },
        {
            "rule_id": "time_gap_detection",
            "description": "large gaps between candles must be flagged for review.",
            "severity": "warning",
            "action": "flag_file"
        }
    ],
    "price_rules": [
        {
            "rule_id": "prices_positive",
            "description": "open, high, low, and close must be greater than zero.",
            "severity": "critical",
            "action": "reject_row"
        },
        {
            "rule_id": "ohlc_consistency",
            "description": "high must be greater than or equal to open, low, and close; low must be less than or equal to open, high, and close.",
            "severity": "critical",
            "action": "reject_row"
        },
        {
            "rule_id": "extreme_price_move_flag",
            "description": "single-candle close-to-close moves above 15 percent must be flagged.",
            "severity": "warning",
            "threshold_pct": 15,
            "action": "flag_row"
        }
    ],
    "volume_rules": [
        {
            "rule_id": "volume_non_negative",
            "description": "volume must not be negative.",
            "severity": "critical",
            "action": "reject_row"
        },
        {
            "rule_id": "zero_volume_flag",
            "description": "zero-volume candles are allowed only if explicitly reviewed.",
            "severity": "warning",
            "action": "flag_row"
        }
    ],
    "coverage_rules": [
        {
            "rule_id": "minimum_history_window",
            "description": "required symbols should target at least 90 days of usable historical candles.",
            "severity": "critical",
            "minimum_days": 90,
            "action": "flag_symbol_timeframe"
        },
        {
            "rule_id": "preferred_history_window",
            "description": "preferred coverage target is 180 days.",
            "severity": "warning",
            "preferred_days": 180,
            "action": "flag_symbol_timeframe"
        },
        {
            "rule_id": "required_symbol_timeframe_coverage",
            "description": "BTCUSDT, ETHUSDT, and BNBUSDT should have 1m, 5m, 15m, and 1h datasets.",
            "severity": "critical",
            "action": "flag_missing_target"
        }
    ],
    "safety_rules": [
        {
            "rule_id": "offline_only",
            "description": "Quality validation must run offline and must not submit orders.",
            "severity": "critical",
            "action": "block_execution"
        },
        {
            "rule_id": "no_live_trading",
            "description": "Live trading flags must remain disabled.",
            "severity": "critical",
            "action": "block_execution"
        },
        {
            "rule_id": "no_real_capital",
            "description": "No real capital or production API keys may be used.",
            "severity": "critical",
            "action": "block_execution"
        }
    ]
}

quality_rule_checks = {
    "safe_mode_active": safe_mode,
    "manifest_report_present": MANIFEST_REPORT.exists(),
    "manifest_file_present": MANIFEST_FILE.exists(),
    "plan_present": PLAN.exists(),
    "phase19_decision_present": PHASE19_DECISION.exists(),
    "phase18_closeout_present": PHASE18_CLOSEOUT.exists(),
    "selected_option_is_remain_on_hold": selected_option == "remain_on_hold",
    "selected_path_is_data_expansion_first": selected_path == "historical_data_expansion_first_then_strategy_rework",
    "manifest_ready": manifest_ready,
    "historical_data_expansion_plan_ready": plan_ready,
    "phase19_decision_ready": phase19_decision_ready,
    "phase18_closed_safely": phase18_closed_safely,
    "required_targets_present": len(required_targets) > 0,
    "paper_shadow_not_started": manifest_report.get("paper_shadow_started") is False,
    "paper_shadow_start_not_approved": manifest_report.get("approved_for_paper_shadow_start") is False,
    "exchange_order_submission_disabled": manifest_report.get("exchange_order_submission") is False,
    "micro_live_not_approved": manifest_report.get("approved_for_micro_live_execution") is False,
    "real_live_not_approved": manifest_report.get("approved_for_real_live_trading") is False,
}

blockers = [k for k, v in quality_rule_checks.items() if v is not True]
quality_rules_ready = all(quality_rule_checks.values())

RULES_DIR.mkdir(parents=True, exist_ok=True)

if quality_rules_ready:
    decision = "PHASE_19_HISTORICAL_DATA_QUALITY_RULES_CREATED_NOT_APPROVED_FOR_EXECUTION"
    next_phase = "Phase 19.5 — Historical Dataset Coverage Validator"
else:
    decision = "PHASE_19_HISTORICAL_DATA_QUALITY_RULES_BLOCKED_REVIEW_REQUIRED"
    next_phase = "Phase 19.5 — Historical Data Quality Rules Review"

rules_record = {
    "phase": "phase_19_4_historical_data_quality_rules_record",
    "created_at_unix": int(time.time()),
    "git_head": current_git_head,
    "system_state": "HOLD",
    "selected_option": selected_option,
    "selected_phase19_path": selected_path,
    "quality_rules_ready": quality_rules_ready,
    "quality_rule_checks": quality_rule_checks,
    "blockers": blockers,
    "required_target_count": len(required_targets),
    "optional_target_count": len(optional_targets),
    "quality_rules": quality_rules,
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

rules_file = RULES_DIR / "historical_data_quality_rules.json"
write_json(rules_file, rules_record)
write_json(RUNTIME_OUT, rules_record)

report = {
    "phase": "phase_19_4_historical_data_quality_rules_builder",
    "generated_at_unix": int(time.time()),
    "scope": "quality_rules_builder_only_no_download_no_execution",
    "git_head": current_git_head,
    "safety_flags": flags,
    "safe_mode_active": safe_mode,
    "git_working_tree_clean": git_clean_before_outputs,
    "selected_option": selected_option,
    "selected_phase19_path": selected_path,
    "quality_rules_ready": quality_rules_ready,
    "quality_rule_checks": quality_rule_checks,
    "blockers": blockers,
    "required_target_count": len(required_targets),
    "optional_target_count": len(optional_targets),
    "rules_file": str(rules_file),
    "runtime_rules_file": str(RUNTIME_OUT),
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
        "This phase builds historical data quality rules only.",
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
print(f"Runtime rules written to: {RUNTIME_OUT}")
print(f"Rules written to: {rules_file}")
print(f"safe_mode_active={safe_mode}")
print(f"selected_option={selected_option}")
print(f"selected_phase19_path={selected_path}")
print(f"quality_rules_ready={quality_rules_ready}")
print(f"required_target_count={len(required_targets)}")
print(f"optional_target_count={len(optional_targets)}")
print("paper_shadow_started=False")
print("approved_for_paper_shadow_start=False")
print("exchange_order_submission=False")
print("approved_for_micro_live_execution=False")
print("approved_for_real_live_trading=False")
print(f"decision={decision}")
