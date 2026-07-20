import json, os, subprocess, time
from pathlib import Path

OUT = Path("data/processed/phase23_paper_shadow_start_gate.json")
RUNTIME_OUT = Path("runtime/phase23_paper_shadow_start_gate_state.json")
GATE_FILE = Path("data/processed/phase23_reopening/paper_shadow_start_gate.json")

PLAN_FILES = [
    Path("data/processed/phase23_paper_shadow_restart_plan.json"),
    Path("runtime/phase23_paper_shadow_restart_plan_state.json"),
    Path("data/processed/phase23_reopening/paper_shadow_restart_plan.json"),
]

FINAL_END_STATE = Path("data/processed/phase22_project_final_end_state_record.json")

def run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True)

def git_value(cmd):
    r = run(cmd)
    return r.stdout.strip() if r.returncode == 0 else None

def load(path):
    try:
        return json.loads(path.read_text()) if path.exists() else {}
    except Exception:
        return {}

def any_true(items, key):
    return any(item.get(key) is True for item in items)

def any_false(items, key):
    return any(item.get(key) is False for item in items)

def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2))

head = git_value(["git", "rev-parse", "HEAD"])
branch = git_value(["git", "branch", "--show-current"])
remote = git_value(["git", "remote", "get-url", "origin"])
status_short = git_value(["git", "status", "--short"]) or ""
git_clean = status_short == ""

plans = [load(p) for p in PLAN_FILES]
final_state = load(FINAL_END_STATE)

plan_created = (
    any_true(plans, "paper_shadow_restart_plan_created")
    or any("PHASE_23_PAPER_SHADOW_RESTART_PLAN_CREATED" in str(x.get("decision", "")) for x in plans)
)

phase22_closed = (
    final_state.get("project_final_end_state_record_created") is True
    or "PHASE_22_PROJECT_FINAL_END_STATE_RECORD_CREATED" in str(final_state.get("decision", ""))
)

flags = {
    "BINANCE_TESTNET": os.getenv("BINANCE_TESTNET", ""),
    "BINANCE_USE_TESTNET": os.getenv("BINANCE_USE_TESTNET", ""),
    "BINANCE_ENABLE_LIVE_TRADING": os.getenv("BINANCE_ENABLE_LIVE_TRADING", ""),
    "LIVE_TRADING_ALLOWED": os.getenv("LIVE_TRADING_ALLOWED", ""),
    "KILL_SWITCH_ENABLED": os.getenv("KILL_SWITCH_ENABLED", ""),
}

safe_flags_active = (
    flags["BINANCE_TESTNET"] == "true"
    and flags["BINANCE_USE_TESTNET"] == "true"
    and flags["BINANCE_ENABLE_LIVE_TRADING"] == "false"
    and flags["LIVE_TRADING_ALLOWED"] == "false"
)

kill_switch_enabled = flags["KILL_SWITCH_ENABLED"].lower() in {"true", "1", "yes", "enabled"}

checks = {
    "git_head_present": bool(head),
    "git_branch_present": bool(branch),
    "git_remote_origin_present": bool(remote),
    "git_working_tree_clean_before_outputs": git_clean,
    "phase22_final_end_state_present": FINAL_END_STATE.exists(),
    "phase22_closed_on_hold": phase22_closed,
    "phase23_13_plan_present": any(p.exists() for p in PLAN_FILES),
    "phase23_13_plan_created": plan_created,
    "safe_flags_active": safe_flags_active,
    "binance_testnet_true": flags["BINANCE_TESTNET"] == "true",
    "binance_use_testnet_true": flags["BINANCE_USE_TESTNET"] == "true",
    "live_trading_flag_false": flags["BINANCE_ENABLE_LIVE_TRADING"] == "false",
    "live_trading_allowed_false": flags["LIVE_TRADING_ALLOWED"] == "false",
    "kill_switch_enabled": kill_switch_enabled,
    "prior_paper_shadow_not_started": any_false(plans, "paper_shadow_started"),
    "prior_exchange_order_submission_false": any_false(plans, "exchange_order_submission"),
    "prior_execution_allowed_false": any_false(plans, "execution_allowed"),
    "prior_micro_live_approved_false": any_false(plans, "approved_for_micro_live_execution"),
    "prior_real_live_approved_false": any_false(plans, "approved_for_real_live_trading"),
    "gate_only_no_start": True,
}

blockers = [k for k, v in checks.items() if v is not True]
passed = not blockers

decision = (
    "PHASE_23_PAPER_SHADOW_START_GATE_CREATED_READY_FOR_MONITORING_VALIDATION_NOT_APPROVED_FOR_EXECUTION"
    if passed else
    "PHASE_23_PAPER_SHADOW_START_GATE_FAILED_REVIEW_REQUIRED_NOT_APPROVED_FOR_EXECUTION"
)

record = {
    "phase": "phase_23_14_paper_shadow_start_gate",
    "generated_at_unix": int(time.time()),
    "git_head": head,
    "git_branch": branch,
    "git_remote_origin": remote,
    "git_working_tree_clean_before_outputs": git_clean,
    "current_transition_status": "paper_shadow_start_gate_only_not_started_not_approved_for_execution",
    "paper_shadow_start_gate_created": passed,
    "paper_shadow_start_gate_passed": passed,
    "gate_checks": checks,
    "blockers": blockers,
    "safe_flags": flags,
    "safe_flags_active": safe_flags_active,
    "kill_switch_enabled": kill_switch_enabled,
    "paper_shadow_gate_scope": {
        "mode": "gate_only",
        "paper_shadow_engine_start": False,
        "monitoring_start": False,
        "exchange_submission": False,
        "signed_endpoint_call": False,
        "account_endpoint_call": False,
        "order_endpoint_call": False,
        "production_credentials_used": False,
        "real_capital_usage": False
    },
    "paper_shadow_started": False,
    "paper_shadow_start_approved": False,
    "approved_for_paper_shadow_start": False,
    "approved_for_paper_shadow": False,
    "monitoring_started": False,
    "run_dry_run_now": False,
    "run_backtest_now": False,
    "signed_endpoint_called": False,
    "account_endpoint_called": False,
    "order_endpoint_called": False,
    "network_call_made": False,
    "production_credentials_used": False,
    "execution_allowed": False,
    "approved_for_execution": False,
    "approved_for_live": False,
    "exchange_order_submission": False,
    "approved_for_micro_live_execution": False,
    "approved_for_real_live_trading": False,
    "production_api_key_usage": False,
    "real_capital_usage": False,
    "decision": decision,
    "next_phase": "Phase 23.15 — Paper Shadow Monitoring Validation"
}

write(OUT, record)
write(RUNTIME_OUT, record)
write(GATE_FILE, record)

print(f"Report written to: {OUT}")
print(f"Runtime state written to: {RUNTIME_OUT}")
print(f"Gate file written to: {GATE_FILE}")
print(f"paper_shadow_start_gate_passed={passed}")
print(f"safe_flags_active={safe_flags_active}")
print(f"kill_switch_enabled={kill_switch_enabled}")
print("paper_shadow_started=False")
print("paper_shadow_start_approved=False")
print("approved_for_paper_shadow_start=False")
print("monitoring_started=False")
print("execution_allowed=False")
print("exchange_order_submission=False")
print("approved_for_micro_live_execution=False")
print("approved_for_real_live_trading=False")
print("production_api_key_usage=False")
print("real_capital_usage=False")
print(f"decision={decision}")
if blockers:
    print("blockers=" + ",".join(blockers))
