# Phase 8 — Anchored VWAP Engine

## Purpose

The Anchored VWAP engine confirms liquidity-sweep outcomes using volume-weighted price acceptance from specific anchor points. It supports three production anchor classes:

1. **Structural anchors** from high-quality liquidity levels.
2. **Session anchors** from configured UTC session boundaries.
3. **Sweep-event anchors** from penetration/consumption/rejection/acceptance events.

The engine is incremental and replay-deterministic. It does not recalculate VWAP from full history on every tick.

## Hot-path formula

For each active anchor:

```text
sum_pv  += price * volume
sum_v   += volume
sum_p2v += price * price * volume
AVWAP    = sum_pv / sum_v
variance = max(sum_p2v / sum_v - AVWAP^2, 0)
sigma    = sqrt(variance)
```

Deviation bands are emitted as:

```text
upper_band_1 = AVWAP + band_sigma * sigma
lower_band_1 = AVWAP - band_sigma * sigma
```

## Confirmation logic

For bullish sweep outcomes, AVWAP confirmation improves when:

- price is above AVWAP;
- AVWAP slope is non-negative;
- distance from AVWAP is not overextended;
- price reclaims AVWAP after previously trading below it.

For bearish sweep outcomes, the inverse applies.

The emitted `AnchoredVwapEvent` includes:

- `confirmation`
- `confirmation_score`
- `is_reclaim`
- `is_failure`
- `distance_from_price_bps`
- `band_z_score`
- `sweep_id` when tied to a sweep-event anchor

## Failure safety

- Invalid prices/quantities are ignored.
- Unhealthy reconstructed books are ignored for reclaim/failure checks.
- Anchors expire after `max_anchor_lifetime_ms`.
- Active anchors per symbol are capped by `max_active_anchors_per_symbol`.
- All outputs are contract-valid `AnchoredVwapEvent` objects.

## Replay

```bash
python scripts/run_anchored_vwap.py examples/avwap/avwap_replay.jsonl --output /tmp/avwap_events.jsonl
```

## Benchmark

```bash
python scripts/benchmark_avwap_engine.py
```

The benchmark measures incremental trade updates across multiple active anchors. Final performance must be measured on the target production server.
