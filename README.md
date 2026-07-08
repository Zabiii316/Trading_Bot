# Trading Signal Bot — Controlled Live Deployment

An institutional-grade, modular trading-signal pipeline for Binance USD-M futures research, paper execution, risk-controlled decisioning, monitoring, and staged live-deployment validation.

The system is designed around strict separation of concerns: market-data capture, normalized event contracts, order-book reconstruction, order-flow analytics, liquidity modelling, signal generation, risk controls, execution simulation, live-execution safety checks, observability, and production-readiness gates.

> **Important:** This repository is for engineering, research, controlled testing, and staged deployment workflows. Live trading is disabled by default and must only be enabled through explicit safety flags, manual approval, and production-readiness validation.

---

## Table of Contents

- [Project Overview](#project-overview)
- [Core Objectives](#core-objectives)
- [Technical Stack](#technical-stack)
- [System Architecture](#system-architecture)
- [Repository Structure](#repository-structure)
- [Development Phases](#development-phases)
- [Data Pipeline Workflow](#data-pipeline-workflow)
- [Execution Workflow](#execution-workflow)
- [Risk and Safety Controls](#risk-and-safety-controls)
- [Monitoring and Observability](#monitoring-and-observability)
- [Production Readiness Workflow](#production-readiness-workflow)
- [Controlled Live Deployment Workflow](#controlled-live-deployment-workflow)
- [Environment Variables](#environment-variables)
- [Testing](#testing)
- [GitHub Safety Policy](#github-safety-policy)
- [Operational Notes](#operational-notes)
- [Disclaimer](#disclaimer)

---

## Project Overview

This project implements a controlled live-deployment trading bot architecture for Binance USD-M futures.

The system processes raw market data into structured trading events, reconstructs local order books, extracts order-flow features, identifies liquidity levels and sweeps, confirms behaviour using anchored VWAP, scores trading signals, applies risk controls, simulates execution through a paper engine, and finally validates controlled live-execution pathways using strict operational gates.

The repository is structured as a multi-service Python monorepo with shared event contracts and replayable JSONL-based pipelines.

---

## Core Objectives

The main goals of this project are:

1. Build a replay-safe market-data and signal-generation pipeline.
2. Maintain strict schema validation across all services.
3. Separate research logic from execution logic.
4. Prevent accidental live trading through explicit multi-layer safety gates.
5. Provide deterministic test coverage for core services.
6. Support ClickHouse-backed event storage.
7. Provide monitoring endpoints for health, readiness, and Prometheus metrics.
8. Create a controlled path from local replay to testnet, micro-live, and controlled-live deployment.

---

## Technical Stack

### Language and Runtime

- Python 3.11+
- Bash scripts for local orchestration
- JSON / JSONL event replay format

### Backend and Services

- FastAPI
- Uvicorn
- Pydantic v2
- Async Python
- Modular service-based architecture

### Storage

- ClickHouse
- JSONL replay files
- Local processed artifacts for pipeline validation

### Exchange Integration

- Binance USD-M Futures
- Binance testnet support
- Signed REST request flow
- Live execution disabled by default

### Testing

- Pytest
- Async test support
- Contract validation tests
- Service-level unit tests
- Replay-path validation

### Monitoring

- FastAPI monitoring API
- Health endpoints
- Readiness endpoints
- Prometheus metrics export
- Component liveness and readiness tracking

### DevOps and Deployment

- Docker Compose
- Environment-based configuration
- Production readiness gate validation
- Controlled deployment runbook
- GitHub version control

---

## System Architecture

```mermaid
flowchart TD
    A[Raw Binance Market Data] --> B[Market Data Recorder]
    B --> C[Normalized Event Contracts]
    C --> D[ClickHouse Storage]

    C --> E[Order Book Reconstructor]
    E --> F[Reconstructed Book Events]

    C --> G[Order Flow Engine]
    F --> G
    G --> H[Order Flow Feature Events]

    C --> I[Liquidity Level Engine]
    I --> J[Liquidity Level Events]

    J --> K[Liquidity Sweep Engine]
    H --> K
    F --> K
    K --> L[Liquidity Sweep Events]

    L --> M[Anchored VWAP Engine]
    C --> M
    M --> N[AVWAP Confirmation Events]

    F --> O[Signal Scorer]
    H --> O
    L --> O
    N --> O
    O --> P[Signal Events]

    P --> Q[Risk Engine]
    Q --> R[Risk Decision Events]

    R --> S[Paper Execution Engine]
    F --> S
    S --> T[Paper Orders and Fills]

    R --> U[Binance Live Execution Adapter]
    P --> U
    U --> V[Testnet / Controlled Live Execution]

    W[Monitoring API] --> X[Health / Readiness / Metrics]
    Y[Production Readiness Gates] --> Z[Controlled Deployment Runbook]
.
├── contracts/
│   └── Shared event definitions and schemas
│
├── libs/
│   └── Shared Python utilities and reusable modules
│
├── services/
│   ├── market_data/
│   ├── order_book/
│   ├── features/
│   ├── liquidity/
│   ├── sweep/
│   ├── avwap/
│   ├── signals/
│   ├── risk/
│   ├── paper_execution/
│   ├── live_execution/
│   ├── monitoring/
│   └── deployment/
│
├── scripts/
│   └── CLI scripts for replay, validation, storage, and deployment checks
│
├── infra/
│   └── ClickHouse, deployment, and infrastructure configuration
│
├── docs/
│   ├── PHASE_16_CONTROLLED_LIVE_DEPLOYMENT_RUNBOOK.md
│   └── PHASE_16_LIVE_DEPLOYMENT_CHECKLIST.md
│
├── data/
│   ├── raw/
│   └── processed/
│
├── docker-compose.yml
├── pyproject.toml
├── pytest.ini
├── README.md
└── .gitignore


Development Phases
Phase 1 — Event Contracts and Repository Foundation

Established the base repository structure and shared event contracts.

Key outcomes:

Standardized event naming.
Contract-valid JSON payloads.
Shared Pydantic validation.
Consistent schema versioning.
Foundation for replayable service pipelines.
Phase 2 — Market Data Ingestion

Implemented raw Binance market-data capture and normalization.

Key outcomes:

Raw trades.
Aggregated trades.
Depth updates.
Order-book snapshots.
Normalized market-data event structure.
Phase 3 — ClickHouse Storage Layer

Added ClickHouse-backed event storage for normalized data.

Key outcomes:

Insert pipeline for JSON events.
Event table schemas.
Storage writer utility.
Query validation using ClickHouse client.
Event count verification.
Phase 4 — Local Order Book Reconstruction

Built a local order-book reconstruction engine.

Key outcomes:

Snapshot loading.
Depth delta application.
Sequence-health tracking.
Top-of-book bid/ask extraction.
Reconstructed book event emission.
Phase 5 — Order Flow Feature Engine

Created order-flow feature generation from trades and order-book views.

Key outcomes:

Rolling trade delta.
Cumulative volume delta.
Buy/sell volume analysis.
Queue imbalance.
Depth notional.
Absorption ratio.
Normalized order-flow feature events.
Phase 6 — Liquidity Level Engine

Implemented liquidity-level detection from OHLCV-style bar data.

Key outcomes:

Swing high and swing low detection.
Round-number liquidity levels.
Prior-session levels.
Quality scoring.
Liquidity level event generation.
Phase 7 — Liquidity Sweep Engine

Built sweep-state logic for detecting liquidity events around key levels.

Key outcomes:

Level armed state.
Penetration detection.
Consumption confirmation.
Rejection and acceptance candidates.
Sweep lifecycle events.
Bullish and bearish sweep outcomes.
Phase 8 — Anchored VWAP Confirmation

Added anchored VWAP confirmation around liquidity sweep events.

Key outcomes:

AVWAP session anchoring.
Confirmation score.
Bullish and bearish confirmation states.
Reclaim and failure handling.
Confirmation alignment with sweep outcome.
Phase 9 — Signal Scorer

Implemented a rule-based signal scorer combining liquidity, order-flow, AVWAP, regime, and execution context.

Key outcomes:

Signal candidate construction.
Liquidity score.
Order-flow score.
AVWAP score.
Regime score.
Execution score.
Final signal score.
Expected net return estimate.
Signal event generation.
Phase 10 — Replay and Storage Integration

Connected generated feature, sweep, AVWAP, and signal events into replayable JSONL flows.

Key outcomes:

Sorted event replay.
Deterministic input construction.
Storage writer integration.
ClickHouse verification.
End-to-end event traceability.
Phase 11 — Risk Engine

Implemented risk decisioning before execution.

Key outcomes:

Equity and margin controls.
Risk fraction per trade.
Maximum notional per trade.
Reduced-size status.
Approved quantity calculation.
Risk snapshot generation.
Risk decision event emission.
Phase 12 — Paper Execution Engine

Implemented simulated execution based on approved risk decisions and reconstructed book events.

Key outcomes:

Paper order creation.
Paper fill creation.
Position tracking.
Order lifecycle handling.
Reconciliation health reporting.
Execution event output.
Phase 13 — Binance Live Execution Safety Path

Added Binance USD-M futures live-execution adapter with safety controls.

Key outcomes:

Binance testnet support.
Signed REST request flow.
Dry-run mode.
Live trading disabled by default.
Explicit execution flags.
API-key validation.
Test coverage for live execution adapter.
Phase 14 — Monitoring and Observability

Implemented health, readiness, and metrics endpoints.

Key outcomes:

/health/live
/health/ready
/health
/metrics
Prometheus-compatible metrics.
Component liveness.
Component readiness.
Heartbeat freshness tracking.
Phase 15 — Production Readiness Gates

Implemented production-readiness validation before live deployment.

Key outcomes:

Operational snapshot validation.
Capital controls validation.
CI/test evidence checks.
Risk-engine health checks.
Monitoring health checks.
Reconciliation health checks.
Order-book sequence health checks.
Kill-switch test evidence.
Manual approval gate.
Live-trading opt-in gate.
Stage allocation and leverage caps.
Phase 16 — Controlled Live Deployment Runbook

Created a formal controlled live-deployment runbook.

Key outcomes:

Deployment stage definitions.
Safety flag policy.
Dry-run workflow.
Testnet execution workflow.
Micro-live workflow.
Controlled-live workflow.
Kill-switch procedure.
Rollback procedure.
Manual approval requirements.

docs/PHASE_16_CONTROLLED_LIVE_DEPLOYMENT_RUNBOOK.md
docs/PHASE_16_LIVE_DEPLOYMENT_CHECKLIST.md

docs/PHASE_16_CONTROLLED_LIVE_DEPLOYMENT_RUNBOOK.md
docs/PHASE_16_LIVE_DEPLOYMENT_CHECKLIST.md

raw.trade
raw.agg_trade
raw.depth_update
raw.order_book_snapshot

2. Order Book Reconstruction

Depth updates and snapshots are replayed into a local order book.

Output event: book.reconstructed

3. Order Flow Feature Generation

Trades and reconstructed books are transformed into order-flow features.

Output event: features.order_flow

4. Liquidity Level Detection

Bars are processed to detect liquidity levels.

Output event: liquidity.level

5. Liquidity Sweep Detection

Liquidity levels, order-flow features, raw trades, and reconstructed books are replayed into the sweep engine.

Output event: liquidity.sweep

6. AVWAP Confirmation

Sweep events are validated using anchored VWAP logic.

Output event: features.anchored_vwap

7. Signal Scoring

The signal scorer combines sweep outcome, order-flow, AVWAP, regime, and execution context.

Output event: signal.generated

8. Risk Decision

Signals are passed through the risk engine before any execution step.

Output event: risk.decision

9. Execution

Risk-approved signals may enter: paper execution
dry-run live execution
testnet execution
micro-live execution
controlled-live execution

Execution Workflow
Paper Execution

Paper execution validates the trading logic without submitting live exchange orders.

python scripts/run_paper_execution.py \
  --fee-bps 4 \
  --slippage-bps 2 \
  data/processed/paper_execution_input_with_book.jsonl \
  > data/processed/paper_execution_raw.txt

Filter JSONL output if required:
grep '^{' data/processed/paper_execution_raw.txt > data/processed/paper_execution.jsonl
Binance Dry Run

Dry run validates live-execution input without submitting an exchange order.
export BINANCE_TESTNET=true
export BINANCE_ENABLE_LIVE_TRADING=false
export LIVE_TRADING_ALLOWED=false

python scripts/run_binance_live_execution.py \
  --signal data/processed/live_signal_dryrun.json \
  --risk data/processed/live_risk_dryrun.json \
  --dry-run
Expected behaviour:
{
  "submitted": false,
  "reasons": [
    "dry_run: true; no order submitted"
  ]
}
Binance Testnet Execution

Only testnet API credentials should be used at this stage.
export BINANCE_TESTNET=true
export BINANCE_ENABLE_LIVE_TRADING=true
export LIVE_TRADING_ALLOWED=true

export BINANCE_API_KEY="your_testnet_key"
export BINANCE_API_SECRET="your_testnet_secret"
Then submit one controlled testnet order:
python scripts/run_binance_live_execution.py \
  --signal data/processed/live_signal_dryrun.json \
  --risk data/processed/live_risk_dryrun.json

Risk and Safety Controls

The system includes multiple safety layers before live execution.

Key Risk Controls
Maximum risk fraction per trade.
Maximum notional per trade.
Maximum open positions.
Available margin validation.
Reduced-size decisioning.
Approved quantity calculation.
Daily loss limits.
Weekly loss limits.
Portfolio drawdown limits.
Manual approval gate.
Kill-switch validation.
Live-trading opt-in flag.
Required Safety Flags

Live trading requires all three conditions to be explicit: export BINANCE_TESTNET=false
export BINANCE_ENABLE_LIVE_TRADING=true
export LIVE_TRADING_ALLOWED=true
If any one of these is missing or false, the system must not submit a real live order.

Monitoring and Observability

Start the monitoring API: PYTHONPATH="$PWD/libs/python:$PWD/services/monitoring/python" \
python -m uvicorn trading_monitoring.app:app --host 127.0.0.1 --port 8081
Health checks:
curl -s http://127.0.0.1:8081/metrics | head -40
mportant metrics include:
trading_events_total
trading_event_lag_ms
trading_component_up
trading_component_ready
trading_component_last_heartbeat_ms
trading_orderbook_sequence_healthy
trading_orderbook_spread_bps
trading_orderflow_delta
trading_orderflow_cvd
trading_orderflow_queue_imbalance_l1
trading_liquidity_levels_active
trading_liquidity_level_quality
trading_liquidity_sweeps_total
trading_avwap_confirmation_score
trading_avwap_distance_bps

Production Readiness Workflow

Run the production readiness gate before any controlled deployment:
python scripts/run_production_readiness_check.py \
  --snapshot data/processed/operational_snapshot.json \
  --capital data/processed/capital_controls.json \
  --output data/processed/production_readiness_report.json

Review the report:
cat data/processed/production_readiness_report.json | python -m json.tool

A deployment should not proceed if the report contains blocking failures.

Key gates include:

CI test suite.
Immutable release reference.
Risk engine health.
Monitoring health.
Reconciliation health.
Order-book sequence health.
Kill-switch test.
Critical alerts.
Stale components.
Daily loss limit.
Weekly loss limit.
Portfolio drawdown limit.
Paper trade evidence.
Testnet order evidence.
Withdrawal permissions disabled.
Secret manager validation.
Live-trading flag.
Emergency drills.
Manual approval.
Capital allocation cap.
Stage leverage cap.

Controlled Live Deployment Workflow

The live deployment path is intentionally staged.

Stage 1 — Local

Purpose:

Validate contracts.
Run tests.
Replay events.
Verify paper execution.

Live orders:
No
Stage 2 — Testnet Shadow

Purpose:

Validate Binance execution inputs.
Use dry-run only.
Confirm risk decisions and signal payloads.

Live orders:
No real funds
Stage 3 — Testnet Execution

Purpose:

Submit controlled orders to Binance testnet.
Confirm exchange acknowledgement.
Validate reconciliation.

Live orders:
Testnet only
Stage 4 — Micro Live

Purpose:

Submit minimum-size real order.
Confirm safety controls.
Validate monitoring and kill switch.

Live orders:
Yes, minimum size only
Stage 5 — Controlled Live

Purpose:

Operate under strict capital, leverage, and loss limits.
Continue monitoring and reconciliation.
Maintain manual review requirements.

Live orders:
Yes, capped
Stage 6 — Full Live

Purpose:

Only after extended validation.
Requires institutional approval and complete operational controls.

Live orders:
Yes
Environment Variables

Recommended safe defaults:
export BINANCE_TESTNET=true
export BINANCE_USE_TESTNET=true
export BINANCE_ENABLE_LIVE_TRADING=false
export LIVE_TRADING_ALLOWED=false

Binance credentials:
export BINANCE_API_KEY="your_key"
export BINANCE_API_SECRET="your_secret"
Monitoring: export PYTHONPATH="$PWD/libs/python:$PWD/services/monitoring/python"
ClickHouse:
export CLICKHOUSE_URL="http://localhost:8123"
export CLICKHOUSE_USER="trading_bot"
export CLICKHOUSE_PASSWORD="trading_bot"
export CLICKHOUSE_DATABASE="tradingbot"
Testing

Run all tests:

python -m pytest -q

Run selected service tests:

python -m pytest services/monitoring/python/tests -q
python -m pytest services/live_execution/python/tests -q
python -m pytest services/paper_execution/python/tests -q
python -m pytest services/risk/python/tests -q
python -m pytest services/signals/python/tests -q

Expected status:

tests passed

A known non-blocking warning may appear from FastAPI/Starlette test client dependencies.

Disclaimer

This repository is for educational, engineering, research, and controlled-deployment purposes only.

It does not provide financial advice, investment advice, or trading recommendations. Trading futures, crypto assets, or leveraged products involves significant risk, including the possible loss of capital. Any live trading must be performed only after independent review, appropriate risk controls, and explicit manual approval.

