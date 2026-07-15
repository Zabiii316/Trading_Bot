import json, os, subprocess, time
from pathlib import Path

OUT = Path("data/processed/phase18_hold_state_monitoring_report.json")
RUNTIME_OUT = Path("runtime/phase18_hold_state_monitoring_report_state.json")
REPORT_DIR = Path("data/processed/phase18_hold_monitoring")

PLAN_INPUT = Path("data/processed/phase18_hold_state_monitoring_plan.json")
HEALTH_INPUT = Path("data/processed/phase18_hold_state_monitoring_health_check.json")
RUNTIME_HEALTH = Path("runtime/phase18_hold_state_monitoring_health_check_state.json")
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

plan = load_json(PLAN_INPUT)
health = load_json(HEALTH_INPUT)
runtime_health = load_json(RUNTIME_HEALTH)
next_action = load_json(NEXT_ACTION)
phase17_closeout = load_json(PHASE17_CLOSEOUT)

selected_option = (
    plan.get("selected_option")
    or health.get("selected_option")
    or next_action.get("selected_option")
)

monitoring_plan_ready = plan.get("monitoring_plan_ready") is True
core_hold_health_passed = (
    health.get("core_hold_health_passed") is True
    or runtime_health.get("core_hold_health_passed") is True
)

monitoring_endpoint_available = (
    health.get("monitoring_endpoint_available") is True
    or runtime_health.get("monitoring_endpoint_available") is True
)

paper_shadow_started = any_true(
    plan.get("paper_shadow_started"),
    health.get("paper_shadow_started"),
    runtime_health.get("paper_shadow_started"),
    next_action.get("paper_shadow_started"),
    phase17_closeout.get("paper_shadow_started")
)

approved_for_paper_shadow_start = any_true(
    plan.get("approved_for_paper_shadow_start"),
    health.get("approved_for_paper_shadow_start"),
    runtime_health.get("approved_for_paper_shadow_start"),
    next_action.get("approved_for_paper_shadow_start"),
    phase17_closeout.get("approved_for_paper_shadow_start")
)

exchange_order_submission = any_true(
    plan.get("exchange_order_submission"),
    health.get("exchange_order_submission"),
    runtime_health.get("exchange_order_submission"),
    next_action.get("exchange_order_submission"),
    phase17_closeout.get("exchange_order_submission")
)

approved_for_micro_live_execution = any_true(
    plan.get("approved_for_micro_live_execution"),
    health.get("approved_for_micro_live_execution"),
    runtime_health.get("approved_for_micro_live_execution"),
    next_action.get("approved_for_micro_live_execution"),
    phase17_closeout.get("approved_for_micro_live_execution")
)

approved_for_real_live_trading = any_true(
    plan.get("approved_for_real_live_trading"),
    health.get("approved_for_real_live_trading"),
    runtime_health.get("approved_for_real_live_trading"),
    next_action.get("approved_for_real_live_trading"),
    phase17_closeout.get("approved_for_real_live_trading")
)

report_checks = {
    "safe_mode_active": safe_mode,
    "plan_input_present": PLAN_INPUT.exists(),
    "health_input_present": HEALTH_INPUT.exists(),
    "runtime_health_present": RUNTIME_HEALTH.exists(),
    "next_action_present": NEXT_ACTION.exists(),
    "phase17_closeout_present": PHASE17_CLOSEOUT.exists(),
    "selected_option_is_remain_on_hold": selected_option == "remain_on_hold",
    "monitoring_plan_ready": monitoring_plan_ready,
    "core_hold_health_passed": core_hold_health_passed,
    "paper_shadow_not_started": paper_shadow_started is False,
    "paper_shadow_start_not_approved": approved_for_paper_shadow_start is False,
    "exchange_order_submission_disabled": exchange_order_submission is False,
    "micro_live_not_approved": approved_for_micro_live_execution is False,
    "real_live_not_approved": approved_for_real_live_trading is False,
}

blockers = [k for k, v in report_checks.items() if v is not True]
hold_state_report_passed = all(report_checks.values())

if hold_state_report_passed:
    decision = "PHASE_18_HOLD_STATE_MONITORING_REPORT_COMPLETE_HOLD_CONFIRMED_NOT_APPROVED_FOR_EXECUTION"
    next_phase = "Phase 18.5 — Hold State Daily Checklist"
else:
    decision = "PHASE_18_HOLD_STATE_MONITORING_REPORT_FAILED_REVIEW_REQUIRED"
    next_phase = "Phase 18.5 — Hold State Monitoring Review"

REPORT_DIR.mkdir(parents=True, exist_ok=True)

monitoring_report = {
    "phase": "phase_18_4_hold_state_monitoring_report_record",
    "created_at_unix": int(time.time()),
    "selected_option": selected_option,
    "monitoring_plan_ready": monitoring_plan_ready,
    "core_hold_health_passed": core_hold_health_passed,
    "monitoring_endpoint_available": monitoring_endpoint_available,
    "hold_state_report_passed": hold_state_report_passed,
    "report_checks": report_checks,
    "blockers": blockers,
    "status_summary": {
        "paper_shadow_started": False,
        "approved_for_paper_shadow_start": False,
        "exchange_order_submission": False,
        "real_capital_allowed": False,
        "live_trading_enabled": False,
        "approved_for_micro_live_execution": False,
        "approved_for_real_live_trading": False
    },
    "recommended_next_steps": [
        "keep_safe_trading_flags_enabled",
        "keep_live_trading_flags_disabled",
        "review_hold_state_daily",
        "review_monitoring_dashboard_weekly",
        "do_not_start_paper_shadow_without_separate_manual_approval",
        "do_not_enable_exchange_order_submission",
        "do_not_use_real_capital"
    ],
    "decision": decision,
    "next_phase": next_phase
}

report_file = REPORT_DIR / "hold_state_monitoring_report.json"
write_json(report_file, monitoring_report)
write_json(RUNTIME_OUT, monitoring_report)

report = {
    "phase": "phase_18_4_hold_state_monitoring_report",
    "generated_at_unix": int(time.time()),
    "scope": "hold_state_monitoring_report_only",
    "selected_option": selected_option,
    "safety_flags": flags,
    "safe_mode_active": safe_mode,
    "git_working_tree_clean": git_clean_before_outputs,
    "monitoring_plan_ready": monitoring_plan_ready,
    "core_hold_health_passed": core_hold_health_passed,
    "monitoring_endpoint_available": monitoring_endpoint_available,
    "hold_state_report_passed": hold_state_report_passed,
    "report_checks": report_checks,
    "blockers": blockers,
    "paper_shadow_started": False,
    "approved_for_paper_shadow_start": False,
    "exchange_order_submission": False,
    "real_capital_allowed": False,
    "live_trading_enabled": False,
    "approved_for_micro_live_execution": False,
    "approved_for_real_live_trading": False,
    "monitoring_report_file": str(report_file),
    "runtime_report_file": str(RUNTIME_OUT),
    "decision": decision,
    "next_phase": next_phase,
    "safety_notes": [
        "This phase creates a hold-state monitoring report only.",
        "This phase does not start paper shadow execution.",
        "This phase does not approve micro-live execution.",
        "This phase does not approve real live trading.",
        "This phase does not submit Binance orders.",
        "Real capital and exchange order submission remain disabled."
    ]
}

write_json(OUT, report)

print(f"Report written to: {OUT}")
print(f"Runtime report written to: {RUNTIME_OUT}")
print(f"Monitoring report written to: {report_file}")
print(f"safe_mode_active={safe_mode}")
print(f"selected_option={selected_option}")
print(f"monitoring_plan_ready={monitoring_plan_ready}")
print(f"core_hold_health_passed={core_hold_health_passed}")
print(f"hold_state_report_passed={hold_state_report_passed}")
print("paper_shadow_started=False")
print("approved_for_paper_shadow_start=False")
print("exchange_order_submission=False")
print("approved_for_micro_live_execution=False")
print("approved_for_real_live_trading=False")
print(f"decision={decision}")
