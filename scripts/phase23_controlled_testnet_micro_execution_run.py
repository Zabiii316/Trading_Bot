import hashlib
import hmac
import json
import os
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

OUT = Path(
    "data/processed/phase23_controlled_testnet_micro_execution_run.json"
)
RUNTIME_OUT = Path(
    "runtime/phase23_controlled_testnet_micro_execution_run_state.json"
)
RUN_FILE = Path(
    "data/processed/phase23_reopening/"
    "controlled_testnet_micro_execution_run.json"
)

GATE_FILES = [
    Path(
        "data/processed/"
        "phase23_testnet_micro_execution_approval_gate.json"
    ),
    Path(
        "runtime/"
        "phase23_testnet_micro_execution_approval_gate_state.json"
    ),
    Path(
        "data/processed/phase23_reopening/"
        "testnet_micro_execution_approval_gate.json"
    ),
]

ALLOWED_TESTNET_HOST = "testnet.binance.vision"

def run(cmd):
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
    )

def git_value(cmd):
    result = run(cmd)
    if result.returncode == 0:
        return result.stdout.strip()
    return None

def load(path):
    try:
        if path.exists():
            return json.loads(path.read_text())
    except Exception:
        pass
    return {}

def any_true(items, key):
    return any(
        item.get(key) is True
        for item in items
    )

def parse_positive(value):
    try:
        number = float(value)
        if number > 0:
            return number
    except Exception:
        pass
    return None

def first_symbol(value):
    if not value:
        return "BTCUSDT"

    symbol = value.split(",")[0].strip()
    return symbol or "BTCUSDT"

def valid_secret(value):
    if not value:
        return False

    upper = value.upper()

    if "PASTE_YOUR_" in upper:
        return False

    if "YOUR_" in upper:
        return False

    return len(value) >= 8

def request_json(
    url,
    method="GET",
    headers=None,
    timeout=15,
):
    started = time.time()

    try:
        request = urllib.request.Request(
            url=url,
            headers=headers or {},
            method=method,
        )

        with urllib.request.urlopen(
            request,
            timeout=timeout,
        ) as response:
            raw = response.read().decode(
                "utf-8",
                errors="replace",
            )

            try:
                body = json.loads(raw)
            except Exception:
                body = {
                    "raw_response": raw[:1000]
                }

            return {
                "ok": 200 <= response.status < 300,
                "status_code": response.status,
                "elapsed_ms": int(
                    (time.time() - started) * 1000
                ),
                "body": body,
                "error": None,
            }

    except urllib.error.HTTPError as exc:
        raw = exc.read().decode(
            "utf-8",
            errors="replace",
        )

        try:
            body = json.loads(raw)
        except Exception:
            body = {
                "raw_response": raw[:1000]
            }

        return {
            "ok": False,
            "status_code": exc.code,
            "elapsed_ms": int(
                (time.time() - started) * 1000
            ),
            "body": body,
            "error": str(exc),
        }

    except Exception as exc:
        return {
            "ok": False,
            "status_code": None,
            "elapsed_ms": int(
                (time.time() - started) * 1000
            ),
            "body": None,
            "error": str(exc),
        }

def write(path, data):
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    path.write_text(
        json.dumps(
            data,
            indent=2,
        )
    )

head = git_value([
    "git",
    "rev-parse",
    "HEAD",
])

branch = git_value([
    "git",
    "branch",
    "--show-current",
])

remote = git_value([
    "git",
    "remote",
    "get-url",
    "origin",
])

status_short = git_value([
    "git",
    "status",
    "--short",
]) or ""

git_clean = status_short == ""

gate_records = [
    load(path)
    for path in GATE_FILES
]

gate_passed = (
    any_true(
        gate_records,
        "testnet_micro_execution_approval_gate_passed",
    )
    or any(
        "PHASE_23_TESTNET_MICRO_EXECUTION_APPROVAL_GATE_COMPLETE"
        in str(item.get("decision", ""))
        for item in gate_records
    )
)

gate_manual_approval = any_true(
    gate_records,
    "manual_testnet_approval_present",
)

gate_execution_approved = any_true(
    gate_records,
    "testnet_micro_execution_approved",
)

manual_approval = (
    os.getenv(
        "PHASE23_TESTNET_EXECUTION_APPROVED",
        "",
    ).lower()
    in {
        "true",
        "1",
        "yes",
        "approved",
    }
)

flags = {
    "BINANCE_TESTNET":
        os.getenv(
            "BINANCE_TESTNET",
            "",
        ),
    "BINANCE_USE_TESTNET":
        os.getenv(
            "BINANCE_USE_TESTNET",
            "",
        ),
    "BINANCE_ENABLE_LIVE_TRADING":
        os.getenv(
            "BINANCE_ENABLE_LIVE_TRADING",
            "",
        ),
    "LIVE_TRADING_ALLOWED":
        os.getenv(
            "LIVE_TRADING_ALLOWED",
            "",
        ),
    "KILL_SWITCH_ENABLED":
        os.getenv(
            "KILL_SWITCH_ENABLED",
            "",
        ),
}

safe_flags_active = (
    flags["BINANCE_TESTNET"] == "true"
    and flags["BINANCE_USE_TESTNET"] == "true"
    and flags["BINANCE_ENABLE_LIVE_TRADING"] == "false"
    and flags["LIVE_TRADING_ALLOWED"] == "false"
)

kill_switch_enabled = (
    flags["KILL_SWITCH_ENABLED"].lower()
    in {
        "true",
        "1",
        "yes",
        "enabled",
    }
)

api_key = os.getenv(
    "BINANCE_TESTNET_API_KEY",
    "",
)

api_secret = os.getenv(
    "BINANCE_TESTNET_API_SECRET",
    "",
)

production_api_key = os.getenv(
    "BINANCE_API_KEY",
    "",
)

production_api_secret = os.getenv(
    "BINANCE_API_SECRET",
    "",
)

base_url = os.getenv(
    "BINANCE_TESTNET_BASE_URL",
    "https://testnet.binance.vision",
).rstrip("/")

parsed_url = urllib.parse.urlparse(
    base_url
)

hostname = (
    parsed_url.hostname
    or ""
).lower()

testnet_host_allowed = (
    hostname == ALLOWED_TESTNET_HOST
)

production_credentials_absent = (
    not production_api_key
    and not production_api_secret
)

testnet_credentials_present = (
    valid_secret(api_key)
    and valid_secret(api_secret)
)

symbol = first_symbol(
    os.getenv(
        "TRADING_SYMBOLS",
        "BTCUSDT",
    )
)

micro_notional = parse_positive(
    os.getenv(
        "MICRO_TRADE_NOTIONAL_USDT",
        "",
    )
)

max_order = parse_positive(
    os.getenv(
        "MAX_ORDER_NOTIONAL_USDT",
        "",
    )
)

max_position = parse_positive(
    os.getenv(
        "MAX_POSITION_SIZE_USDT",
        "",
    )
)

micro_within_order = (
    micro_notional is not None
    and max_order is not None
    and micro_notional <= max_order
)

order_within_position = (
    max_order is not None
    and max_position is not None
    and max_order <= max_position
)

preflight_checks = {
    "git_head_present":
        bool(head),

    "git_branch_present":
        bool(branch),

    "git_remote_origin_present":
        bool(remote),

    "git_working_tree_clean_before_outputs":
        git_clean,

    "phase23_19_gate_present":
        any(
            path.exists()
            for path in GATE_FILES
        ),

    "phase23_19_gate_passed":
        gate_passed,

    "phase23_19_manual_approval_present":
        gate_manual_approval,

    "phase23_19_testnet_execution_approved":
        gate_execution_approved,

    "current_manual_approval_present":
        manual_approval,

    "safe_flags_active":
        safe_flags_active,

    "kill_switch_enabled":
        kill_switch_enabled,

    "testnet_host_allowed":
        testnet_host_allowed,

    "testnet_credentials_present":
        testnet_credentials_present,

    "production_credentials_absent":
        production_credentials_absent,

    "micro_trade_notional_defined":
        micro_notional is not None,

    "max_order_notional_defined":
        max_order is not None,

    "max_position_size_defined":
        max_position is not None,

    "micro_notional_within_order_limit":
        micro_within_order,

    "order_limit_within_position_limit":
        order_within_position,
}

blockers = [
    key
    for key, value
    in preflight_checks.items()
    if value is not True
]

preflight_passed = not blockers

server_time_result = None
order_result = None

testnet_order_submission_attempted = False
testnet_order_submission_succeeded = False

signed_endpoint_called = False
order_endpoint_called = False
network_call_made = False

if preflight_passed:
    server_time_result = request_json(
        base_url + "/api/v3/time"
    )

    network_call_made = True

    if not server_time_result["ok"]:
        blockers.append(
            "testnet_server_time_request_failed"
        )

    else:
        body = (
            server_time_result.get("body")
            or {}
        )

        server_time = body.get(
            "serverTime"
        )

        if not isinstance(
            server_time,
            int,
        ):
            blockers.append(
                "invalid_testnet_server_time"
            )

        else:
            quote_value = (
                f"{micro_notional:.8f}"
                .rstrip("0")
                .rstrip(".")
            )

            params = {
                "symbol": symbol,
                "side": "BUY",
                "type": "MARKET",
                "quoteOrderQty": quote_value,
                "recvWindow": "5000",
                "timestamp": str(server_time),
                "newClientOrderId":
                    "PHASE23_20_"
                    + str(int(time.time())),
            }

            payload = urllib.parse.urlencode(
                params
            )

            signature = hmac.new(
                api_secret.encode("utf-8"),
                payload.encode("utf-8"),
                hashlib.sha256,
            ).hexdigest()

            order_url = (
                base_url
                + "/api/v3/order?"
                + payload
                + "&signature="
                + signature
            )

            headers = {
                "X-MBX-APIKEY":
                    api_key,
            }

            testnet_order_submission_attempted = True
            signed_endpoint_called = True
            order_endpoint_called = True
            network_call_made = True

            order_result = request_json(
                order_url,
                method="POST",
                headers=headers,
            )

            testnet_order_submission_succeeded = (
                order_result["ok"]
                and isinstance(
                    order_result.get("body"),
                    dict,
                )
                and (
                    order_result["body"].get(
                        "orderId"
                    )
                    is not None
                )
            )

if testnet_order_submission_succeeded:
    decision = (
        "PHASE_23_CONTROLLED_TESTNET_MICRO_EXECUTION_RUN_COMPLETE_"
        "READY_FOR_TESTNET_EXECUTION_REVIEW_"
        "NOT_APPROVED_FOR_LIVE_EXECUTION"
    )

elif preflight_passed:
    decision = (
        "PHASE_23_CONTROLLED_TESTNET_MICRO_EXECUTION_RUN_ATTEMPTED_"
        "TESTNET_ORDER_NOT_COMPLETED_REVIEW_REQUIRED_"
        "NOT_APPROVED_FOR_LIVE_EXECUTION"
    )

else:
    decision = (
        "PHASE_23_CONTROLLED_TESTNET_MICRO_EXECUTION_RUN_BLOCKED_"
        "PREFLIGHT_REQUIREMENTS_NOT_MET_"
        "NOT_APPROVED_FOR_EXECUTION"
    )

safe_order_response = None

if order_result is not None:
    body = order_result.get(
        "body"
    )

    if isinstance(body, dict):
        safe_order_response = {
            "orderId":
                body.get("orderId"),

            "clientOrderId":
                body.get("clientOrderId"),

            "transactTime":
                body.get("transactTime"),

            "symbol":
                body.get("symbol"),

            "status":
                body.get("status"),

            "executedQty":
                body.get("executedQty"),

            "cummulativeQuoteQty":
                body.get(
                    "cummulativeQuoteQty"
                ),

            "code":
                body.get("code"),

            "msg":
                body.get("msg"),
        }

record = {
    "phase":
        "phase_23_20_controlled_testnet_micro_execution_run",

    "generated_at_unix":
        int(time.time()),

    "git_head":
        head,

    "git_branch":
        branch,

    "git_remote_origin":
        remote,

    "git_working_tree_clean_before_outputs":
        git_clean,

    "current_transition_status":
        "controlled_testnet_micro_execution_run",

    "preflight_passed":
        preflight_passed,

    "preflight_checks":
        preflight_checks,

    "blockers":
        blockers,

    "safe_flags":
        flags,

    "safe_flags_active":
        safe_flags_active,

    "kill_switch_enabled":
        kill_switch_enabled,

    "testnet_environment": {
        "hostname":
            hostname,

        "testnet_host_allowed":
            testnet_host_allowed,

        "symbol":
            symbol,

        "planned_notional_usdt":
            micro_notional,

        "production_credentials_absent":
            production_credentials_absent,

        "testnet_credentials_present":
            testnet_credentials_present,
    },

    "testnet_micro_execution_approved":
        gate_execution_approved
        and manual_approval,

    "testnet_micro_execution_started":
        testnet_order_submission_attempted,

    "testnet_micro_execution_completed":
        testnet_order_submission_succeeded,

    "testnet_order_submission_attempted":
        testnet_order_submission_attempted,

    "testnet_order_submission_succeeded":
        testnet_order_submission_succeeded,

    "testnet_order_response":
        safe_order_response,

    "server_time_request_ok":
        (
            server_time_result["ok"]
            if server_time_result
            else False
        ),

    "signed_endpoint_called":
        signed_endpoint_called,

    "account_endpoint_called":
        False,

    "order_endpoint_called":
        order_endpoint_called,

    "network_call_made":
        network_call_made,

    "production_credentials_used":
        False,

    "testnet_exchange_order_submission":
        testnet_order_submission_attempted,

    "production_exchange_order_submission":
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

    "production_api_key_usage":
        False,

    "real_capital_usage":
        False,

    "decision":
        decision,

    "next_phase":
        "Phase 23.21 — Testnet Micro-Execution Review",
}

write(
    OUT,
    record,
)

write(
    RUNTIME_OUT,
    record,
)

write(
    RUN_FILE,
    record,
)

print(
    f"Report written to: {OUT}"
)

print(
    f"Runtime state written to: {RUNTIME_OUT}"
)

print(
    f"Run file written to: {RUN_FILE}"
)

print(
    f"preflight_passed={preflight_passed}"
)

print(
    "testnet_order_submission_attempted="
    + str(testnet_order_submission_attempted)
)

print(
    "testnet_order_submission_succeeded="
    + str(testnet_order_submission_succeeded)
)

print(
    "testnet_micro_execution_completed="
    + str(testnet_order_submission_succeeded)
)

print(
    f"signed_endpoint_called={signed_endpoint_called}"
)

print(
    f"order_endpoint_called={order_endpoint_called}"
)

print(
    "production_credentials_used=False"
)

print(
    "production_exchange_order_submission=False"
)

print(
    "approved_for_micro_live_execution=False"
)

print(
    "approved_for_real_live_trading=False"
)

print(
    "real_capital_usage=False"
)

print(
    f"decision={decision}"
)

if blockers:
    print(
        "blockers="
        + ",".join(blockers)
    )
