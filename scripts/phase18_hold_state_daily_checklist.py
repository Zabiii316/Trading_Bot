import json, os, subprocess, time
from pathlib import Path

OUT = Path("data/processed/phase18_hold_state_daily_checklist.json")
RUNTIME_OUT = Path("runtime/phase18_hold_state_daily_checklist_state.json")
CHECKLIST_DIR = Path("data/processed/phase18_hold_monitoring")

REPORT_INPUT = Path("data/processed/phase18_hold_state_monitoring_report.json")
RUNTIME_REPORT = Path("runtime/phase18_hold_state_monitoring_report_state.json")
PLAN_INPUT = Path("data/processed/phase18_hold_state_monitoring_plan.json")
HEALTH_INPUT = Path("data/processed/phase18_hold_state_monitoring_health_check.json")
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

report_input = load_json(REPORT_INPUT)
runtime_report = load_json(RUNTIME_REPORT)
plan_input = load_json(PLAN_INPUT)
health_input = load_json(HEALTH_INPUT)
next_action = load_json(NEXT_ACTION)
phase17_closeout = load_json(PHASE17_CLOSEOUT)

selected_option = (
    report_input.get("selected_option")
    or runtime_report.get("selected_option")
    or plan_input.get("selected_option")
    or next_action.get("selected_option")
)

hold_report_passed = (
    report_input.get("hold_state_report_passed") is True
    or runtime_report.get("hold_state_report_passed") is True
)

monitoring_plan_ready = (
    report_input.get("monitoring_plan_ready") is True
    or plan_input.get("monitoring_plan_ready") is True
)

core_hold_health_passed = (
    report_input.get("core_hold_health_passed") is True
    or health_input.get("core_hold_health_passed") is True
)

paper_shadow_started = any_true(
    report_input.get("paper_shadow_started"),
    runtime_report.get("paper_shadow_started"),
    plan_input.get("paper_shadow_started"),
    health_input.get("paper_shadow_started"),
    next_action.get("paper_shadow_started"),
    phase17_closeout.get("paper_shadow_started")
)

approved_for_paper_shadow_start = any_true(
    report_input.get("approved_for_paper_shadow_start"),
    runtime_report.get("approved_for_paper_shadow_start"),
    plan_input.get("approved_for_paper_shadow_start"),
    health_input.get("approved_for_paper_shadow_start"),
    next_action.get("approved_for_paper_shadow_start"),
    phase17_closeout.get("approved_for_paper_shadow_start")
)

exchange_order_submission = any_true(
    report_input.get("exchange_order_submission"),
    runtime_report.get("exchange_order_submission"),
    plan_input.get("exchange_order_submission"),
    health_input.get("exchange_order_submission"),
    next_action.get("exchange_order_submission"),
    phase17_closeout.get("exchange_order_submission")
)

approved_for_micro_live_execution = any_true(
    report_input.get("approved_for_micro_live_execution"),
    runtime_report.get("approved_for_micro_live_execution"),
    plan_input.get("approved_for_micro_live_execution"),
    health_input.get("approved_for_micro_live_execution"),
    next_action.get("approved_for_micro_live_execution"),
    phase17_closeout.get("approved_for_micro_live_execution")
)

approved_for_real_live_trading = any_true(
    report_input.get("approved_for_real_live_trading"),
    runtime_report.get("approved_for_real_live_trading"),
    plan_input.get("approved_for_real_live_trading"),
    health_input.get("approved_for_real_live_trading"),
    next_action.get("approved_for_real_live_trading"),
    phase17_closeout.get("approved_for_real_live_trading")
)

daily_checks = {
    "safe_mode_active": safe_mode,
    "report_input_present": REPORT_INPUT.exists(),
    "runtime_report_present": RUNTIME_REPORT.exists(),
    "plan_input_present": PLAN_INPUT.exists(),
    "health_input_present": HEALTH_INPUT.exists(),
    "next_action_present": NEXT_ACTION.exists(),
    "phase17_closeout_present": PHASE17_CLOSEOUT.exists(),
    "selected_option_is_remain_on_hold": selected_option == "remain_on_hold",
    "hold_state_report_passed": hold_report_passed,
    "monitoring_plan_ready": monitoring_plan_ready,
    "core_hold_health_passed": core_hold_health_passed,
    "paper_shadow_not_started": paper_shadow_started is False,
    "paper_shadow_start_not_approved": approved_for_paper_shadow_start is False,
    "exchange_order_submission_disabled": exchange_order_submission is False,
    "micro_live_not_approved": approved_for_micro_live_execution is False,
    "real_live_not_approved": approved_for_real_live_trading is False,
}

blockers = [k for k, v in daily_checks.items() if v is not True]
daily_checklist_ready = all(daily_checks.values())

checklist_items = [
    {
        "item": "Confirm safe trading flags",
        "required_state": "BINANCE_ENABLE_LIVE_TRADING=false and LIVE_TRADING_ALLOWED=false",
        "status": "passed" if safe_mode else "failed"
    },
    {
        "item": "Confirm selected option remains hold",
        "required_state": "selected_option=remain_on_hold",
        "status": "passed" if selected_option == "remain_on_hold" else "failed"
    },
    {
        "item": "Confirm paper shadow has not started",
        "required_state": "paper_shadow_started=False",
        "status": "passed" if paper_shadow_started is False else "failed"
    },
    {
        "item": "Confirm paper shadow start is not approved",
        "required_state": "approved_for_paper_shadow_start=False",
        "status": "passed" if approved_for_paper_shadow_start is False else "failed"
    },
    {
        "item": "Confirm exchange order submission is disabled",
        "required_state": "exchange_order_submission=False",
        "status": "passed" if exchange_order_submission is False else "failed"
    },
    {
        "item": "Confirm micro-live is not approved",
        "required_state": "approved_for_micro_live_execution=False",
        "status": "passed" if approved_for_micro_live_execution is False else "failed"
    },
    {
        "item": "Confirm real live trading is not approved",
        "required_state": "approved_for_real_live_trading=False",
        "status": "passed" if approved_for_real_live_trading is False else "failed"
    },
    {
        "item": "Review dashboard health",
        "required_state": "dashboard review only, no execution",
        "status": "manual_review"
    },
    {
        "item": "Review git status",
        "required_state": "clean or evidence intentionally committed",
        "status": "passed" if git_clean_before_outputs else "review"
    }
]

CHECKLIST_DIR.mkdir(parents=True, exist_ok=True)

if daily_checklist_ready:
    decision = "PHASE_18_HOLD_STATE_DAILY_CHECKLIST_CREATED_HOLD_CONFIRMED_NOT_APPROVED_FOR_EXECUTION"
    next_phase = "Phase 18.6 — Hold State Weekly Dashboard Review Plan"
else:
    decision = "PHASE_18_HOLD_STATE_DAILY_CHECKLIST_BLOCKED_REVIEW_REQUIRED"
    next_phase = "Phase 18.6 — Hold State Checklist Review"

checklist_record = {
    "phase": "phase_18_5_hold_state_daily_checklist_record",
    "created_at_unix": int(time.time()),
    "selected_option": selected_option,
    "daily_checklist_ready": daily_checklist_ready,
    "daily_checks": daily_checks,
    "checklist_items": checklist_items,
    "blockers": blockers,
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

checklist_file = CHECKLIST_DIR / "hold_state_daily_checklist.json"
write_json(checklist_file, checklist_record)
write_json(RUNTIME_OUT, checklist_record)

report = {
    "phase": "phase_18_5_hold_state_daily_checklist",
    "generated_at_unix": int(time.time()),
    "scope": "hold_state_daily_checklist_only",
    "selected_option": selected_option,
    "safety_flags": flags,
    "safe_mode_active": safe_mode,
    "git_working_tree_clean": git_clean_before_outputs,
    "daily_checklist_ready": daily_checklist_ready,
    "daily_checks": daily_checks,
    "checklist_items": checklist_items,
    "blockers": blockers,
    "paper_shadow_started": False,
    "approved_for_paper_shadow_start": False,
    "exchange_order_submission": False,
    "real_capital_allowed": False,
    "live_trading_enabled": False,
    "approved_for_micro_live_execution": False,
    "approved_for_real_live_trading": False,
    "checklist_file": str(checklist_file),
    "runtime_checklist_file": str(RUNTIME_OUT),
    "decision": decision,
    "next_phase": next_phase,
    "safety_notes": [
        "This phase creates a daily hold-state checklist only.",
        "This phase does not start paper shadow execution.",
        "This phase does not approve micro-live execution.",
        "This phase does not approve real live trading.",
        "This phase does not submit Binance orders.",
        "Real capital and exchange order submission remain disabled."
    ]
}

write_json(OUT, report)

print(f"Report written to: {OUT}")
print(f"Runtime checklist written to: {RUNTIME_OUT}")
print(f"Checklist written to: {checklist_file}")
print(f"safe_mode_active={safe_mode}")
print(f"selected_option={selected_option}")
print(f"daily_checklist_ready={daily_checklist_ready}")
print("paper_shadow_started=False")
print("approved_for_paper_shadow_start=False")
print("exchange_order_submission=False")
print("approved_for_micro_live_execution=False")
print("approved_for_real_live_trading=False")
print(f"decision={decision}")
