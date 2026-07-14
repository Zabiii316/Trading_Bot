from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path

OUTPUT_PATH = Path("data/processed/phase16_production_api_key_permission_audit.json")

INPUTS = {
    "manual_approval_record": Path("data/processed/phase16_micro_live_manual_approval_record.json"),
    "final_go_no_go_gate": Path("data/processed/phase16_final_micro_live_go_no_go_gate_spec.json"),
    "post_soak_review": Path("data/processed/phase16_post_soak_review_micro_live_gap.json"),
}


def git_clean() -> bool:
    result = subprocess.run(["git", "status", "--short"], capture_output=True, text=True)
    return result.stdout.strip() == ""


def tracked_secret_scan_clean() -> bool:
    result = subprocess.run(
        ["git", "grep", "-n", "BINANCE_API_SECRET"],
        capture_output=True,
        text=True,
    )
    output = result.stdout.strip()
    if not output:
        return True

    allowed_refs = [".env.example", "README", "docs/"]
    return all(any(ref in line for ref in allowed_refs) for line in output.splitlines())


def main() -> None:
    flags = {
        "BINANCE_TESTNET": os.getenv("BINANCE_TESTNET"),
        "BINANCE_USE_TESTNET": os.getenv("BINANCE_USE_TESTNET"),
        "BINANCE_ENABLE_LIVE_TRADING": os.getenv("BINANCE_ENABLE_LIVE_TRADING"),
        "LIVE_TRADING_ALLOWED": os.getenv("LIVE_TRADING_ALLOWED"),
    }

    safe_mode_active = (
        flags.get("BINANCE_ENABLE_LIVE_TRADING") == "false"
        and flags.get("LIVE_TRADING_ALLOWED") == "false"
    )

    inputs_present = {name: path.exists() for name, path in INPUTS.items()}

    permission_audit = {
        "production_api_key_created": os.getenv("PRODUCTION_BINANCE_API_KEY_CREATED", "false") == "true",
        "production_api_key_ip_whitelisted": os.getenv("PRODUCTION_BINANCE_API_KEY_IP_WHITELISTED", "false") == "true",
        "withdrawal_permissions_disabled_verified": os.getenv("PRODUCTION_BINANCE_WITHDRAWALS_DISABLED_VERIFIED", "false") == "true",
        "futures_trading_permission_reviewed": os.getenv("PRODUCTION_BINANCE_FUTURES_PERMISSION_REVIEWED", "false") == "true",
        "secret_manager_ready": os.getenv("PRODUCTION_SECRET_MANAGER_READY", "false") == "true",
        "api_key_rotation_plan_exists": os.getenv("PRODUCTION_API_KEY_ROTATION_PLAN_EXISTS", "false") == "true",
        "raw_key_values_stored_in_report": False,
        "tracked_secret_scan_clean": tracked_secret_scan_clean(),
    }

    report = {
        "phase": "phase_16_18_production_api_key_exchange_permission_audit",
        "generated_at_unix": int(time.time()),
        "scope": "production_api_key_and_exchange_permission_audit_only",
        "not_approved_for": [
            "real_live_trading",
            "micro_live_execution",
            "production_binance_order_submission",
        ],
        "safety_flags": flags,
        "safe_mode_active": safe_mode_active,
        "inputs_present": inputs_present,
        "all_inputs_present": all(inputs_present.values()),
        "git_working_tree_clean": git_clean(),
        "permission_audit": permission_audit,
        "approved_for_micro_live_execution": False,
        "decision": "PRODUCTION_API_KEY_PERMISSION_AUDIT_CREATED_NOT_APPROVED_FOR_EXECUTION",
        "next_phase": "Phase 16.19 — Secrets Manager and Key Handling Controls",
        "safety_notes": [
            "Do not paste real Binance API keys into terminal, docs, Git, or reports.",
            "Production keys must be stored only in a private secrets manager or local private environment.",
            "Withdrawal permissions must remain disabled.",
            "IP whitelist must be verified before any future micro-live approval.",
            "This phase does not enable live trading.",
        ],
    }

    OUTPUT_PATH.write_text(json.dumps(report, indent=2))

    print(f"Report written to: {OUTPUT_PATH}")
    print(f"safe_mode_active={safe_mode_active}")
    print(f"all_inputs_present={report['all_inputs_present']}")
    print(f"git_working_tree_clean={report['git_working_tree_clean']}")
    print(f"tracked_secret_scan_clean={permission_audit['tracked_secret_scan_clean']}")
    print(f"approved_for_micro_live_execution={report['approved_for_micro_live_execution']}")
    print(f"decision={report['decision']}")


if __name__ == "__main__":
    main()
