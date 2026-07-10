#!/usr/bin/env bash
set -euo pipefail

export PYTHONPATH="$PWD/contracts/python:$PWD/libs/python:$PWD/services/live_execution/python:$PWD/services/monitoring/python:$PWD/services/risk/python:$PWD/services/signals/python:$PWD/services/paper_execution/python:${PYTHONPATH:-}"

echo "=================================================="
echo "Phase 16.5 — Binance Testnet Execution Gate"
echo "=================================================="

mkdir -p runtime data/processed

cleanup() {
  cat > runtime/safe_trading_flags.env << EOT
export BINANCE_TESTNET=true
export BINANCE_USE_TESTNET=true
export BINANCE_ENABLE_LIVE_TRADING=false
export LIVE_TRADING_ALLOWED=false
EOT
  echo ""
  echo "Safe flags written to runtime/safe_trading_flags.env"
  echo "Run this after the script:"
  echo "source runtime/safe_trading_flags.env"
}
trap cleanup EXIT

echo ""
echo "1) Checking Git status..."
if ! git diff --quiet || ! git diff --cached --quiet; then
  echo "❌ Git working tree has uncommitted changes."
  git status
  exit 1
fi
echo "✅ Git working tree clean."

echo ""
echo "2) Checking kill switch state..."
if [[ -f runtime/KILL_SWITCH_ACTIVE ]]; then
  echo "❌ Kill switch is active:"
  cat runtime/KILL_SWITCH_ACTIVE
  exit 1
fi
echo "✅ Kill switch is not active."

echo ""
echo "3) Applying testnet execution flags..."
export BINANCE_TESTNET=true
export BINANCE_USE_TESTNET=true
export BINANCE_ENABLE_LIVE_TRADING=true
export LIVE_TRADING_ALLOWED=true

echo "BINANCE_TESTNET=$BINANCE_TESTNET"
echo "BINANCE_USE_TESTNET=$BINANCE_USE_TESTNET"
echo "BINANCE_ENABLE_LIVE_TRADING=$BINANCE_ENABLE_LIVE_TRADING"
echo "LIVE_TRADING_ALLOWED=$LIVE_TRADING_ALLOWED"

echo ""
echo "4) Checking API keys..."
if [[ -z "${BINANCE_API_KEY:-}" || -z "${BINANCE_API_SECRET:-}" ]]; then
  echo "❌ BINANCE_API_KEY and BINANCE_API_SECRET are required."
  exit 1
fi

if [[ "${BINANCE_API_KEY}" == "phase16_dummy_api_key" || "${BINANCE_API_SECRET}" == "phase16_dummy_api_secret" ]]; then
  echo "❌ Dummy keys cannot be used for testnet execution."
  exit 1
fi
echo "✅ API key variables are present."

echo ""
echo "5) Checking required input files..."
test -f data/processed/live_signal_dryrun.json
test -f data/processed/live_risk_testnet_min_qty.json
echo "✅ Signal and risk input files found."

echo ""
echo "6) Checking monitoring API..."
if curl -s http://127.0.0.1:8081/health/live >/tmp/phase16_testnet_health_live.json; then
  echo "✅ Monitoring API reachable."
else
  echo "❌ Monitoring API is not reachable on port 8081."
  exit 1
fi

echo ""
echo "7) Running pre-execution dry-run check..."

python scripts/run_binance_live_execution.py --signal data/processed/live_signal_dryrun.json --risk data/processed/live_risk_testnet_min_qty.json --dry-run > runtime/phase16_testnet_pre_dryrun.txt

cat runtime/phase16_testnet_pre_dryrun.txt

if grep -q '"submitted": true' runtime/phase16_testnet_pre_dryrun.txt; then
  echo "❌ Dry-run unexpectedly submitted an order."
  exit 1
fi

echo "✅ Dry-run safety check passed."

echo ""
echo "=================================================="
echo "MANUAL CONFIRMATION REQUIRED"
echo "=================================================="
echo "This will attempt ONE Binance FUTURES TESTNET order."
echo "It must not use real Binance production keys."
echo ""
read -r -p "Type TESTNET_ORDER to continue: " CONFIRMATION

if [[ "$CONFIRMATION" != "TESTNET_ORDER" ]]; then
  echo "❌ Confirmation failed. Testnet order cancelled."
  exit 1
fi

echo ""
echo "8) Submitting one Binance testnet order..."

set +e
python scripts/run_binance_live_execution.py --signal data/processed/live_signal_dryrun.json --risk data/processed/live_risk_testnet_min_qty.json > runtime/phase16_testnet_execution_raw.txt 2>&1
RESULT_CODE=$?
set -e

cat runtime/phase16_testnet_execution_raw.txt

echo ""
echo "9) Writing testnet execution evidence report..."

python - <<'PY'
from __future__ import annotations

import json
import os
import time
from pathlib import Path

raw_path = Path("runtime/phase16_testnet_execution_raw.txt")
dryrun_path = Path("runtime/phase16_testnet_pre_dryrun.txt")
out_path = Path("data/processed/phase16_testnet_execution_report.json")

raw = raw_path.read_text() if raw_path.exists() else ""
dry = dryrun_path.read_text() if dryrun_path.exists() else ""

raw_lower = raw.lower()
submitted = '"submitted": true' in raw_lower or '"submitted":true' in raw_lower
blocked = "live trading disabled" in raw_lower
api_error = "api error" in raw_lower or "binance api error" in raw_lower

report = {
    "phase": "phase_16_5_testnet_execution_gate",
    "generated_at_unix": int(time.time()),
    "environment": {
        "BINANCE_TESTNET": os.getenv("BINANCE_TESTNET"),
        "BINANCE_USE_TESTNET": os.getenv("BINANCE_USE_TESTNET"),
        "BINANCE_ENABLE_LIVE_TRADING": os.getenv("BINANCE_ENABLE_LIVE_TRADING"),
        "LIVE_TRADING_ALLOWED": os.getenv("LIVE_TRADING_ALLOWED"),
        "has_binance_api_key": bool(os.getenv("BINANCE_API_KEY")),
        "has_binance_api_secret": bool(os.getenv("BINANCE_API_SECRET")),
    },
    "execution_mode": "binance_futures_testnet",
    "order_submission_allowed": True,
    "dry_run_output_tail": dry[-3000:],
    "raw_output_tail": raw[-5000:],
    "submitted": submitted,
    "blocked_by_live_disabled_gate": blocked,
    "api_error_detected": api_error,
    "process_exit_code": int(os.getenv("RESULT_CODE", "0")) if os.getenv("RESULT_CODE") else None,
    "passed": submitted and not blocked and not api_error,
}

out_path.write_text(json.dumps(report, indent=2))
print(f"Testnet execution report written to: {out_path}")
print(f"passed={report['passed']}")
PY

if [[ "$RESULT_CODE" -ne 0 ]]; then
  echo "❌ Testnet execution command exited with code $RESULT_CODE."
  echo "Review data/processed/phase16_testnet_execution_report.json"
  exit "$RESULT_CODE"
fi

if grep -q '"passed": true' data/processed/phase16_testnet_execution_report.json; then
  echo "✅ Phase 16.5 testnet execution passed."
else
  echo "⚠️ Testnet execution completed but report did not pass. Review the report."
  exit 1
fi
