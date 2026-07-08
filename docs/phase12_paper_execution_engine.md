# Phase 12 — Paper Execution Engine

The paper execution engine converts approved `RiskDecisionEvent` objects into simulated `ExecutionOrderEvent` orders, applies deterministic fills against live/replayed `ReconstructedBookEvent` objects, emits `ExecutionFillEvent` records, and maintains an internal paper position ledger.

## Design principles

- Uses the same order/fill contracts planned for the live Binance adapter.
- Performs no network or database I/O in the hot path.
- Fails closed on unhealthy or stale reconstructed books.
- Supports marketable-limit entry simulation with configurable slippage, fee, top-level participation, TTL, and partial-fill policy.
- Tracks open orders, fill state, positions, and reconciliation diagnostics.

## Order lifecycle

```text
ACKNOWLEDGED
  -> PARTIALLY_FILLED
  -> FILLED
  -> CANCELLED / EXPIRED
```

The engine emits an order lifecycle update after each fill or cancellation.

## Reconciliation

`reconcile()` checks:

- negative remaining quantity
- overfilled orders
- filled orders with remaining quantity
- non-positive positions
- invalid mark prices

A healthy reconciliation report is required before moving from paper execution to live adapter development.

## Event bus topics

Recommended topics:

```text
execution.orders
execution.fills
paper.reconciliation
```

## Compatibility

The module is intentionally paper-only but contract-compatible with the planned Binance live execution adapter in Phase 14.
