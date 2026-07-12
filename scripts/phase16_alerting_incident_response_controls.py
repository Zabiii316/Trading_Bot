from __future__ import annotations

import json
import os
import subprocess
import time
import urllib.parse
import urllib.request
from pathlib import Path


OUTPUT_PATH = Path("data/processed/phase16_alerting_incident_response_controls.json")
ALERT_RULES_PATH = Path("deploy/prometheus/trading_bot_alert_rules.yml")
CONTROLS_SPEC_PATH = Path("data/processed/phase16_micro_live_controls_spec.json")


PROMETHEUS_URL = "http://localhost:9090"


def git_clean() -> bool:
    result = subprocess.run(
        ["git", "status", "--short"],
        capture_output=True,
        text=True,
    )
    return result.stdout.strip() == ""


def query_prometheus(query: str) -> dict:
    params = urllib.parse.urlencode({"query": query})
    url = f"{PROMETHEUS_URL}/api/v1/query?{params}"
    try:
        with urllib.request.urlopen(url, timeout=10) as response:
            return json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        return {
            "status": "error",
            "error": str(exc),
            "data": {"result": []},
        }


def prometheus_has_data(query: str) -> bool:
    result = query_prometheus(query)
    return bool(result.get("data", {}).get("result"))


def main() -> None:
    safety_flags = {
        "BINANCE_TESTNET": os.getenv("BINANCE_TESTNET"),
        "BINANCE_USE_TESTNET": os.getenv("BINANCE_USE_TESTNET"),
        "BINANCE_ENABLE_LIVE_TRADING": os.getenv("BINANCE_ENABLE_LIVE_TRADING"),
        "LIVE_TRADING_ALLOWED": os.getenv("LIVE_TRADING_ALLOWED"),
    }

    safe_mode_active = (
        safety_flags.get("BINANCE_ENABLE_LIVE_TRADING") == "false"
        and safety_flags.get("LIVE_TRADING_ALLOWED") == "false"
    )

    required_alerts = [
        "TradingMonitoringAPIDown",
        "TradingComponentNotReady",
        "KillSwitchActive",
        "RiskRejectionDetected",
        "OrderSubmitted",
        "FillDetected",
        "WebSocketDecodeErrors",
        "WebSocketReconnectsHigh",
    ]

    alert_rules_text = ALERT_RULES_PATH.read_text() if ALERT_RULES_PATH.exists() else ""
    alert_rules_present = {
        alert_name: alert_name in alert_rules_text
        for alert_name in required_alerts
    }

    prometheus_queries = {
        "monitoring_api_up": 'up{job="trading-monitoring-api"}',
        "component_up": "trading_component_up",
        "component_ready": "trading_component_ready",
        "kill_switch_active": "trading_kill_switch_active",
        "risk_rejections": "trading_risk_rejections_total",
        "orders_total": "trading_orders_total",
        "fills_total": "trading_fills_total",
        "websocket_errors": "trading_websocket_decode_errors_total",
    }

    prometheus_results = {
        name: prometheus_has_data(query)
        for name, query in prometheus_queries.items()
    }

    incident_response_controls = {
        "severity_levels": {
            "critical": [
                "monitoring_api_down",
                "kill_switch_active",
                "unexpected_live_order",
                "daily_loss_limit_hit",
            ],
            "warning": [
                "component_not_ready",
                "risk_rejection_detected",
                "websocket_decode_errors",
                "websocket_reconnects_high",
            ],
            "info": [
                "order_submitted",
                "fill_detected",
                "testnet_reconciliation_completed",
            ],
        },
        "required_response_steps": {
            "critical": [
                "activate_or_confirm_kill_switch",
                "disable_live_trading_flags",
                "cancel_all_open_orders",
                "check_position_risk",
                "record_incident_report",
                "do_not_resume_without_manual_approval",
            ],
            "warning": [
                "review_grafana_dashboard",
                "inspect_prometheus_query",
                "check_service_logs",
                "confirm_no_unexpected_orders",
                "record_observation",
            ],
        },
        "emergency_commands": {
            "safe_mode": "source runtime/safe_trading_flags.env",
            "emergency_stop": "./scripts/phase16_emergency_stop.sh",
            "check_git": "git status",
            "check_prometheus_target": "curl -s http://localhost:9090/api/v1/targets | python -m json.tool",
        },
    }

    report = {
        "phase": "phase_16_12_alerting_incident_response_controls",
        "generated_at_unix": int(time.time()),
        "scope": "alerting_and_incident_response_controls_only",
        "not_approved_for": [
            "real_live_trading",
            "micro_live_execution",
            "production_binance_order_submission",
        ],
        "safety_flags": safety_flags,
        "safe_mode_active": safe_mode_active,
        "git_working_tree_clean": git_clean(),
        "alert_rules_file_exists": ALERT_RULES_PATH.exists(),
        "controls_spec_present": CONTROLS_SPEC_PATH.exists(),
        "required_alerts": alert_rules_present,
        "all_required_alerts_defined": all(alert_rules_present.values()),
        "prometheus_metric_checks": prometheus_results,
        "prometheus_core_metrics_available": all(prometheus_results.values()),
        "incident_response_controls": incident_response_controls,
        "approved_for_micro_live_execution": False,
        "decision": "ALERTING_AND_INCIDENT_RESPONSE_CONTROLS_READY_FOR_REVIEW_NOT_EXECUTION",
        "next_phase": "Phase 16.13 — 24h Testnet Soak Plan",
        "safety_notes": [
            "This phase defines alerting and incident response controls only.",
            "Live trading remains disabled.",
            "Micro-live execution requires a separate approval gate.",
            "Alerts must be reviewed in Grafana/Prometheus before any future real execution stage.",
        ],
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(report, indent=2))

    print(f"Report written to: {OUTPUT_PATH}")
    print(f"safe_mode_active={safe_mode_active}")
    print(f"all_required_alerts_defined={report['all_required_alerts_defined']}")
    print(f"prometheus_core_metrics_available={report['prometheus_core_metrics_available']}")
    print(f"decision={report['decision']}")


if __name__ == "__main__":
    main()
