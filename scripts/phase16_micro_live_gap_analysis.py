from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path


OUTPUT_PATH = Path("data/processed/phase16_micro_live_gap_analysis.json")

REPORTS = {
    "validation": Path("data/processed/phase16_validation_report.json"),
    "testnet_shadow": Path("data/processed/phase16_testnet_shadow_report.json"),
    "testnet_execution": Path("data/processed/phase16_testnet_execution_report.json"),
    "testnet_reconciliation": Path("data/processed/phase16_testnet_reconciliation_report.json"),
    "testnet_cleanup": Path("data/processed/phase16_testnet_cleanup_report.json"),
    "go_no_go": Path("data/processed/phase16_go_no_go_summary.json"),
    "manual_approval": Path("data/processed/phase16_manual_approval_checklist.json"),
}


def git_clean() -> bool:
    result = subprocess.run(
        ["git", "status", "--short"],
        capture_output=True,
        text=True,
    )
    return result.stdout.strip() == ""


def load_report(path: Path) -> dict:
    if not path.exists():
        return {"exists": False, "passed": False, "data": {}}

    try:
        data = json.loads(path.read_text())
    except Exception as exc:
        return {
            "exists": True,
            "passed": False,
            "error": str(exc),
            "data": {},
        }

    return {
        "exists": True,
        "passed": bool(data.get("passed") or data.get("go_decision") or data.get("approved_for_controlled_testnet_review")),
        "phase": data.get("phase"),
        "data": data,
    }


def main() -> None:
    loaded_reports = {
        name: load_report(path)
        for name, path in REPORTS.items()
    }

    all_phase16_reports_exist = all(item["exists"] for item in loaded_reports.values())
    all_phase16_reports_passed = all(item["passed"] for item in loaded_reports.values())

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

    completed_readiness_items = {
        "phase16_validation_passed": loaded_reports["validation"]["passed"],
        "testnet_shadow_passed": loaded_reports["testnet_shadow"]["passed"],
        "testnet_order_submitted_and_acknowledged": loaded_reports["testnet_execution"]["passed"],
        "testnet_order_reconciled": loaded_reports["testnet_reconciliation"]["passed"],
        "testnet_cleanup_passed": loaded_reports["testnet_cleanup"]["passed"],
        "go_no_go_summary_passed": loaded_reports["go_no_go"]["passed"],
        "manual_testnet_review_approval_recorded": loaded_reports["manual_approval"]["passed"],
        "safe_mode_active": safe_mode_active,
        "git_working_tree_clean": git_clean(),
    }

    required_before_micro_live = {
        "real_exchange_key_management_documented": False,
        "real_binance_api_key_ip_whitelisted": False,
        "withdrawal_permissions_disabled_confirmed": False,
        "micro_live_capital_allocation_defined": False,
        "maximum_single_order_notional_defined": False,
        "daily_loss_limit_defined": False,
        "weekly_loss_limit_defined": False,
        "maximum_drawdown_stop_defined": False,
        "position_flattening_procedure_tested": False,
        "cancel_all_orders_procedure_tested": False,
        "kill_switch_tested_again_after_testnet_execution": False,
        "monitoring_alerts_tested": False,
        "grafana_dashboard_review_completed": False,
        "incident_response_owner_assigned": False,
        "manual_micro_live_approval_recorded": False,
        "minimum_24h_testnet_soak_completed": False,
        "exchange_permissions_audited": False,
        "production_environment_secrets_manager_ready": False,
        "independent_code_review_completed": False,
    }

    missing_items = [
        key for key, value in required_before_micro_live.items()
        if not value
    ]

    micro_live_ready = (
        all(completed_readiness_items.values())
        and all(required_before_micro_live.values())
    )

    report = {
        "phase": "phase_16_10_micro_live_readiness_gap_analysis",
        "generated_at_unix": int(time.time()),
        "scope": "planning_and_gap_analysis_only",
        "not_approved_for": [
            "real_live_trading",
            "micro_live_execution",
            "production_binance_order_submission",
        ],
        "safety_flags": safety_flags,
        "safe_mode_active": safe_mode_active,
        "all_phase16_reports_exist": all_phase16_reports_exist,
        "all_phase16_reports_passed": all_phase16_reports_passed,
        "completed_readiness_items": completed_readiness_items,
        "required_before_micro_live": required_before_micro_live,
        "missing_items_count": len(missing_items),
        "missing_items": missing_items,
        "micro_live_ready": micro_live_ready,
        "decision": "NO_GO_FOR_MICRO_LIVE_EXECUTION" if not micro_live_ready else "READY_FOR_SEPARATE_MICRO_LIVE_APPROVAL_GATE",
        "recommended_next_phase": "Phase 16.11 — Micro-Live Controls Specification",
        "safety_notes": [
            "This report does not authorize real live trading.",
            "The system has completed controlled testnet validation only.",
            "Micro-live requires a separate approval gate.",
            "Production API keys must not be committed.",
            "Withdrawal permissions must remain disabled.",
            "Emergency stop and cancel-all procedures must be validated before any real exchange execution.",
        ],
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(report, indent=2))

    print(f"Report written to: {OUTPUT_PATH}")
    print(f"micro_live_ready={micro_live_ready}")
    print(f"decision={report['decision']}")
    print(f"missing_items_count={len(missing_items)}")

    if missing_items:
        print("")
        print("Missing before micro-live:")
        for item in missing_items:
            print(f"- {item}")


if __name__ == "__main__":
    main()
