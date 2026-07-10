# Phase 16.5 — Testnet Execution Gate

## Objective

Submit one controlled Binance Futures testnet order after the Phase 16 validation and testnet shadow phases have passed.

This phase is still not real live trading. It uses Binance testnet only.

## Required Conditions

- Phase 16 validation passed.
- Phase 16.4 testnet shadow execution passed.
- Monitoring API is running.
- Emergency stop script exists.
- Testnet API keys are available.
- Real Binance keys are not used.
- `BINANCE_TESTNET=true`.
- `BINANCE_USE_TESTNET=true`.
- Manual confirmation is required before order submission.

## Required Environment

```bash
export BINANCE_TESTNET=true
export BINANCE_USE_TESTNET=true
export BINANCE_ENABLE_LIVE_TRADING=true
export LIVE_TRADING_ALLOWED=true

export BINANCE_API_KEY=your_binance_testnet_api_key
export BINANCE_API_SECRET=your_binance_testnet_api_secret
Execution Command
./scripts/phase16_testnet_execution_gate.sh

The script performs:

Git status check.
Monitoring API check.
Required input-file check.
API-key placeholder check.
Dry-run safety check.
Manual typed confirmation.
One Binance testnet order attempt.
Evidence report generation.
Automatic return to safe local flags inside the script.
Forbidden

Do not use real Binance API keys in this phase.

Do not set:

export BINANCE_TESTNET=false
export BINANCE_USE_TESTNET=false

Do not commit .env files or credentials.

Expected Evidence File
data/processed/phase16_testnet_execution_report.json

