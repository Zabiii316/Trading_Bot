from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]


def test_readiness_cli_passes_example():
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "run_production_readiness_check.py"),
            "--snapshot",
            str(ROOT / "examples" / "deployment" / "readiness_pass_snapshot.json"),
            "--capital",
            str(ROOT / "examples" / "deployment" / "capital_controls.json"),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    report = json.loads(result.stdout)
    assert report["decision"] in {"approve", "approve_with_limits"}


def test_readiness_cli_fails_bad_example():
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "run_production_readiness_check.py"),
            "--snapshot",
            str(ROOT / "examples" / "deployment" / "readiness_fail_snapshot.json"),
            "--capital",
            str(ROOT / "examples" / "deployment" / "capital_controls.json"),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 1
    report = json.loads(result.stdout)
    assert report["decision"] == "hold"
