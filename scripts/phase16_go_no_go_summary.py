from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path


OUTPUT_PATH = Path("data/processed/phase16_go_no_go_summary.json")

REQUIRED_REPORTS = {
    "phase16_validation": Path("data/processed/phase16_validation_report.json"),
    "phase16_shadow_execution": Path("data/processed/phase16_testnet_shadow_report.json"),
    "phase16_testnet_execution": Path("data/processed/phase16_testnet_execution_report.json"),
    "phase16_reconciliation": Path("data/processed/phase16_testnet_reconciliation_report.json"),
    "phase16_cleanup": Path("data/processed/phase16_testnet_cleanup_report.json"),
}


def git_status_clean() -> bool:
    result = subprocess.run(
        ["git", "status", "--short"],
        capture_output=True,
        text=True,
    )
    return result.stdout.strip() == ""


def load_report(path: Path) -> dict:
    if not path.exists():
        return {
            "exists": False,
            "passed": False,
            "error": f"Missing report: {path}",
        }

    try:
        data = json.loads(path.read_text())
    except Exception as exc:
        return {
            "exists": True,
            "passed": False,
            "error": str(exc),
        }

    return {
        "exists": True,
        "passed": bool(data.get("passed")),
        "phase": data.get("phase"),
        "summary": data,
    }


def main() -> None:
    reports = {
        name: load_report(path)
        for name, path in REQUIRED_REPORTS.items()
    }

    required_passed = all(item["passed"] for item in reports.values())
    all_exist = all(item["exists"] for item in reports.values())
    clean_git = git_status_clean()

    execution = reports["phase16_testnet_execution"]["summary"]
    cleanup = reports["phase16_cleanup"]["summary"]
    reconciliation = reports["phase16_reconciliation"]["summary"]

    go_conditions = {
        "all_required_reports_exist": all_exist,
        "all_required_reports_passed": required_passed,
        "git_working_tree_clean": clean_git,
        "testnet_order_submitted": bool(execution.get("submitted")),
        "testnet_order_acknowledged": execution.get("order_status") == "acknowledged",
        "testnet_order_reconciled": bool(reconciliation.get("passed")),
        "no_open_orders_after_cleanup": cleanup.get("open_orders_after") == 0,
        "cleanup_passed": bool(cleanup.get("passed")),
    }

    go_decision = all(go_conditions.values())

    summary = {
        "phase": "phase_16_8_controlled_testnet_go_no_go_summary",
        "generated_at_unix": int(time.time()),
        "decision": "GO_FOR_CONTROLLED_TESTNET_RUNBOOK_REVIEW" if go_decision else "NO_GO_REVIEW_REQUIRED",
        "go_decision": go_decision,
        "go_conditions": go_conditions,
        "reports": {
            name: {
                "exists": item["exists"],
                "passed": item["passed"],
                "phase": item.get("phase"),
                "error": item.get("error"),
            }
            for name, item in reports.items()
        },
        "safety_notes": [
            "Live production trading must remain disabled.",
            "Only Binance Futures testnet was used.",
            "Real production Binance API keys must not be committed.",
            "Micro-live deployment requires a separate manual approval gate.",
            "Emergency stop script must remain available before any further execution stage.",
        ],
        "next_recommended_phase": "Phase 16.9 — Controlled Testnet Runbook Documentation and Manual Approval Checklist",
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(summary, indent=2))

    print(f"GO decision: {go_decision}")
    print(f"Decision: {summary['decision']}")
    print(f"Report written to: {OUTPUT_PATH}")

    if not go_decision:
        print("")
        print("NO-GO reasons:")
        for key, value in go_conditions.items():
            if not value:
                print(f"- {key}: {value}")


if __name__ == "__main__":
    main()
