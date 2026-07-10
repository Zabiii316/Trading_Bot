#!/usr/bin/env bash
set -euo pipefail

export PYTHONPATH="$PWD/contracts/python:$PWD/libs/python:$PWD/services/live_execution/python:$PWD/services/monitoring/python:$PWD/services/risk/python:$PWD/services/signals/python:$PWD/services/paper_execution/python:${PYTHONPATH:-}"


echo "=================================================="
echo "Phase 16 — Controlled Live Deployment Validation"
echo "=================================================="

echo ""
echo "1) Checking Git status..."
if ! git diff --quiet || ! git diff --cached --quiet; then
  echo "❌ Git working tree has uncommitted changes."
  git status
  exit 1
fi
echo "✅ Git working tree clean."

echo ""
echo "2) Checking safety environment flags..."

BINANCE_TESTNET_VALUE="${BINANCE_TESTNET:-}"
BINANCE_USE_TESTNET_VALUE="${BINANCE_USE_TESTNET:-}"
BINANCE_ENABLE_LIVE_TRADING_VALUE="${BINANCE_ENABLE_LIVE_TRADING:-}"
LIVE_TRADING_ALLOWED_VALUE="${LIVE_TRADING_ALLOWED:-}"

echo "BINANCE_TESTNET=${BINANCE_TESTNET_VALUE}"
echo "BINANCE_USE_TESTNET=${BINANCE_USE_TESTNET_VALUE}"
echo "BINANCE_ENABLE_LIVE_TRADING=${BINANCE_ENABLE_LIVE_TRADING_VALUE}"
echo "LIVE_TRADING_ALLOWED=${LIVE_TRADING_ALLOWED_VALUE}"

if [[ "${BINANCE_ENABLE_LIVE_TRADING_VALUE}" != "false" ]]; then
  echo "❌ BINANCE_ENABLE_LIVE_TRADING must be false for validation."
  exit 1
fi

if [[ "${LIVE_TRADING_ALLOWED_VALUE}" != "false" ]]; then
  echo "❌ LIVE_TRADING_ALLOWED must be false for validation."
  exit 1
fi

echo "✅ Live trading is disabled."

# Dummy credentials for validation only.
# These are not real exchange keys. They allow the live-execution client
# to initialize while BINANCE_ENABLE_LIVE_TRADING=false prevents order submission.
export BINANCE_API_KEY="${BINANCE_API_KEY:-phase16_dummy_api_key}"
export BINANCE_API_SECRET="${BINANCE_API_SECRET:-phase16_dummy_api_secret}"

echo ""
echo "3) Running critical test suite..."
python -m pytest \
  services/monitoring/python/tests \
  services/live_execution/python/tests \
  services/paper_execution/python/tests \
  services/risk/python/tests \
  services/signals/python/tests \
  -q

echo "✅ Critical tests passed."

echo ""
echo "4) Checking monitoring API..."

if curl -s http://127.0.0.1:8081/health/live >/tmp/phase16_health_live.json; then
  echo "✅ /health/live reachable."
else
  echo "❌ Monitoring API not reachable on port 8081."
  echo "Start it with:"
  echo 'PYTHONPATH="$PWD/libs/python:$PWD/services/monitoring/python" python -m uvicorn trading_monitoring.app:app --host 127.0.0.1 --port 8081'
  exit 1
fi

curl -s http://127.0.0.1:8081/health/ready >/tmp/phase16_health_ready.json
curl -s http://127.0.0.1:8081/health >/tmp/phase16_health.json
curl -s http://127.0.0.1:8081/metrics >/tmp/phase16_metrics.txt

echo "✅ Monitoring endpoints reachable."

echo ""
echo "5) Running Binance dry-run safety check..."

python scripts/run_binance_live_execution.py \
  --signal data/processed/live_signal_dryrun.json \
  --risk data/processed/live_risk_dryrun.json \
  --dry-run >/tmp/phase16_binance_dryrun.json

cat /tmp/phase16_binance_dryrun.json

if grep -q '"submitted": true' /tmp/phase16_binance_dryrun.json; then
  echo "❌ Dry-run unexpectedly submitted an order."
  exit 1
fi

echo "✅ Dry-run did not submit an order."

echo ""
echo "6) Running no-live safety gate check..."

python scripts/run_binance_live_execution.py \
  --signal data/processed/live_signal_dryrun.json \
  --risk data/processed/live_risk_dryrun.json >/tmp/phase16_live_disabled_check.json

cat /tmp/phase16_live_disabled_check.json

if grep -q '"submitted": true' /tmp/phase16_live_disabled_check.json; then
  echo "❌ Live-disabled safety gate failed. Order submission attempted."
  exit 1
fi

if ! grep -q 'live trading disabled' /tmp/phase16_live_disabled_check.json; then
  echo "❌ Expected live trading disabled reason was not found."
  exit 1
fi

echo "✅ Live-disabled safety gate passed."

echo ""
echo "7) Running production readiness validator..."

python scripts/run_production_readiness_check.py \
  --snapshot data/processed/operational_snapshot.json \
  --capital data/processed/capital_controls.json \
  --output data/processed/production_readiness_report.json

echo "✅ Production readiness report generated."

echo ""
echo "8) Checking production readiness report..."

cat data/processed/production_readiness_report.json | python -m json.tool

if grep -q '"decision": "hold"' data/processed/production_readiness_report.json; then
  echo "⚠️ Production readiness decision is HOLD."
  echo "This may be expected unless you intentionally patched manual approval and live flags."
else
  echo "✅ Production readiness decision is not HOLD."
fi

echo ""
echo "=================================================="
echo "✅ Phase 16 validation completed."
echo "=================================================="
