from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path


GO_NO_GO_PATH = Path("data/processed/phase16_go_no_go_summary.json")
OUTPUT_PATH = Path("data/processed/phase16_manual_approval_checklist.json")


def git_clean() -> bool:
    result = subprocess.run(
        ["git", "status", "--short"],
        capture_output=True,
        text=True,
    )
    return result.stdout.strip() == ""


def read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text())


def main() -> None:
    print("==================================================")
    print("Phase 16.9 — Manual Approval Checklist")
    print("==================================================")
    print("")
    print("This approval is for CONTROLLED TESTNET REVIEW ONLY.")
    print("It is NOT approval for real live trading.")
    print("")

    go_no_go = read_json(GO_NO_GO_PATH)

    safety_flags = {
        "BINANCE_TESTNET": os.getenv("BINANCE_TESTNET"),
        "BINANCE_USE_TESTNET": os.getenv("BINANCE_USE_TESTNET"),
        "BINANCE_ENABLE_LIVE_TRADING": os.getenv("BINANCE_ENABLE_LIVE_TRADING"),
        "LIVE_TRADING_ALLOWED": os.getenv("LIVE_TRADING_ALLOWED"),
    }

    print("Current safety flags:")
    for key, value in safety_flags.items():
        print(f"{key}={value}")

    print("")
    print("Required manual confirmations:")
    print("1. Safe mode is enabled.")
    print("2. Production live trading remains disabled.")
    print("3. Binance testnet evidence has passed.")
    print("4. Cleanup report confirms no open testnet orders.")
    print("5. This approval is not for real live trading.")
    print("")

    confirm_safe = input("Type SAFE_MODE_CONFIRMED: ").strip()
    confirm_testnet = input("Type TESTNET_REVIEW_ONLY: ").strip()
    confirm_no_live = input("Type NO_REAL_LIVE_TRADING: ").strip()

    approvals = {
        "safe_mode_confirmed": confirm_safe == "SAFE_MODE_CONFIRMED",
        "testnet_review_only_confirmed": confirm_testnet == "TESTNET_REVIEW_ONLY",
        "no_real_live_trading_confirmed": confirm_no_live == "NO_REAL_LIVE_TRADING",
    }

    go_no_go_passed = bool(go_no_go.get("go_decision"))
    git_is_clean = git_clean()

    safe_mode_active = (
        safety_flags.get("BINANCE_ENABLE_LIVE_TRADING") == "false"
        and safety_flags.get("LIVE_TRADING_ALLOWED") == "false"
    )

    checklist = {
        "phase": "phase_16_9_manual_approval_checklist",
        "generated_at_unix": int(time.time()),
        "approval_scope": "controlled_testnet_runbook_review_only",
        "not_approved_for": [
            "real_live_trading",
            "micro_live_execution",
            "production_exchange_order_submission",
        ],
        "safety_flags": safety_flags,
        "go_no_go_summary_present": GO_NO_GO_PATH.exists(),
        "go_no_go_passed": go_no_go_passed,
        "git_working_tree_clean": git_is_clean,
        "safe_mode_active": safe_mode_active,
        "manual_approvals": approvals,
        "approved_for_controlled_testnet_review": (
            go_no_go_passed
            and git_is_clean
            and safe_mode_active
            and all(approvals.values())
        ),
        "next_phase": "Phase 16.10 — Micro-Live Readiness Gap Analysis",
        "safety_notes": [
            "This checklist does not authorize real live trading.",
            "Production Binance API keys must never be committed.",
            "Withdrawal permissions must remain disabled for any future real exchange key.",
            "Micro-live requires a separate approval gate.",
            "Emergency stop must be tested before any future execution stage.",
        ],
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(checklist, indent=2))

    print("")
    print(f"Checklist written to: {OUTPUT_PATH}")
    print(
        "approved_for_controlled_testnet_review="
        f"{checklist['approved_for_controlled_testnet_review']}"
    )

    if not checklist["approved_for_controlled_testnet_review"]:
        print("")
        print("Approval checklist did not pass. Review:")
        for key, value in checklist.items():
            if key in {
                "go_no_go_passed",
                "git_working_tree_clean",
                "safe_mode_active",
            }:
                print(f"- {key}: {value}")


if __name__ == "__main__":
    main()
