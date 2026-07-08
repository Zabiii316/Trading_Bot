# Phase 7 — Liquidity-Sweep State Machine

## Objective

Phase 7 converts structural liquidity levels and order-flow features into deterministic sweep lifecycle events. The engine is intentionally explainable and fail-closed: it does not infer a tradable event from stale order-flow data, unhealthy books, or unclassified liquidity zones.

## Inputs

- `LiquidityLevelEvent` from Phase 6
- `OrderFlowFeatureEvent` from Phase 5
- `ReconstructedBookEvent` / `BookView` from Phase 3

## Output

- `LiquiditySweepEvent`

## Lifecycle

```text
LEVEL_ARMED
  -> APPROACHING_LEVEL
  -> PENETRATING_LEVEL
  -> CONSUMPTION_CONFIRMED
  -> REJECTION_CANDIDATE | ACCEPTANCE_CANDIDATE
  -> ORDER_FLOW_CONFIRMED
  -> EXPIRED
```

## Sweep direction

High-side levels such as previous-day highs, swing highs and equal highs are classified as upside-liquidity candidates. Low-side levels are classified as downside-liquidity candidates. Round numbers remain context-dependent until the engine sees current price.

## Rejection logic

- Upside sweep + reclaim back below the zone => bearish rejection candidate.
- Downside sweep + reclaim back above the zone => bullish rejection candidate.
- Candidate is confirmed only when order flow supports the reversal bias.

## Acceptance logic

- Upside sweep + hold above the zone for `acceptance_hold_ms` => bullish acceptance candidate.
- Downside sweep + hold below the zone for `acceptance_hold_ms` => bearish acceptance candidate.
- Candidate is confirmed only when order flow supports the continuation bias.

## Fail-closed rules

The engine emits no new transition from an unhealthy reconstructed book. Armed and partial contexts expire if they exceed configured lifetimes. Levels below `min_level_quality` are rejected at ingestion.

## Storage

Phase 7 adds the `tradingbot.liquidity_sweeps` ClickHouse table and a storage mapper for `LiquiditySweepEvent`.
