#!/usr/bin/env bash
set -euo pipefail

echo "=================================================="
echo "PHASE 16 EMERGENCY STOP / KILL SWITCH"
echo "=================================================="

mkdir -p runtime

cat > runtime/KILL_SWITCH_ACTIVE << EOT
kill_switch_active=true
activated_at=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
reason=manual_emergency_stop
EOT

cat > runtime/safe_trading_flags.env << EOT
export BINANCE_ENABLE_LIVE_TRADING=false
export LIVE_TRADING_ALLOWED=false
export BINANCE_TESTNET=true
export BINANCE_USE_TESTNET=true
EOT

echo ""
echo "✅ Kill switch file created:"
echo "runtime/KILL_SWITCH_ACTIVE"

echo ""
echo "✅ Safe trading flags written:"
echo "runtime/safe_trading_flags.env"

echo ""
echo "Stopping local monitoring server on port 8081 if running..."
lsof -tiTCP:8081 -sTCP:LISTEN | xargs kill -9 2>/dev/null || true

echo ""
echo "IMPORTANT:"
echo "To apply safe flags to your current terminal, run:"
echo ""
echo "source runtime/safe_trading_flags.env"
echo ""
echo "Manual exchange actions if real trading was active:"
echo "1. Open Binance"
echo "2. Cancel open orders"
echo "3. Flatten positions if needed"
echo "4. Disable API key"
echo "5. Record incident notes"

echo ""
echo "✅ Emergency stop completed."
