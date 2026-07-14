from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path

OUTPUT_PATH = Path("data/processed/phase16_secrets_manager_key_handling_controls.json")

INPUTS = {
    "production_api_key_audit": Path("data/processed/phase16_production_api_key_permission_audit.json"),
    "manual_approval_record": Path("data/processed/phase16_micro_live_manual_approval_record.json"),
    "final_go_no_go_gate": Path("data/processed/phase16_final_micro_live_go_no_go_gate_spec.json"),
}


def git_clean() -> bool:
    result = subprocess.run(["git", "status", "--short"], capture_output=True, text=True)
    return result.stdout.strip() == ""


def tracked_secret_scan_clean() -> bool:
    patterns = [
        "BINANCE_API_SECRET=",
        "BINANCE_API_KEY=",
        "PRODUCTION_BINANCE_API_SECRET=",
        "PRODUCTION_BINANCE_API_KEY=",
    ]

    for pattern in patterns:
        result = subprocess.run(["git", "grep", "-n", pattern], capture_output=True, text=True)
        output = result.stdout.strip()

        if not output:
            continue

        for line in output.splitlines():
            allowed = ".env.example" in line or "docs/" in line or "README" in line
            if not allowed:
                return False

    return True


def file_contains(path: Path, text: str) -> bool:
    if not path.exists():
        return False
    return text in path.read_text(errors="ignore")


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
    gitignore = Path(".gitignore")

    controls = {
        "env_file_ignored": file_contains(gitignore, ".env"),
        "env_variants_ignored": file_contains(gitignore, ".env.*"),
        "env_example_allowed": file_contains(gitignore, "!.env.example"),
        "tracked_secret_scan_clean": tracked_secret_scan_clean(),
        "raw_secret_values_written_to_report": False,
        "production_secret_manager_selected": os.getenv("PRODUCTION_SECRET_MANAGER_SELECTED", "false") == "true",
        "production_secret_manager_ready": os.getenv("PRODUCTION_SECRET_MANAGER_READY", "false") == "true",
        "api_key_rotation_plan_exists": os.getenv("PRODUCTION_API_KEY_ROTATION_PLAN_EXISTS", "false") == "true",
        "emergency_key_revocation_process_exists": os.getenv("PRODUCTION_KEY_REVOCATION_PROCESS_EXISTS", "false") == "true",
        "access_limited_to_required_operator": os.getenv("PRODUCTION_SECRET_ACCESS_LIMITED", "false") == "true",
    }

    report = {
        "phase": "phase_16_19_secrets_manager_key_handling_controls",
        "generated_at_unix": int(time.time()),
        "scope": "secrets_manager_and_key_handling_controls_only",
        "not_approved_for": [
            "real_live_trading",
            "micro_live_execution",
            "production_binance_order_submission",
            "production_api_key_usage",
        ],
        "safety_flags": flags,
        "safe_mode_active": safe_mode_active,
        "inputs_present": inputs_present,
        "all_inputs_present": all(inputs_present.values()),
        "git_working_tree_clean": git_clean(),
        "secrets_controls": controls,
        "approved_for_micro_live_execution": False,
        "decision": "SECRETS_MANAGER_KEY_HANDLING_CONTROLS_CREATED_NOT_APPROVED_FOR_EXECUTION",
        "next_phase": "Phase 16.20 — Capital Limits and Loss-Limit Controls",
        "safety_notes": [
            "Never commit production API keys or secrets.",
            "Do not paste real keys into terminal history, docs, reports, screenshots, or Git.",
            "Use a private secrets manager or private local environment only.",
            "Live trading flags must remain disabled.",
            "This phase does not enable live trading.",
        ],
    }

    OUTPUT_PATH.write_text(json.dumps(report, indent=2))

    print(f"Report written to: {OUTPUT_PATH}")
    print(f"safe_mode_active={safe_mode_active}")
    print(f"all_inputs_present={report['all_inputs_present']}")
    print(f"git_working_tree_clean={report['git_working_tree_clean']}")
    print(f"env_file_ignored={controls['env_file_ignored']}")
    print(f"tracked_secret_scan_clean={controls['tracked_secret_scan_clean']}")
    print(f"approved_for_micro_live_execution={report['approved_for_micro_live_execution']}")
    print(f"decision={report['decision']}")


if __name__ == "__main__":
    main()
