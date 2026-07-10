# Phase 16.4 — Testnet Shadow Execution Plan

## Objective

Validate the Binance live-execution pathway in a safe shadow mode before enabling any real testnet order submission.

In this phase, the system uses Binance testnet configuration but keeps live execution disabled and forces dry-run execution.

No exchange order should be submitted during this phase.

---

## Required Safety Flags

```bash
export BINANCE_TESTNET=true
export BINANCE_USE_TESTNET=true
export BINANCE_ENABLE_LIVE_TRADING=false
export LIVE_TRADING_ALLOWED=false
export BINANCE_API_KEY=phase16_dummy_api_key
export BINANCE_API_SECRET=phase16_dummy_api_secret
Shadow Execution Command
python scripts/run_binance_live_execution.py \
  --signal data/processed/live_signal_dryrun.json \
  --risk data/processed/live_risk_dryrun.json \
  --dry-run
Expected result:

dry_run=true; no order submitted
Promotion Criteria

The project can move from testnet shadow to testnet execution only when:

Phase 16 validation passes.
Shadow dry-run completes successfully.
Monitoring health checks pass.
No order is submitted.
Manual approval is recorded.
Testnet API keys are available.
The emergency stop script is tested.
Forbidden in This Phase

Do not set:

export BINANCE_ENABLE_LIVE_TRADING=true
export LIVE_TRADING_ALLOWED=true

Do not use real Binance API keys.

Do not remove --dry-run.

