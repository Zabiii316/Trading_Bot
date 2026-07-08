# Phase 3 — Local Order-Book Reconstruction

## Goal

Phase 3 converts normalized Binance depth updates into a deterministic local limit order book. The component is designed to be the authoritative source of top-of-book, spread, compact depth, and sequence-health state for all downstream order-flow, sweep-detection, risk, and execution modules.

## Design principles

- **Native Binance sequencing:** snapshot + diff-depth synchronization is implemented directly rather than hidden behind CCXT or a generic adapter.
- **Fail closed:** any sequence gap, crossed book, buffer overflow, or integrity fault marks the book unhealthy and requests resynchronization.
- **Replayable:** given the same snapshot and depth-update sequence, the same checksums and reconstructed events are emitted.
- **Low allocation path:** each side of the book uses a price-to-quantity map plus a sorted index, avoiding full-book sorting after every update.
- **Compact downstream event:** downstream services consume `ReconstructedBookEvent`, not the entire raw book.

## Snapshot + diff-depth lifecycle

```text
Open diff-depth stream
        │
        ▼
Buffer incoming DepthUpdateEvent objects
        │
        ▼
Fetch REST depth snapshot
        │
        ▼
Load snapshot into LocalOrderBook
        │
        ▼
Discard stale buffered updates where u <= lastUpdateId
        │
        ▼
Apply first crossing update where U <= lastUpdateId + 1 <= u
        │
        ▼
Apply contiguous live updates
        │
        ▼
Emit ReconstructedBookEvent after every accepted update
```

## Gap rules

The sequencer maintains strict data integrity:

- Before snapshot: depth updates are buffered.
- Stale updates with `final_update_id <= local last_update_id` are discarded.
- The first applied update must bridge `lastUpdateId + 1`.
- For USD-M futures events that include `pu`, all subsequent live events must satisfy `pu == previous_u`.
- For spot-style events without `pu`, the update range must satisfy `U <= previous_u + 1 <= u`.
- Any violation puts the sequencer into `RESYNC_REQUIRED`.

## Emitted event

Each accepted update emits:

- `last_update_id`
- best bid and ask
- spread and spread in basis points
- bid/ask notional depth for top N levels
- deterministic SHA-256 checksum over top N bid/ask levels
- sequence-health flag

## Production notes

This Phase 3 implementation is Python-based to stay aligned with the existing prototype and test stack. The module is structured so that the hot path can later be ported to Rust without changing event contracts. For higher-throughput production use, the same interface should be preserved while moving `SideBook`, `LocalOrderBook`, and `DepthSequencer` to Rust.
