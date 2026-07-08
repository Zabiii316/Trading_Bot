# Phase 9 — Rule-Based Signal Scorer

## Purpose

The Phase 9 signal scorer converts confirmed liquidity-sweep outcomes into
trade-ready `SignalEvent` contracts. It synthesizes:

- Liquidity sweep quality
- Order-flow confirmation
- Anchored VWAP confirmation
- Market-regime assumptions
- Execution quality from the latest reconstructed book

The engine is deterministic, replayable, and emits at most one signal per sweep
by default.

## Scoring formula

```text
final_score =
  0.30 * liquidity_score
+ 0.30 * order_flow_score
+ 0.20 * avwap_score
+ 0.10 * regime_score
+ 0.10 * execution_score
```

Default thresholds:

```text
liquidity_score >= 0.60
order_flow_score >= 0.60
avwap_score >= 0.55
regime_score >= 0.50
execution_score >= 0.50
final_score >= 0.72
expected_net_return_bps > 0
```

## Execution-quality scoring

Execution quality uses book health, spread and depth:

- unhealthy sequence => score 0
- low spread => higher score
- deeper top-10 notional => higher score

## Entry and exit levels

For bullish outcomes, the scorer uses the current best ask as entry and places
the stop below the sweep extreme plus a configurable tick buffer. Targets are
risk-multiple based. Bearish outcomes invert the logic.

## Fail-closed behavior

The engine rejects signals when:

- the sweep has not reached a final state
- AVWAP is missing, stale, directionally mismatched, or failed
- book or order-flow features are stale
- regime is not tradeable
- component scores or expected net return fail thresholds
- the sweep already emitted a signal

## Replay

```bash
python scripts/run_signal_scorer.py examples/signals/signal_replay.jsonl
```

## Benchmark

```bash
python scripts/benchmark_signal_scorer.py
```
