import json, os, subprocess, time
from pathlib import Path

OUT = Path("data/processed/phase18_final_safety_closeout.json")
RUNTIME_OUT = Path("runtime/phase18_final_safety_closeout_state.json")
CLOSEOUT_DIR = Path("data/processed/phase18_hold_monitoring")

FINAL_REVIEW = Path("data/processed/phase18_hold_state_final_continuation_review.json")
RUNTIME_FINAL_REVIEW = Path("runtime/phase18_hold_state_final_continuation_review_state.json")
EVIDENCE_SNAPSHOT = Path("data/processed/phase18_hold_state_continuation_evidence_snapshot.json")
HEALTH_CHECK = Path("data/processed/phase18_hold_state_continuation_health_check.json")
CONTINUATION_PLAN = Path("data/processed/phase18_hold_state_continuation_plan.json")
HOLD_CLOSEOUT = Path("data/processed/phase18_hold_state_closeout_report.json")
EVIDENCE_INDEX = Path("data/processed/phase18_hold_state_evidence_index.json")
WEEKLY_SUMMARY = Path("data/processed/phase18_hold_state_weekly_review_summary.json")
NEXT_ACTION = Path("data/processed/phase18_next_action_selection.json")
PHASE17_CLOSEOUT = Path("data/processed/phase17_safety_closeout_next_action_options.json")

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
current_git_head = git_head()

final_review = load_json(FINAL_REVIEW)
runtime_final_review = load_json(RUNTIME_FINAL_REVIEW)
evidence_snapshot = load_json(EVIDENCE_SNAPSHOT)
health_check = load_json(HEALTH_CHECK)
continuation_plan = load_json(CONTINUATION_PLAN)
hold_closeout = load_json(HOLD_CLOSEOUT)
evidence_index = load_json(EVIDENCE_INDEX)
weekly_summary = load_json(WEEKLY_SUMMARY)
next_action = load_json(NEXT_ACTION)
phase17_closeout = load_json(PHASE17_CLOSEOUT)

records = [
    final_review,
    runtime_final_review,
    evidence_snapshot,
    health_check,
    continuation_plan,
    hold_closeout,
    evidence_index,
    weekly_summary,
    next_action,
    phase17_closeout,
]

selected_option = (
    final_review.get("selected_option")
    or runtime_final_review.get("selected_option")
    or evidence_snapshot.get("selected_option")
    or continuation_plan.get("selected_option")
    or hold_closeout.get("selected_option")
    or next_action.get("selected_option")
)

final_continuation_review_passed = (
    final_review.get("final_continuation_review_passed") is True
    or runtime_final_review.get("final_continuation_review_passed") is True
)

continuation_evidence_snapshot_ready = evidence_snapshot.get("continuation_evidence_snapshot_ready") is True
continuation_health_passed = health_check.get("continuation_health_passed") is True
continuation_plan_ready = continuation_plan.get("continuation_plan_ready") is True
hold_state_closeout_passed = hold_closeout.get("hold_state_closeout_passed") is True
evidence_index_ready = evidence_index.get("evidence_index_ready") is True
weekly_summary_passed = weekly_summary.get("weekly_summary_passed") is True
phase17_closed_safely = phase17_closeout.get("phase17_closed_safely") is True

paper_shadow_started = any_true(*[r.get("paper_shadow_started") for r in records])
approved_for_paper_shadow_start = any_true(*[r.get("approved_for_paper_shadow_start") for r in records])
exchange_order_submission = any_true(*[r.get("exchange_order_submission") for r in records])
real_capital_allowed = any_true(*[r.get("real_capital_allowed") for r in records])
live_trading_enabled = any_true(*[r.get("live_trading_enabled") for r in records])
approved_for_micro_live_execution = any_true(*[r.get("approved_for_micro_live_execution") for r in records])
approved_for_real_live_trading = any_true(*[r.get("approved_for_real_live_trading") for r in records])

phase18_processed_files = sorted(str(p) for p in Path("data/processed").glob("phase18_*.json"))
phase18_runtime_files = sorted(str(p) for p in Path("runtime").glob("phase18_*.json"))
phase18_hold_monitoring_files = sorted(str(p) for p in Path("data/processed/phase18_hold_monitoring").glob("*.json"))

final_closeout_checks = {
    "safe_mode_active": safe_mode,
    "final_review_present": FINAL_REVIEW.exists(),
    "runtime_final_review_present": RUNTIME_FINAL_REVIEW.exists(),
    "evidence_snapshot_present": EVIDENCE_SNAPSHOT.exists(),
    "health_check_present": HEALTH_CHECK.exists(),
    "continuation_plan_present": CONTINUATION_PLAN.exists(),
    "hold_closeout_present": HOLD_CLOSEOUT.exists(),
    "evidence_index_present": EVIDENCE_INDEX.exists(),
    "weekly_summary_present": WEEKLY_SUMMARY.exists(),
    "next_action_present": NEXT_ACTION.exists(),
    "phase17_closeout_present": PHASE17_CLOSEOUT.exists(),
    "selected_option_is_remain_on_hold": selected_option == "remain_on_hold",
    "final_continuation_review_passed": final_continuation_review_passed,
    "continuation_evidence_snapshot_ready": continuation_evidence_snapshot_ready,
    "continuation_health_passed": continuation_health_passed,
    "continuation_plan_ready": continuation_plan_ready,
    "hold_state_closeout_passed": hold_state_closeout_passed,
    "evidence_index_ready": evidence_index_ready,
    "weekly_summary_passed": weekly_summary_passed,
    "phase17_closed_safely": phase17_closed_safely,
    "paper_shadow_not_started": paper_shadow_started is False,
    "paper_shadow_start_not_approved": approved_for_paper_shadow_start is False,
    "exchange_order_submission_disabled": exchange_order_submission is False,
    "real_capital_disabled": real_capital_allowed is False,
    "live_trading_disabled": live_trading_enabled is False,
    "micro_live_not_approved": approved_for_micro_live_execution is False,
    "real_live_not_approved": approved_for_real_live_trading is False,
}

blockers = [k for k, v in final_closeout_checks.items() if v is not True]
phase18_closed_safely = all(final_closeout_checks.values())

CLOSEOUT_DIR.mkdir(parents=True, exist_ok=True)

if phase18_closed_safely:
    decision = "PHASE_18_FINAL_SAFETY_CLOSEOUT_COMPLETE_HOLD_CONFIRMED_NOT_APPROVED_FOR_EXECUTION"
    next_phase = "Phase 19 — Strategy Rework And Historical Data Expansion Decision"
else:
    decision = "PHASE_18_FINAL_SAFETY_CLOSEOUT_BLOCKED_REVIEW_REQUIRED"
    next_phase = "Phase 18.16 — Phase 18 Final Safety Closeout Review"

closeout_record = {
    "phase": "phase_18_15_final_safety_closeout_record",
    "created_at_unix": int(time.time()),
    "git_head": current_git_head,
    "selected_option": selected_option,
    "phase18_closed_safely": phase18_closed_safely,
    "final_closeout_checks": final_closeout_checks,
    "blockers": blockers,
    "evidence_counts": {
        "phase18_processed_file_count": len(phase18_processed_files),
        "phase18_runtime_file_count": len(phase18_runtime_files),
        "phase18_hold_monitoring_file_count": len(phase18_hold_monitoring_files)
    },
    "final_phase18_status": {
        "system_state": "HOLD",
        "paper_shadow_started": False,
        "approved_for_paper_shadow_start": False,
        "exchange_order_submission": False,
        "real_capital_allowed": False,
        "live_trading_enabled": False,
        "approved_for_micro_live_execution": False,
        "approved_for_real_live_trading": False
    },
    "approved_actions": [],
    "allowed_next_actions": [
        "strategy_rework_only",
        "historical_data_expansion_only",
        "continue_hold_state_monitoring",
        "documentation_cleanup_only",
        "dashboard_observation_only"
    ],
    "blocked_actions": [
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

closeout_file = CLOSEOUT_DIR / "phase18_final_safety_closeout.json"
write_json(closeout_file, closeout_record)
write_json(RUNTIME_OUT, closeout_record)

report = {
    "phase": "phase_18_15_final_safety_closeout",
    "generated_at_unix": int(time.time()),
    "scope": "phase18_final_safety_closeout_only",
    "git_head": current_git_head,
    "selected_option": selected_option,
    "safety_flags": flags,
    "safe_mode_active": safe_mode,
    "git_working_tree_clean": git_clean_before_outputs,
    "phase18_closed_safely": phase18_closed_safely,
    "final_closeout_checks": final_closeout_checks,
    "blockers": blockers,
    "phase18_processed_file_count": len(phase18_processed_files),
    "phase18_runtime_file_count": len(phase18_runtime_files),
    "phase18_hold_monitoring_file_count": len(phase18_hold_monitoring_files),
    "paper_shadow_started": False,
    "approved_for_paper_shadow_start": False,
    "exchange_order_submission": False,
    "real_capital_allowed": False,
    "live_trading_enabled": False,
    "approved_for_micro_live_execution": False,
    "approved_for_real_live_trading": False,
    "closeout_file": str(closeout_file),
    "runtime_closeout_file": str(RUNTIME_OUT),
    "decision": decision,
    "next_phase": next_phase,
    "safety_notes": [
        "Phase 18 is closed in HOLD state only.",
        "This phase does not start paper shadow execution.",
        "This phase does not approve micro-live execution.",
        "This phase does not approve real live trading.",
        "This phase does not submit Binance orders.",
        "Real capital and exchange order submission remain disabled."
    ]
}

write_json(OUT, report)

print(f"Report written to: {OUT}")
print(f"Runtime closeout written to: {RUNTIME_OUT}")
print(f"Closeout written to: {closeout_file}")
print(f"safe_mode_active={safe_mode}")
print(f"selected_option={selected_option}")
print(f"phase18_closed_safely={phase18_closed_safely}")
print("paper_shadow_started=False")
print("approved_for_paper_shadow_start=False")
print("exchange_order_submission=False")
print("approved_for_micro_live_execution=False")
print("approved_for_real_live_trading=False")
print(f"decision={decision}")
