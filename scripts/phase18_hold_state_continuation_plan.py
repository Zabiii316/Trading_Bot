import json, os, subprocess, time
from pathlib import Path

OUT = Path("data/processed/phase18_hold_state_continuation_plan.json")
RUNTIME_OUT = Path("runtime/phase18_hold_state_continuation_plan_state.json")
PLAN_DIR = Path("data/processed/phase18_hold_monitoring")

CLOSEOUT = Path("data/processed/phase18_hold_state_closeout_report.json")
RUNTIME_CLOSEOUT = Path("runtime/phase18_hold_state_closeout_report_state.json")
EVIDENCE_INDEX = Path("data/processed/phase18_hold_state_evidence_index.json")
WEEKLY_SUMMARY = Path("data/processed/phase18_hold_state_weekly_review_summary.json")
NEXT_ACTION = Path("data/processed/phase18_next_action_selection.json")
PHASE17_CLOSEOUT = Path("data/processed/phase17_safety_closeout_next_action_options.json")

def run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True)

def git_clean():
    return run(["git", "status", "--short"]).stdout.strip() == ""

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

def any_true(*values):
    return any(v is True for v in values)

flags = {
    "BINANCE_TESTNET": os.getenv("BINANCE_TESTNET", ""),
    "BINANCE_USE_TESTNET": os.getenv("BINANCE_USE_TESTNET", ""),
    "BINANCE_ENABLE_LIVE_TRADING": os.getenv("BINANCE_ENABLE_LIVE_TRADING", ""),
    "LIVE_TRADING_ALLOWED": os.getenv("LIVE_TRADING_ALLOWED", ""),
}

safe_mode = flags["BINANCE_ENABLE_LIVE_TRADING"] == "false" and flags["LIVE_TRADING_ALLOWED"] == "false"
git_clean_before_outputs = git_clean()

closeout = load_json(CLOSEOUT)
runtime_closeout = load_json(RUNTIME_CLOSEOUT)
evidence_index = load_json(EVIDENCE_INDEX)
weekly_summary = load_json(WEEKLY_SUMMARY)
next_action = load_json(NEXT_ACTION)
phase17_closeout = load_json(PHASE17_CLOSEOUT)

records = [
    closeout,
    runtime_closeout,
    evidence_index,
    weekly_summary,
    next_action,
    phase17_closeout,
]

selected_option = (
    closeout.get("selected_option")
    or runtime_closeout.get("selected_option")
    or evidence_index.get("selected_option")
    or weekly_summary.get("selected_option")
    or next_action.get("selected_option")
)

hold_state_closeout_passed = (
    closeout.get("hold_state_closeout_passed") is True
    or runtime_closeout.get("hold_state_closeout_passed") is True
)

evidence_index_ready = evidence_index.get("evidence_index_ready") is True
weekly_summary_passed = weekly_summary.get("weekly_summary_passed") is True
phase17_closed_safely = phase17_closeout.get("phase17_closed_safely") is True

paper_shadow_started = any_true(*[r.get("paper_shadow_started") for r in records])
approved_for_paper_shadow_start = any_true(*[r.get("approved_for_paper_shadow_start") for r in records])
exchange_order_submission = any_true(*[r.get("exchange_order_submission") for r in records])
approved_for_micro_live_execution = any_true(*[r.get("approved_for_micro_live_execution") for r in records])
approved_for_real_live_trading = any_true(*[r.get("approved_for_real_live_trading") for r in records])

continuation_checks = {
    "safe_mode_active": safe_mode,
    "closeout_present": CLOSEOUT.exists(),
    "runtime_closeout_present": RUNTIME_CLOSEOUT.exists(),
    "evidence_index_present": EVIDENCE_INDEX.exists(),
    "weekly_summary_present": WEEKLY_SUMMARY.exists(),
    "next_action_present": NEXT_ACTION.exists(),
    "phase17_closeout_present": PHASE17_CLOSEOUT.exists(),
    "selected_option_is_remain_on_hold": selected_option == "remain_on_hold",
    "hold_state_closeout_passed": hold_state_closeout_passed,
    "evidence_index_ready": evidence_index_ready,
    "weekly_summary_passed": weekly_summary_passed,
    "phase17_closed_safely": phase17_closed_safely,
    "paper_shadow_not_started": paper_shadow_started is False,
    "paper_shadow_start_not_approved": approved_for_paper_shadow_start is False,
    "exchange_order_submission_disabled": exchange_order_submission is False,
    "micro_live_not_approved": approved_for_micro_live_execution is False,
    "real_live_not_approved": approved_for_real_live_trading is False,
}

blockers = [k for k, v in continuation_checks.items() if v is not True]
continuation_plan_ready = all(continuation_checks.values())

PLAN_DIR.mkdir(parents=True, exist_ok=True)

if continuation_plan_ready:
    decision = "PHASE_18_HOLD_STATE_CONTINUATION_PLAN_CREATED_HOLD_CONFIRMED_NOT_APPROVED_FOR_EXECUTION"
    next_phase = "Phase 18.12 — Hold State Continuation Health Check"
else:
    decision = "PHASE_18_HOLD_STATE_CONTINUATION_PLAN_BLOCKED_REVIEW_REQUIRED"
    next_phase = "Phase 18.12 — Hold State Continuation Review"

continuation_plan = {
    "phase": "phase_18_11_hold_state_continuation_plan_record",
    "created_at_unix": int(time.time()),
    "selected_option": selected_option,
    "continuation_plan_ready": continuation_plan_ready,
    "continuation_checks": continuation_checks,
    "blockers": blockers,
    "system_state": "HOLD",
    "execution_allowed": False,
    "paper_shadow_execution_allowed": False,
    "exchange_order_submission_allowed": False,
    "real_capital_allowed": False,
    "live_trading_allowed": False,
    "continuation_cadence": {
        "daily": [
            "confirm_safe_trading_flags",
            "confirm_no_paper_shadow_started",
            "confirm_no_exchange_order_submission",
            "confirm_no_micro_live_approval",
            "confirm_no_real_live_trading_approval"
        ],
        "weekly": [
            "review_monitoring_dashboards",
            "review_hold_state_evidence",
            "confirm_git_evidence_committed",
            "confirm_runtime_hold_files_consistent"
        ],
        "monthly_or_before_any_change": [
            "review_strategy_status",
            "review historical data coverage",
            "review whether to remain on hold or start a new approval path",
            "do_not_enable_execution_without_new explicit approval phases"
        ]
    },
    "allowed_next_actions": [
        "continue_hold_state_monitoring",
        "strategy_rework_only",
        "historical_data_expansion_only",
        "dashboard_review_only",
        "documentation_cleanup_only"
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

plan_file = PLAN_DIR / "hold_state_continuation_plan.json"
write_json(plan_file, continuation_plan)
write_json(RUNTIME_OUT, continuation_plan)

report = {
    "phase": "phase_18_11_hold_state_continuation_plan",
    "generated_at_unix": int(time.time()),
    "scope": "hold_state_continuation_plan_only",
    "selected_option": selected_option,
    "safety_flags": flags,
    "safe_mode_active": safe_mode,
    "git_working_tree_clean": git_clean_before_outputs,
    "continuation_plan_ready": continuation_plan_ready,
    "continuation_checks": continuation_checks,
    "blockers": blockers,
    "paper_shadow_started": False,
    "approved_for_paper_shadow_start": False,
    "exchange_order_submission": False,
    "real_capital_allowed": False,
    "live_trading_enabled": False,
    "approved_for_micro_live_execution": False,
    "approved_for_real_live_trading": False,
    "plan_file": str(plan_file),
    "runtime_plan_file": str(RUNTIME_OUT),
    "decision": decision,
    "next_phase": next_phase,
    "safety_notes": [
        "This phase creates a hold-state continuation plan only.",
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
print(f"continuation_plan_ready={continuation_plan_ready}")
print("paper_shadow_started=False")
print("approved_for_paper_shadow_start=False")
print("exchange_order_submission=False")
print("approved_for_micro_live_execution=False")
print("approved_for_real_live_trading=False")
print(f"decision={decision}")
