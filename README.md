<<<<<<< HEAD
# Trading_Bot
=======
# Trading Bot — Phase 14: Binance Live Execution Adapter

This repository contains the Phase 14 implementation for the institutional trading-bot build. It extends the Phase 13 monitoring stack with a Binance USD-M Futures live execution adapter, while keeping execution safe by default through testnet-first configuration, explicit live-trading enablement, kill-switch checks, and reconciliation controls.

## Phase 14 scope

Implemented:

- Binance USD-M Futures REST execution client
- HMAC SHA256 signed request generation
- New order submission using approved `RiskDecisionEvent` objects
- Marketable-limit entry mapping: internal `MARKETABLE_LIMIT` → Binance `LIMIT` + `IOC`
- Idempotent client order IDs
- Order acknowledgement tracking
- Query-order and cancel-order workflows
- User-data listen-key lifecycle helper
- `ORDER_TRADE_UPDATE` mapping to internal `ExecutionOrderEvent` and `ExecutionFillEvent`
- Partial-fill handling from user-stream payloads
- Strict reduce-only close-order helper
- Hard/emergency kill-switch rejection before order submission
- Live-trading guard: mainnet order submission blocked unless `BINANCE_ENABLE_LIVE_TRADING=true`
- Exchange-vs-internal reconciliation layer
- Live execution benchmark script
- Unit tests for signing, mapping, REST client, order lifecycle, reduce-only safety, user stream lifecycle, and reconciliation

## Safety defaults

```text
BINANCE_TESTNET=true
BINANCE_ENABLE_LIVE_TRADING=false
```

With these defaults, the adapter is designed for Binance Futures Testnet validation. If the production Binance base URL is selected while `BINANCE_ENABLE_LIVE_TRADING=false`, the adapter rejects new entry orders before any exchange request is made.

## Quick start

Install development dependencies:

```bash
pip install -e .[dev]
```

Run all tests:

```bash
pytest -q
```

Run the live-execution mapping benchmark:

```bash
PYTHONPATH=libs/python:services/live_execution/python python scripts/benchmark_live_execution_mapping.py
```

Build-environment result:

```text
50,000 order mappings
10.058 microseconds per mapping
```

## Environment

```env
BINANCE_API_KEY=
BINANCE_API_SECRET=
BINANCE_TESTNET=true
BINANCE_ENABLE_LIVE_TRADING=false
BINANCE_RECV_WINDOW_MS=5000
BINANCE_REQUEST_TIMEOUT_S=5
BINANCE_MAX_RETRIES=2
BINANCE_RETRY_BACKOFF_S=0.25
BINANCE_ONE_WAY_MODE=true
BINANCE_CLIENT_ORDER_PREFIX=tb14
```

Use API keys with trading permission only. Do not use withdrawal-enabled keys.

## Dry-run validation

```bash
PYTHONPATH=libs/python:services/live_execution/python python scripts/run_binance_live_execution.py \
  --signal path/to/signal_event.json \
  --risk path/to/risk_decision_event.json \
  --dry-run
```

For actual testnet submission, provide a single valid `RiskDecisionEvent` JSON file and omit `--dry-run` only after configuring testnet API keys.

## Live execution module

```text
services/live_execution/python/trading_live_execution/
  config.py
  signing.py
  mapping.py
  client.py
  models.py
  engine.py
  reconciliation.py
  user_stream.py
```

## Prior phases included

1. Schemas and event contracts
2. Binance market-data recorder
3. Local order-book reconstruction
4. Raw data storage
5. Order-flow feature engine
6. Liquidity-level engine
7. Liquidity-sweep state machine
8. Anchored VWAP engine
9. Rule-based signal scorer
10. Event-driven replay/backtest engine
11. Risk engine
12. Paper execution engine
13. Monitoring dashboards
14. Binance live execution adapter

## Important note

This implementation includes the code path required to place Binance USD-M Futures orders, but it should be run on testnet first. Real-capital deployment still requires exchange account configuration, symbol filter validation, IP allowlisting, manual kill-switch drills, reconciliation drills, and the final Phase 15 controlled deployment process.


## Phase 15: Controlled Live Deployment

This repository now includes the operational deployment layer required before mainnet trading:

- Production-readiness gate validator
- Staged rollout plan from testnet shadow to controlled live
- Capital allocation controller
- Emergency drill validation
- Deployment manifests
- Testnet-to-live runbook
- Emergency response runbook
- Daily operations runbook
- Production readiness checklist

Run the readiness checker:

```bash
python scripts/run_production_readiness_check.py \
  --snapshot examples/deployment/readiness_pass_snapshot.json \
  --capital examples/deployment/capital_controls.json
```

Generate an immutable deployment manifest:

```bash
python scripts/generate_deployment_manifest.py \
  --commit-sha abc1234def \
  --image-tag trading-bot:0.15.0 \
  --stage micro_live \
  --config-hash sha256:deadbeef \
  --output artifacts/deployment_manifest.json
```
>>>>>>> ab38d41 (complete trading bot All phases passed  and ready for deployement)
