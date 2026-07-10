from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data" / "processed" / "phase16_validation_report.json"


def run(command: list[str]) -> dict:
    started = time.time()
    result = subprocess.run(
        command,
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    finished = time.time()

    return {
        "command": " ".join(command),
        "returncode": result.returncode,
        "duration_seconds": round(finished - started, 3),
        "stdout_tail": result.stdout[-3000:],
        "stderr_tail": result.stderr[-3000:],
        "passed": result.returncode == 0,
    }


def main() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)

    report = {
        "phase": "phase_16_controlled_live_deployment",
        "generated_at_unix": int(time.time()),
        "environment": {
            "BINANCE_TESTNET": os.getenv("BINANCE_TESTNET"),
            "BINANCE_USE_TESTNET": os.getenv("BINANCE_USE_TESTNET"),
            "BINANCE_ENABLE_LIVE_TRADING": os.getenv("BINANCE_ENABLE_LIVE_TRADING"),
            "LIVE_TRADING_ALLOWED": os.getenv("LIVE_TRADING_ALLOWED"),
            "has_binance_api_key": bool(os.getenv("BINANCE_API_KEY")),
            "has_binance_api_secret": bool(os.getenv("BINANCE_API_SECRET")),
        },
        "checks": {},
    }

    report["checks"]["git_status"] = run(["git", "status", "--short"])

    report["checks"]["critical_tests"] = run([
        "python", "-m", "pytest",
        "services/monitoring/python/tests",
        "services/live_execution/python/tests",
        "services/paper_execution/python/tests",
        "services/risk/python/tests",
        "services/signals/python/tests",
        "-q",
    ])

    report["checks"]["binance_dry_run"] = run([
        "python",
        "scripts/run_binance_live_execution.py",
        "--signal",
        "data/processed/live_signal_dryrun.json",
        "--risk",
        "data/processed/live_risk_dryrun.json",
        "--dry-run",
    ])

    report["checks"]["production_readiness"] = run([
        "python",
        "scripts/run_production_readiness_check.py",
        "--snapshot",
        "data/processed/operational_snapshot.json",
        "--capital",
        "data/processed/capital_controls.json",
        "--output",
        "data/processed/production_readiness_report.json",
    ])

    report["passed"] = all(check["passed"] for check in report["checks"].values())

    OUTPUT.write_text(json.dumps(report, indent=2))
    print(f"Phase 16 validation report written to: {OUTPUT}")
    print(f"passed={report['passed']}")


if __name__ == "__main__":
    main()
