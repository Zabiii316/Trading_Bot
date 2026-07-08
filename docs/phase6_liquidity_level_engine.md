# Phase 6 — Liquidity-Level Engine

## Purpose

The liquidity-level engine converts replayed or live OHLCV bars into auditable `LiquidityLevelEvent` records. It identifies structural levels that may later become inputs to liquidity-sweep detection.

## Implemented detectors

- Confirmed swing highs/lows
- Equal highs/lows through clustering of repeated swing levels
- Session highs/lows from configurable UTC sessions
- Previous day high/low
- Previous week high/low
- Nearby round-number zones
- Adaptive price clustering
- Liquidity-quality scoring

## Design principles

1. **No live look-ahead leakage:** swing pivots are emitted only after the right-side confirmation bars are available.
2. **Incremental hot path:** the engine updates from one bar at a time and never rescans full history.
3. **Adaptive zones:** zone width uses the maximum of tick, ATR and short-term volatility components.
4. **Replay-ready contracts:** every emitted level includes level type, price, zone, touches, first/last seen time, quality score and metadata.
5. **Persistence-ready:** liquidity levels are mapped to the ClickHouse `liquidity_levels` table.

## Core modules

```text
services/liquidity/python/trading_liquidity/
  models.py          # Bar, Pivot, CandidateLevel, PriceCluster
  swings.py          # Confirmed swing high/low detector
  sessions.py        # Session high/low state
  reference.py       # Previous day/week levels
  round_numbers.py   # Round-number zones
  clustering.py      # Adaptive price clustering
  scoring.py         # Liquidity-quality scoring
  engine.py          # Orchestration and event emission
  replay.py          # JSONL replay utilities
```

## Quality score

The quality score is normalized to `[0, 1]` and combines:

- Touch count
- Recency
- Level type priority
- Accumulated volume
- Source diversity
- Prior sweep penalty

Reference levels such as previous week/day levels receive higher base type weight than ordinary swing levels. Round numbers are supported but deliberately receive lower standalone priority unless reinforced by clustering or other sources.

## Running replay

```bash
python scripts/run_liquidity_levels.py examples/liquidity/bars_replay.jsonl --output-jsonl /tmp/liquidity_levels.jsonl
```

## Benchmark

```bash
python scripts/benchmark_liquidity_engine.py
```

In the local build environment the benchmark processed 50,000 bar updates at approximately 28.483 microseconds per update.

## Storage

A new ClickHouse table is included:

```text
tradingbot.liquidity_levels
```

The storage mapper now routes `EventType.LIQUIDITY_LEVEL` to this table.
