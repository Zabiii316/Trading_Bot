#!/usr/bin/env bash
set -euo pipefail

export PYTHONPATH="$PWD/contracts/python:$PWD/libs/python:$PWD/services/live_execution/python:$PWD/services/monitoring/python:$PWD/services/risk/python:$PWD/services/signals/python:$PWD/services/paper_execution/python:${PYTHONPATH:-}"

echo "=================================================="
echo "Phase 16.4 — Testnet Shadow Execution"
echo "=================================================="

mkdir -p data/processed runtime

echo ""
echo "1) Applying safe testnet shadow flags..."

export BINANCE_TESTNET=true
export BINANCE_USE_TESTNET=true
export BINANCE_ENABLE_LIVE_TRADING=false
export LIVE_TRADING_ALLOWED=false
export BINANCE_API_KEY="${BINANCE_API_KEY:-phase16_dummy_api_key}"
export BINANCE_API_SECRET="${BINANCE_API_SECRET:-phase16_dummy_api_secret}"

echo "BINANCE_TESTNET=$BINANCE_TESTNET"
echo "BINANCE_USE_TESTNET=$BINANCE_USE_TESTNET"
echo "BINANCE_ENABLE_LIVE_TRADING=$BINANCE_ENABLE_LIVE_TRADING"
echo "LIVE_TRADING_ALLOWED=$LIVE_TRADING_ALLOWED"

echo ""
echo "2) Checking required input files..."

test -f data/processed/live_signal_dryrun.json
test -f data/processed/live_risk_dryrun.json

echo "✅ Dry-run signal and risk files found."

echo ""
echo "3) Checking monitoring API..."

if curl -s http://127.0.0.1:8081/health/live >/tmp/phase16_shadow_health_live.json; then
  echo "✅ Monitoring API reachable."
else
  echo "❌ Monitoring API is not reachable on port 8081."
  echo "Start it with:"
  echo 'PYTHONPATH="$PWD/libs/python:$PWD/services/monitoring/python" python -m uvicorn trading_monitoring.app:app --host 127.0.0.1 --port 8081'
  exit 1
fi

echo ""
echo "4) Running Binance execution path in forced dry-run shadow mode..."

python scripts/run_binance_live_execution.py \
  --signal data/processed/live_signal_dryrun.json \
  --risk data/processed/live_risk_dryrun.json \
  --dry-run > runtime/phase16_testnet_shadow_raw.txt

cat runtime/phase16_testnet_shadow_raw.txt

if grep -q '"submitted": true' runtime/phase16_testnet_shadow_raw.txt; then
  echo "❌ Shadow mode failed. An order was submitted."
  exit 1
fi

if grep -qi "no order submitted" runtime/phase16_testnet_shadow_raw.txt; then
  echo "✅ Shadow dry-run confirmed: no order submitted."
else
  echo "⚠️ Could not find exact no-order text. Review output manually."
fi

echo ""
echo "5) Writing shadow execution report..."

python - <<'INNERPY'
from __future__ import annotations

import json
import os
import time
from pathlib import Path

raw_path = Path("runtime/phase16_testnet_shadow_raw.txt")
out_path = Path("data/processed/phase16_testnet_shadow_report.json")

raw = raw_path.read_text() if raw_path.exists() else ""

report = {
    "phase": "phase_16_4_testnet_shadow_execution",
    "generated_at_unix": int(time.time()),
    "environment": {
        "BINANCE_TESTNET": os.getenv("BINANCE_TESTNET"),
        "BINANCE_USE_TESTNET": os.getenv("BINANCE_USE_TESTNET"),
        "BINANCE_ENABLE_LIVE_TRADING": os.getenv("BINANCE_ENABLE_LIVE_TRADING"),
        "LIVE_TRADING_ALLOWED": os.getenv("LIVE_TRADING_ALLOWED"),
        "has_binance_api_key": bool(os.getenv("BINANCE_API_KEY")),
        "has_binance_api_secret": bool(os.getenv("BINANCE_API_SECRET")),
    },
    "execution_mode": "forced_dry_run_shadow",
    "order_submission_allowed": False,
    "raw_output_tail": raw[-3000:],
    "passed": ('"submitted": true' not in raw.lower()) and ("no order submitted" in raw.lower()),
}

out_path.write_text(json.dumps(report, indent=2))
print(f"Shadow report written to: {out_path}")
print(f"passed={report['passed']}")
INNERPY

echo ""
echo "✅ Phase 16.4 testnet shadow execution completed."
