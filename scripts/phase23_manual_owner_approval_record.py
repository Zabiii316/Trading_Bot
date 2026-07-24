import json
import os
import subprocess
import time
from pathlib import Path

OUT = Path("data/processed/phase23_manual_owner_approval_record.json")
RUNTIME_OUT = Path("runtime/phase23_manual_owner_approval_record_state.json")
RECORD_FILE = Path(
    "data/processed/phase23_reopening/manual_owner_approval_record.json"
)

CAPITAL_FILES = [
    Path("data/processed/phase23_capital_limit_approval_record.json"),
    Path("runtime/phase23_capital_limit_approval_record_state.json"),
    Path(
        "data/processed/phase23_reopening/"
        "capital_limit_approval_record.json"
    ),
]

VALID_DECISIONS = {"pending", "approved", "declined"}

def run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True)

def git_value(cmd):
    result = run(cmd)
    return result.stdout.strip() if result.returncode == 0 else None

def load(path):
    try:
        return json.loads(path.read_text()) if path.exists() else {}
    except Exception:
        return {}

def any_true(items, key):
    return any(item.get(key) is True for item in items)

def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2))

head = git_value(["git", "rev-parse", "HEAD"])
branch = git_value(["git", "branch", "--show-current"])
remote = git_value(["git", "remote", "get-url", "origin"])
status_short = git_value(["git", "status", "--short"]) or ""
git_clean = status_short == ""

capital_records = [load(path) for path in CAPITAL_FILES]

capital_record_created = (
    any_true(
        capital_records,
        "capital_limit_approval_record_created",
    )
    or any(
        "PHASE_23_CAPITAL_LIMIT_APPROVAL_RECORD_CREATED"
        in str(item.get("decision", ""))
        for item in capital_records
    )
)

capital_limits_valid = any_true(
    capital_records,
    "capital_limits_technically_valid",
)

flags = {
    "BINANCE_TESTNET": os.getenv("BINANCE_TESTNET", ""),
    "BINANCE_USE_TESTNET": os.getenv("BINANCE_USE_TESTNET", ""),
    "BINANCE_ENABLE_LIVE_TRADING":
        os.getenv("BINANCE_ENABLE_LIVE_TRADING", ""),
    "LIVE_TRADING_ALLOWED":
        os.getenv("LIVE_TRADING_ALLOWED", ""),
    "KILL_SWITCH_ENABLED":
        os.getenv("KILL_SWITCH_ENABLED", ""),
}

safe_flags_active = (
    flags["BINANCE_TESTNET"] == "true"
    and flags["BINANCE_USE_TESTNET"] == "true"
    and flags["BINANCE_ENABLE_LIVE_TRADING"] == "false"
    and flags["LIVE_TRADING_ALLOWED"] == "false"
)

kill_switch_enabled = (
    flags["KILL_SWITCH_ENABLED"].lower()
    in {"true", "1", "yes", "enabled"}
)

production_credentials_absent = (
    not os.getenv("BINANCE_API_KEY")
    and not os.getenv("BINANCE_API_SECRET")
)

owner_decision = os.getenv(
    "PHASE23_OWNER_APPROVAL_DECISION",
    "pending",
).strip().lower()

owner_acknowledged = (
    os.getenv(
        "PHASE23_OWNER_APPROVAL_ACKNOWLEDGED",
        "",
    ).strip().lower()
    in {"true", "1", "yes", "acknowledged"}
)

decision_value_valid = owner_decision in VALID_DECISIONS

manual_owner_live_approval_present = (
    owner_decision == "approved"
    and owner_acknowledged
)

owner_declined = (
    owner_decision == "declined"
    and owner_acknowledged
)

checks = {
    "git_head_present": bool(head),
    "git_branch_present": bool(branch),
    "git_remote_origin_present": bool(remote),
    "git_working_tree_clean_before_outputs": git_clean,

    "phase23_27_capital_record_present":
        any(path.exists() for path in CAPITAL_FILES),

    "phase23_27_capital_record_created":
        capital_record_created,

    "capital_limits_technically_valid":
        capital_limits_valid,

    "safe_flags_active":
        safe_flags_active,

    "kill_switch_enabled":
        kill_switch_enabled,

    "production_credentials_absent":
        production_credentials_absent,

    "owner_decision_value_valid":
        decision_value_valid,

    "production_execution_disabled":
        flags["BINANCE_ENABLE_LIVE_TRADING"] == "false",

    "live_trading_not_allowed":
        flags["LIVE_TRADING_ALLOWED"] == "false",
}

blockers = [
    key
    for key, value in checks.items()
    if value is not True
]

record_created = not blockers

if not record_created:
    decision = (
        "PHASE_23_MANUAL_OWNER_APPROVAL_RECORD_FAILED_"
        "REVIEW_REQUIRED_NOT_APPROVED_FOR_LIVE_EXECUTION"
    )
    next_phase = "Phase 23.28 — Manual Owner Approval Record"

elif manual_owner_live_approval_present:
    decision = (
        "PHASE_23_MANUAL_OWNER_APPROVAL_RECORD_CREATED_"
        "OWNER_APPROVAL_PRESENT_READY_FOR_FINAL_GO_NO_GO_"
        "NOT_APPROVED_FOR_LIVE_EXECUTION"
    )
    next_phase = "Phase 23.29 — Final Go / No-Go Review"

elif owner_declined:
    decision = (
        "PHASE_23_MANUAL_OWNER_APPROVAL_RECORD_CREATED_"
        "OWNER_DECLINED_REMAIN_NOT_APPROVED_FOR_LIVE_EXECUTION"
    )
    next_phase = "Phase 23.28 — Manual Owner Approval Record"

else:
    decision = (
        "PHASE_23_MANUAL_OWNER_APPROVAL_RECORD_CREATED_"
        "OWNER_DECISION_PENDING_NOT_APPROVED_FOR_LIVE_EXECUTION"
    )
    next_phase = "Phase 23.28 — Manual Owner Approval Record"

record = {
    "phase": "phase_23_28_manual_owner_approval_record",
    "generated_at_unix": int(time.time()),

    "git_head": head,
    "git_branch": branch,
    "git_remote_origin": remote,

    "git_working_tree_clean_before_outputs":
        git_clean,

    "current_transition_status":
        "manual_owner_approval_record_only_not_approved_for_live_execution",

    "manual_owner_approval_record_created":
        record_created,

    "approval_checks":
        checks,

    "blockers":
        blockers,

    "owner_decision":
        owner_decision,

    "owner_acknowledged":
        owner_acknowledged,

    "manual_owner_live_approval_present":
        manual_owner_live_approval_present,

    "owner_declined_live_approval":
        owner_declined,

    "safe_flags":
        flags,

    "safe_flags_active":
        safe_flags_active,

    "kill_switch_enabled":
        kill_switch_enabled,

    "capital_limits_owner_approved_for_final_review":
        manual_owner_live_approval_present,

    "capital_limits_approved_for_live_use":
        False,

    "final_go_no_go_completed":
        False,

    "production_credentials_present":
        False,

    "production_credentials_used":
        False,

    "production_execution_started":
        False,

    "micro_live_deployment_started":
        False,

    "execution_allowed":
        False,

    "approved_for_execution":
        False,

    "approved_for_micro_live_execution":
        False,

    "approved_for_real_live_trading":
        False,

    "approved_for_live":
        False,

    "exchange_order_submission":
        False,

    "production_exchange_order_submission":
        False,

    "production_api_key_usage":
        False,

    "real_capital_usage":
        False,

    "decision":
        decision,

    "next_phase":
        next_phase,
}

write(OUT, record)
write(RUNTIME_OUT, record)
write(RECORD_FILE, record)

print(f"Report written to: {OUT}")
print(f"Runtime state written to: {RUNTIME_OUT}")
print(f"Record file written to: {RECORD_FILE}")

print(
    "manual_owner_approval_record_created="
    + str(record_created)
)

print(f"owner_decision={owner_decision}")
print(f"owner_acknowledged={owner_acknowledged}")

print(
    "manual_owner_live_approval_present="
    + str(manual_owner_live_approval_present)
)

print(
    "capital_limits_approved_for_live_use=False"
)

print("final_go_no_go_completed=False")
print("production_execution_started=False")
print("execution_allowed=False")
print("approved_for_micro_live_execution=False")
print("approved_for_real_live_trading=False")
print("production_exchange_order_submission=False")
print("real_capital_usage=False")
print(f"decision={decision}")
print(f"next_phase={next_phase}")

if blockers:
    print("blockers=" + ",".join(blockers))
