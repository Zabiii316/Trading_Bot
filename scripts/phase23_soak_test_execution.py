import json
import os
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

OUT = Path("data/processed/phase23_soak_test_execution.json")
RUNTIME_OUT = Path("runtime/phase23_soak_test_execution_state.json")
PROGRESS_OUT = Path("runtime/phase23_soak_test_progress.json")
EXECUTION_FILE = Path(
    "data/processed/phase23_reopening/soak_test_execution.json"
)

PLAN_FILES = [
    Path("data/processed/phase23_soak_test_plan.json"),
    Path("runtime/phase23_soak_test_plan_state.json"),
    Path("data/processed/phase23_reopening/soak_test_plan.json"),
]

DEFAULT_TESTNET_URL = "https://testnet.binance.vision"
ALLOWED_HOST = "testnet.binance.vision"

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

def first_value(items, key, default=None):
    for item in items:
        value = item.get(key)
        if value not in (None, ""):
            return value
    return default

def positive_int(value, default):
    try:
        number = int(value)
        return number if number > 0 else default
    except Exception:
        return default

def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2))

def public_get(url, timeout=15):
    started = time.time()

    try:
        request = urllib.request.Request(
            url,
            method="GET",
            headers={
                "User-Agent": "phase23-soak-test",
                "Accept": "application/json",
            },
        )

        with urllib.request.urlopen(
            request,
            timeout=timeout,
        ) as response:
            raw = response.read().decode(
                "utf-8",
                errors="replace",
            )

            return {
                "ok": 200 <= response.status < 300,
                "status_code": response.status,
                "latency_ms": int(
                    (time.time() - started) * 1000
                ),
                "retry_after": response.headers.get("Retry-After"),
                "error": None,
                "body_preview": raw[:300],
            }

    except urllib.error.HTTPError as exc:
        retry_after = exc.headers.get("Retry-After")

        return {
            "ok": False,
            "status_code": exc.code,
            "latency_ms": int(
                (time.time() - started) * 1000
            ),
            "retry_after": retry_after,
            "error": str(exc),
            "body_preview": exc.read().decode(
                "utf-8",
                errors="replace",
            )[:300],
        }

    except Exception as exc:
        return {
            "ok": False,
            "status_code": None,
            "latency_ms": int(
                (time.time() - started) * 1000
            ),
            "retry_after": None,
            "error": str(exc),
            "body_preview": None,
        }

head = git_value(["git", "rev-parse", "HEAD"])
branch = git_value(["git", "branch", "--show-current"])
remote = git_value(["git", "remote", "get-url", "origin"])
status_short = git_value(["git", "status", "--short"]) or ""
git_clean = status_short == ""

plans = [load(path) for path in PLAN_FILES]

plan_created = (
    any_true(plans, "soak_test_plan_created")
    or any(
        "PHASE_23_SOAK_TEST_PLAN_CREATED"
        in str(item.get("decision", ""))
        for item in plans
    )
)

plan = first_value(plans, "soak_test_plan", {}) or {}

duration_minutes = positive_int(
    os.getenv(
        "SOAK_TEST_DURATION_MINUTES",
        str(plan.get("duration_minutes", 120)),
    ),
    120,
)

sample_interval_seconds = positive_int(
    os.getenv(
        "SOAK_TEST_SAMPLE_INTERVAL_SECONDS",
        str(plan.get("sample_interval_seconds", 60)),
    ),
    60,
)

max_consecutive_errors = positive_int(
    os.getenv(
        "SOAK_TEST_MAX_CONSECUTIVE_ERRORS",
        str(plan.get("max_consecutive_errors", 3)),
    ),
    3,
)

flags = {
    "BINANCE_TESTNET": os.getenv("BINANCE_TESTNET", ""),
    "BINANCE_USE_TESTNET": os.getenv("BINANCE_USE_TESTNET", ""),
    "BINANCE_ENABLE_LIVE_TRADING": os.getenv(
        "BINANCE_ENABLE_LIVE_TRADING", ""
    ),
    "LIVE_TRADING_ALLOWED": os.getenv("LIVE_TRADING_ALLOWED", ""),
    "KILL_SWITCH_ENABLED": os.getenv("KILL_SWITCH_ENABLED", ""),
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

base_url = os.getenv(
    "BINANCE_TESTNET_BASE_URL",
    DEFAULT_TESTNET_URL,
).rstrip("/")

hostname = (
    urllib.parse.urlparse(base_url).hostname
    or ""
).lower()

testnet_host_allowed = hostname == ALLOWED_HOST

preflight_checks = {
    "git_head_present": bool(head),
    "git_branch_present": bool(branch),
    "git_remote_origin_present": bool(remote),
    "git_working_tree_clean_before_outputs": git_clean,
    "phase23_22_plan_present": any(
        path.exists() for path in PLAN_FILES
    ),
    "phase23_22_plan_created": plan_created,
    "safe_flags_active": safe_flags_active,
    "kill_switch_enabled": kill_switch_enabled,
    "testnet_host_allowed": testnet_host_allowed,
    "production_credentials_absent": production_credentials_absent,
    "duration_positive": duration_minutes > 0,
    "sample_interval_positive": sample_interval_seconds > 0,
    "max_consecutive_errors_positive":
        max_consecutive_errors > 0,
}

blockers = [
    key
    for key, value in preflight_checks.items()
    if value is not True
]

preflight_passed = not blockers

samples = []
successful_samples = 0
failed_samples = 0
consecutive_errors = 0
maximum_consecutive_errors_seen = 0
latencies = []

abort_reason = None
soak_test_started = False
soak_test_completed = False

start_time = int(time.time())
planned_end_time = start_time + duration_minutes * 60

if preflight_passed:
    soak_test_started = True

    while time.time() < planned_end_time:
        current_safe = (
            os.getenv(
                "BINANCE_ENABLE_LIVE_TRADING",
                "",
            ) == "false"
            and os.getenv(
                "LIVE_TRADING_ALLOWED",
                "",
            ) == "false"
        )

        current_kill_switch = (
            os.getenv(
                "KILL_SWITCH_ENABLED",
                "",
            ).lower()
            in {"true", "1", "yes", "enabled"}
        )

        if not current_safe:
            abort_reason = "safe_trading_flags_changed"
            break

        if not current_kill_switch:
            abort_reason = "kill_switch_disabled"
            break

        ping = public_get(
            base_url + "/api/v3/ping"
        )

        server_time = public_get(
            base_url + "/api/v3/time"
        )

        sample_ok = (
            ping["ok"]
            and server_time["ok"]
        )

        sample_latency = max(
            ping["latency_ms"],
            server_time["latency_ms"],
        )

        if sample_ok:
            successful_samples += 1
            consecutive_errors = 0
            latencies.append(sample_latency)
        else:
            failed_samples += 1
            consecutive_errors += 1

        maximum_consecutive_errors_seen = max(
            maximum_consecutive_errors_seen,
            consecutive_errors,
        )

        sample = {
            "sample_number": len(samples) + 1,
            "timestamp_unix": int(time.time()),
            "sample_ok": sample_ok,
            "ping": ping,
            "server_time": server_time,
            "sample_latency_ms": sample_latency,
            "consecutive_errors": consecutive_errors,
            "safe_flags_active": current_safe,
            "kill_switch_enabled": current_kill_switch,
            "signed_endpoint_called": False,
            "account_endpoint_called": False,
            "order_endpoint_called": False,
            "exchange_order_submission": False,
        }

        samples.append(sample)

        progress = {
            "phase": "phase_23_23_soak_test_execution",
            "soak_test_started": True,
            "soak_test_completed": False,
            "samples_collected": len(samples),
            "successful_samples": successful_samples,
            "failed_samples": failed_samples,
            "consecutive_errors": consecutive_errors,
            "maximum_consecutive_errors_seen":
                maximum_consecutive_errors_seen,
            "latest_sample_ok": sample_ok,
            "latest_latency_ms": sample_latency,
            "abort_reason": abort_reason,
            "testnet_order_submission": False,
            "production_exchange_order_submission": False,
            "approved_for_micro_live_execution": False,
            "approved_for_real_live_trading": False,
        }

        write(PROGRESS_OUT, progress)

        print(
            f"sample={len(samples)} "
            f"ok={sample_ok} "
            f"latency_ms={sample_latency} "
            f"errors={consecutive_errors}"
        )

        if consecutive_errors >= max_consecutive_errors:
            abort_reason = (
                "maximum_consecutive_errors_reached"
            )
            break

        retry_after_values = [
            item.get("retry_after")
            for item in (ping, server_time)
            if item.get("status_code") == 429
            and item.get("retry_after")
        ]

        sleep_seconds = sample_interval_seconds

        if retry_after_values:
            try:
                sleep_seconds = max(
                    sleep_seconds,
                    max(
                        int(value)
                        for value in retry_after_values
                    ),
                )
            except Exception:
                pass

        remaining = planned_end_time - time.time()

        if remaining <= 0:
            break

        time.sleep(
            min(
                sleep_seconds,
                remaining,
            )
        )

    soak_test_completed = (
        abort_reason is None
        and time.time() >= planned_end_time
    )

total_samples = len(samples)

success_rate = (
    successful_samples / total_samples
    if total_samples
    else 0.0
)

average_latency_ms = (
    round(
        sum(latencies) / len(latencies),
        2,
    )
    if latencies
    else None
)

maximum_latency_ms = (
    max(latencies)
    if latencies
    else None
)

execution_passed = (
    preflight_passed
    and soak_test_completed
    and total_samples > 0
    and failed_samples == 0
    and abort_reason is None
)

if execution_passed:
    decision = (
        "PHASE_23_SOAK_TEST_EXECUTION_COMPLETE_"
        "READY_FOR_SOAK_TEST_REVIEW_"
        "NOT_APPROVED_FOR_LIVE_EXECUTION"
    )
elif preflight_passed:
    decision = (
        "PHASE_23_SOAK_TEST_EXECUTION_INCOMPLETE_"
        "REVIEW_REQUIRED_NOT_APPROVED_FOR_LIVE_EXECUTION"
    )
else:
    decision = (
        "PHASE_23_SOAK_TEST_EXECUTION_BLOCKED_"
        "PREFLIGHT_REQUIREMENTS_NOT_MET_"
        "NOT_APPROVED_FOR_LIVE_EXECUTION"
    )

record = {
    "phase": "phase_23_23_soak_test_execution",
    "generated_at_unix": int(time.time()),
    "git_head": head,
    "git_branch": branch,
    "git_remote_origin": remote,
    "git_working_tree_clean_before_outputs": git_clean,
    "current_transition_status":
        "testnet_soak_test_execution_only_not_approved_for_live_execution",
    "preflight_passed": preflight_passed,
    "preflight_checks": preflight_checks,
    "blockers": blockers,
    "safe_flags": flags,
    "safe_flags_active": safe_flags_active,
    "kill_switch_enabled": kill_switch_enabled,
    "testnet_hostname": hostname,
    "soak_test_started": soak_test_started,
    "soak_test_completed": soak_test_completed,
    "soak_test_execution_passed": execution_passed,
    "duration_minutes": duration_minutes,
    "sample_interval_seconds": sample_interval_seconds,
    "max_consecutive_errors":
        max_consecutive_errors,
    "samples_collected": total_samples,
    "successful_samples": successful_samples,
    "failed_samples": failed_samples,
    "success_rate": success_rate,
    "average_latency_ms": average_latency_ms,
    "maximum_latency_ms": maximum_latency_ms,
    "maximum_consecutive_errors_seen":
        maximum_consecutive_errors_seen,
    "abort_reason": abort_reason,
    "samples": samples,
    "public_endpoints_only": True,
    "signed_endpoint_called": False,
    "account_endpoint_called": False,
    "order_endpoint_called": False,
    "testnet_order_submission": False,
    "production_exchange_order_submission": False,
    "production_credentials_used": False,
    "execution_allowed": False,
    "approved_for_execution": False,
    "approved_for_micro_live_execution": False,
    "approved_for_real_live_trading": False,
    "approved_for_live": False,
    "exchange_order_submission": False,
    "production_api_key_usage": False,
    "real_capital_usage": False,
    "decision": decision,
    "next_phase": "Phase 23.24 — Soak Test Review",
}

write(OUT, record)
write(RUNTIME_OUT, record)
write(EXECUTION_FILE, record)

print(f"Report written to: {OUT}")
print(f"Runtime state written to: {RUNTIME_OUT}")
print(f"Execution file written to: {EXECUTION_FILE}")
print(f"preflight_passed={preflight_passed}")
print(f"soak_test_started={soak_test_started}")
print(f"soak_test_completed={soak_test_completed}")
print(f"soak_test_execution_passed={execution_passed}")
print(f"samples_collected={total_samples}")
print(f"successful_samples={successful_samples}")
print(f"failed_samples={failed_samples}")
print(f"average_latency_ms={average_latency_ms}")
print(f"maximum_consecutive_errors_seen={maximum_consecutive_errors_seen}")
print(f"abort_reason={abort_reason}")
print("signed_endpoint_called=False")
print("account_endpoint_called=False")
print("order_endpoint_called=False")
print("testnet_order_submission=False")
print("production_exchange_order_submission=False")
print("approved_for_micro_live_execution=False")
print("approved_for_real_live_trading=False")
print("real_capital_usage=False")
print(f"decision={decision}")

if blockers:
    print("blockers=" + ",".join(blockers))
