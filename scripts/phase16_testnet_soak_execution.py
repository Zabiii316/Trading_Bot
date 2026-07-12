from __future__ import annotations

import argparse
import json
import os
import time
import urllib.parse
import urllib.request
from pathlib import Path

STATE_PATH = Path("runtime/phase16_soak_state.json")
REPORT_PATH = Path("data/processed/phase16_testnet_soak_execution_report.json")
PROMETHEUS_URL = "http://localhost:9090"


def flags() -> dict:
    return {
        "BINANCE_TESTNET": os.getenv("BINANCE_TESTNET"),
        "BINANCE_USE_TESTNET": os.getenv("BINANCE_USE_TESTNET"),
        "BINANCE_ENABLE_LIVE_TRADING": os.getenv("BINANCE_ENABLE_LIVE_TRADING"),
        "LIVE_TRADING_ALLOWED": os.getenv("LIVE_TRADING_ALLOWED"),
    }


def safe_mode_active() -> bool:
    f = flags()
    return (
        f.get("BINANCE_ENABLE_LIVE_TRADING") == "false"
        and f.get("LIVE_TRADING_ALLOWED") == "false"
    )


def prometheus_has(query: str) -> bool:
    try:
        url = PROMETHEUS_URL + "/api/v1/query?" + urllib.parse.urlencode({"query": query})
        with urllib.request.urlopen(url, timeout=10) as r:
            data = json.loads(r.read().decode("utf-8"))
        return bool(data.get("data", {}).get("result"))
    except Exception:
        return False


def snapshot() -> dict:
    checks = {
        "monitoring_api_up": prometheus_has('up{job="trading-monitoring-api"}'),
        "component_up": prometheus_has("trading_component_up"),
        "component_ready": prometheus_has("trading_component_ready"),
        "kill_switch_metric": prometheus_has("trading_kill_switch_active"),
        "risk_metric": prometheus_has("trading_risk_decisions_total"),
        "orders_metric": prometheus_has("trading_orders_total"),
        "fills_metric": prometheus_has("trading_fills_total"),
    }

    return {
        "captured_at_unix": int(time.time()),
        "safety_flags": flags(),
        "safe_mode_active": safe_mode_active(),
        "prometheus_checks": checks,
        "prometheus_core_metrics_available": all(checks.values()),
        "kill_switch_file_present": Path("runtime/KILL_SWITCH_ACTIVE").exists(),
    }


def start() -> None:
    state = {
        "phase": "phase_16_14_24h_testnet_soak_execution",
        "started_at_unix": int(time.time()),
        "started_at_readable": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
        "required_duration_hours": 24,
        "start_snapshot": snapshot(),
    }
    STATE_PATH.write_text(json.dumps(state, indent=2))
    print(f"Soak started. State written to: {STATE_PATH}")
    print("Required duration: 24 hours")
    print(f"safe_mode_active={state['start_snapshot']['safe_mode_active']}")
    print(f"prometheus_core_metrics_available={state['start_snapshot']['prometheus_core_metrics_available']}")


def status() -> None:
    if not STATE_PATH.exists():
        print("No soak state found. Run --start first.")
        return

    state = json.loads(STATE_PATH.read_text())
    elapsed_seconds = int(time.time()) - int(state["started_at_unix"])
    elapsed_hours = elapsed_seconds / 3600

    print(f"started_at={state.get('started_at_readable')}")
    print(f"elapsed_hours={round(elapsed_hours, 4)}")
    print(f"remaining_hours={round(max(0, 24 - elapsed_hours), 4)}")
    print(f"state_file={STATE_PATH}")


def finish() -> None:
    if not STATE_PATH.exists():
        raise SystemExit("Missing soak state. Run --start first.")

    state = json.loads(STATE_PATH.read_text())
    start_time = int(state["started_at_unix"])
    finish_time = int(time.time())
    elapsed_seconds = finish_time - start_time
    elapsed_hours = elapsed_seconds / 3600
    duration_passed = elapsed_seconds >= 24 * 3600
    finish_snapshot = snapshot()

    report = {
        "phase": "phase_16_14_24h_testnet_soak_execution_evidence",
        "generated_at_unix": finish_time,
        "started_at_unix": start_time,
        "finished_at_unix": finish_time,
        "elapsed_seconds": elapsed_seconds,
        "elapsed_hours": round(elapsed_hours, 4),
        "required_duration_hours": 24,
        "duration_passed": duration_passed,
        "start_snapshot": state.get("start_snapshot"),
        "finish_snapshot": finish_snapshot,
        "approved_for_micro_live_execution": False,
        "passed": (
            duration_passed
            and bool(state.get("start_snapshot", {}).get("safe_mode_active"))
            and finish_snapshot["safe_mode_active"]
            and bool(state.get("start_snapshot", {}).get("prometheus_core_metrics_available"))
            and finish_snapshot["prometheus_core_metrics_available"]
            and not finish_snapshot["kill_switch_file_present"]
        ),
        "decision": "SOAK_EXECUTION_COMPLETE_REVIEW_REQUIRED" if duration_passed else "SOAK_IN_PROGRESS_NOT_COMPLETE",
        "next_phase": "Phase 16.15 — Post-Soak Review and Micro-Live Approval Gap",
    }

    REPORT_PATH.write_text(json.dumps(report, indent=2))
    print(f"Report written to: {REPORT_PATH}")
    print(f"elapsed_hours={round(elapsed_hours, 4)}")
    print(f"duration_passed={duration_passed}")
    print(f"passed={report['passed']}")
    print(f"decision={report['decision']}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", action="store_true")
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--finish", action="store_true")
    args = parser.parse_args()

    if args.start:
        start()
    elif args.status:
        status()
    elif args.finish:
        finish()
    else:
        raise SystemExit("Use --start, --status, or --finish")


if __name__ == "__main__":
    main()
