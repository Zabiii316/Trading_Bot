# Event Topics

Recommended Phase 2 topic naming convention:

```text
<domain>.<venue>.<event_kind>.<symbol>
```

Raw Binance market-data topics emitted by the Phase 2 recorder:

```text
raw.binance.agg_trade.BTCUSDT
raw.binance.trade.BTCUSDT
raw.binance.depth.BTCUSDT
raw.binance.book_ticker.BTCUSDT
raw.binance.snapshot.BTCUSDT
```

Downstream topics planned for later phases:

```text
book.reconstructed.BTCUSDT
features.order_flow.BTCUSDT
features.anchored_vwap.BTCUSDT
liquidity.level.BTCUSDT
liquidity.sweep.BTCUSDT
signal.generated.BTCUSDT
risk.decisions
execution.orders
execution.fills
system.alerts
```

Rules:

1. Raw exchange events are append-only.
2. Feature events are derived and replayable.
3. Signals cannot create orders directly.
4. Execution requires an approved `RiskDecisionEvent`.
5. Kill-switch state must be fail-closed.

## Phase 9 signal scorer topics

```text
signals.generated.<SYMBOL>
signals.rejected.<SYMBOL>
```

`signals.generated` carries contract-valid `SignalEvent` payloads emitted only
after liquidity sweep, order-flow, AVWAP, regime and execution-quality checks.

## Phase 11 risk topics

```text
risk.decisions
risk.kill_switch
```

`risk.decisions` carries `RiskDecisionEvent` payloads emitted after pre-trade validation. `risk.kill_switch` carries scoped or global kill-switch state changes.
