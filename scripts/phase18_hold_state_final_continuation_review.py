import json, os, subprocess, time
from pathlib import Path

OUT = Path("data/processed/phase18_hold_state_final_continuation_review.json")
RUNTIME_OUT = Path("runtime/phase18_hold_state_final_continuation_review_state.json")
REVIEW_DIR = Path("data/processed/phase18_hold_monitoring")

EVIDENCE_SNAPSHOT = Path("data/processed/phase18_hold_state_continuation_evidence_snapshot.json")
RUNTIME_EVIDENCE_SNAPSHOT = Path("runtime/phase18_hold_state_continuation_evidence_snapshot_state.json")
HEALTH_CHECK = Path("data/processed/phase18_hold_state_continuation_health_check.json")
CONTINUATION_PLAN = Path("data/processed/phase18_hold_state_continuation_plan.json")
CLOSEOUT = Path("data/processed/phase18_hold_state_closeout_report.json")
EVIDENCE_INDEX = Path("data/processed/phase18_hold_state_evidence_index.json")
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

snapshot = load_json(EVIDENCE_SNAPSHOT)
runtime_snapshot = load_json(RUNTIME_EVIDENCE_SNAPSHOT)
health = load_json(HEALTH_CHECK)
continuation = load_json(CONTINUATION_PLAN)
closeout = load_json(CLOSEOUT)
evidence_index = load_json(EVIDENCE_INDEX)
next_action = load_json(NEXT_ACTION)
phase17_closeout = load_json(PHASE17_CLOSEOUT)

records = [
    snapshot,
    runtime_snapshot,
    health,
    continuation,
    closeout,
    evidence_index,
    next_action,
    phase17_closeout,
]

selected_option = (
    snapshot.get("selected_option")
    or runtime_snapshot.get("selected_option")
    or health.get("selected_option")
    or continuation.get("selected_option")
    or closeout.get("selected_option")
    or evidence_index.get("selected_option")
    or next_action.get("selected_option")
)

continuation_evidence_snapshot_ready = (
    snapshot.get("continuation_evidence_snapshot_ready") is True
    or runtime_snapshot.get("continuation_evidence_snapshot_ready") is True
)

continuation_health_passed = health.get("continuation_health_passed") is True
continuation_plan_ready = continuation.get("continuation_plan_ready") is True
hold_state_closeout_passed = closeout.get("hold_state_closeout_passed") is True
evidence_index_ready = evidence_index.get("evidence_index_ready") is True
phase17_closed_safely = phase17_closeout.get("phase17_closed_safely") is True

paper_shadow_started = any_true(*[r.get("paper_shadow_started") for r in records])
approved_for_paper_shadow_start = any_true(*[r.get("approved_for_paper_shadow_start") for r in records])
exchange_order_submission = any_true(*[r.get("exchange_order_submission") for r in records])
real_capital_allowed = any_true(*[r.get("real_capital_allowed") for r in records])
live_trading_enabled = any_true(*[r.get("live_trading_enabled") for r in records])
approved_for_micro_live_execution = any_true(*[r.get("approved_for_micro_live_execution") for r in records])
approved_for_real_live_trading = any_true(*[r.get("approved_for_real_live_trading") for r in records])

final_review_checks = {
    "safe_mode_active": safe_mode,
    "evidence_snapshot_present": EVIDENCE_SNAPSHOT.exists(),
    "runtime_evidence_snapshot_present": RUNTIME_EVIDENCE_SNAPSHOT.exists(),
    "health_check_present": HEALTH_CHECK.exists(),
    "continuation_plan_present": CONTINUATION_PLAN.exists(),
    "closeout_present": CLOSEOUT.exists(),
    "evidence_index_present": EVIDENCE_INDEX.exists(),
    "next_action_present": NEXT_ACTION.exists(),
    "phase17_closeout_present": PHASE17_CLOSEOUT.exists(),
    "selected_option_is_remain_on_hold": selected_option == "remain_on_hold",
    "continuation_evidence_snapshot_ready": continuation_evidence_snapshot_ready,
    "continuation_health_passed": continuation_health_passed,
    "continuation_plan_ready": continuation_plan_ready,
    "hold_state_closeout_passed": hold_state_closeout_passed,
    "evidence_index_ready": evidence_index_ready,
    "phase17_closed_safely": phase17_closed_safely,
    "paper_shadow_not_started": paper_shadow_started is False,
    "paper_shadow_start_not_approved": approved_for_paper_shadow_start is False,
    "exchange_order_submission_disabled": exchange_order_submission is False,
    "real_capital_disabled": real_capital_allowed is False,
    "live_trading_disabled": live_trading_enabled is False,
    "micro_live_not_approved": approved_for_micro_live_execution is False,
    "real_live_not_approved": approved_for_real_live_trading is False,
}

blockers = [k for k, v in final_review_checks.items() if v is not True]
final_continuation_review_passed = all(final_review_checks.values())

REVIEW_DIR.mkdir(parents=True, exist_ok=True)

if final_continuation_review_passed:
    decision = "PHASE_18_HOLD_STATE_FINAL_CONTINUATION_REVIEW_COMPLETE_HOLD_CONFIRMED_NOT_APPROVED_FOR_EXECUTION"
    next_phase = "Phase 18.15 — Phase 18 Final Safety Closeout"
else:
    decision = "PHASE_18_HOLD_STATE_FINAL_CONTINUATION_REVIEW_BLOCKED_REVIEW_REQUIRED"
    next_phase = "Phase 18.15 — Final Continuation Review Fix"

review_record = {
    "phase": "phase_18_14_hold_state_final_continuation_review_record",
    "created_at_unix": int(time.time()),
    "selected_option": selected_option,
    "final_continuation_review_passed": final_continuation_review_passed,
    "final_review_checks": final_review_checks,
    "blockers": blockers,
    "final_status": {
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
    "allowed_actions": [
        "continue_hold_state_monitoring",
        "strategy_rework_only",
        "historical_data_expansion_only",
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

review_file = REVIEW_DIR / "hold_state_final_continuation_review.json"
write_json(review_file, review_record)
write_json(RUNTIME_OUT, review_record)

report = {
    "phase": "phase_18_14_hold_state_final_continuation_review",
    "generated_at_unix": int(time.time()),
    "scope": "hold_state_final_continuation_review_only",
    "selected_option": selected_option,
    "safety_flags": flags,
    "safe_mode_active": safe_mode,
    "git_working_tree_clean": git_clean_before_outputs,
    "final_continuation_review_passed": final_continuation_review_passed,
    "final_review_checks": final_review_checks,
    "blockers": blockers,
    "paper_shadow_started": False,
    "approved_for_paper_shadow_start": False,
    "exchange_order_submission": False,
    "real_capital_allowed": False,
    "live_trading_enabled": False,
    "approved_for_micro_live_execution": False,
    "approved_for_real_live_trading": False,
    "review_file": str(review_file),
    "runtime_review_file": str(RUNTIME_OUT),
    "decision": decision,
    "next_phase": next_phase,
    "safety_notes": [
        "This phase performs final hold-state continuation review only.",
        "This phase does not start paper shadow execution.",
        "This phase does not approve micro-live execution.",
        "This phase does not approve real live trading.",
        "This phase does not submit Binance orders.",
        "Real capital and exchange order submission remain disabled."
    ]
}

write_json(OUT, report)

print(f"Report written to: {OUT}")
print(f"Runtime review written to: {RUNTIME_OUT}")
print(f"Review written to: {review_file}")
print(f"safe_mode_active={safe_mode}")
print(f"selected_option={selected_option}")
print(f"final_continuation_review_passed={final_continuation_review_passed}")
print("paper_shadow_started=False")
print("approved_for_paper_shadow_start=False")
print("exchange_order_submission=False")
print("approved_for_micro_live_execution=False")
print("approved_for_real_live_trading=False")
print(f"decision={decision}")
