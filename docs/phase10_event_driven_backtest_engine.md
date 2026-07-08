# Phase 10 — Event-Driven Replay and Backtest Engine

## Objective

Phase 10 adds a deterministic simulation loop that replays contract-valid events and evaluates generated signals against reconstructed order-book data. It is intentionally replay-first: every decision is driven by timestamped event contracts so the same JSONL file produces the same trades, equity curve, and performance report.

## Supported Replay Inputs

The replay engine accepts all existing event contracts:

- raw aggregate trades
- raw trades
- depth updates
- order-book snapshots
- reconstructed books
- order-flow feature events
- liquidity-level events
- liquidity-sweep events
- anchored VWAP events
- signal events

Only `SignalEvent` and `ReconstructedBookEvent` directly drive simulated execution in V1. Other event types are counted and preserved in diagnostics so replay files can include full pipeline output without breaking deterministic execution.

## Execution Model

V1 uses a conservative taker-style simulation:

1. A signal enters a pending queue.
2. The signal becomes executable after `latency_ms`.
3. The next reconstructed book for the same symbol is used as the executable market state.
4. Long entries buy at best ask plus slippage.
5. Short entries sell at best bid minus slippage.
6. Stops and targets are evaluated from subsequent reconstructed books.
7. Per-side fees and slippage are applied to all fills.
8. Signals that expire before simulated latency elapses are rejected as expired.

This is not yet a queue-position or market-impact model. That should be added after paper-trading logs show whether entry quality requires depth-walking, maker/taker split, or queue-fill simulation.

## Position Sizing

Position size is calculated from risk budget:

```text
risk_budget = equity * risk_fraction_per_trade
quantity = risk_budget / abs(entry_price - stop_price)
```

The resulting quantity is capped by:

```text
max_notional = equity * max_notional_fraction * max_leverage
```

Optional quantity step, minimum quantity, and minimum notional constraints are supported.

## Performance Report

The report includes:

- event count
- trade count
- win rate
- gross profit
- gross loss
- profit factor
- net PnL
- net return
- average trade PnL
- average win/loss
- max drawdown
- per-trade Sharpe approximation
- total fees
- rejected signals
- expired signals
- full trade ledger
- equity curve
- event-type counts

## Determinism Rules

Replay files must be sorted by `event_time_ms`. Non-monotonic files fail fast because time-travel in replay can hide bugs and create unrealistic results.

The simulation loop does not use wall-clock time or random fills. Slippage, fees, and latency are explicit config inputs.

## Run Example

```bash
PYTHONPATH=libs/python:services/backtest/python \
python scripts/run_event_backtest.py examples/backtest/backtest_replay.jsonl \
  --output /tmp/backtest_report.json \
  --initial-equity 100000 \
  --risk-fraction 0.0025 \
  --fee-bps 4 \
  --slippage-bps 1.5 \
  --latency-ms 250
```

## Benchmark

```bash
PYTHONPATH=libs/python:services/backtest/python \
python scripts/benchmark_backtest_engine.py
```

## Design Constraints

- Fail closed on malformed events.
- Reject non-monotonic replay files.
- Keep execution assumptions explicit and auditable.
- Keep event ingestion separated from simulation logic.
- Keep V1 simple enough to validate before adding queue-aware execution.
