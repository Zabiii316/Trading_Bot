# Phase 14 — Binance Live Execution Adapter

## Scope

This phase adds the first live execution adapter for Binance USD-M Futures. It converts approved `RiskDecisionEvent` objects into signed Binance order requests, tracks acknowledgements and order lifecycle updates, emits shared `ExecutionOrderEvent` / `ExecutionFillEvent` contracts, and reconciles internal state against exchange open orders and positions.

The adapter is safe by default:

- Binance futures **testnet** is enabled by default.
- Live order submission is blocked unless `BINANCE_ENABLE_LIVE_TRADING=true`.
- API keys are read only from environment variables or a secret manager.
- Withdrawal permissions are never required.
- The system fails closed when hard/emergency kill-switch levels are active.

## Implemented Modules

```text
services/live_execution/python/trading_live_execution/
  config.py           Runtime configuration and environment loading
  signing.py          HMAC SHA256 signing helpers
  mapping.py          Internal contract ↔ Binance parameter/status mapping
  client.py           Narrow async USD-M Futures REST client
  models.py           Live execution dataclasses
  engine.py           Live execution adapter and order lifecycle handling
  reconciliation.py   Exchange-vs-internal reconciliation layer
  user_stream.py      Listen-key lifecycle and user-data event iterator
```

## Order Submission

`BinanceLiveExecutionAdapter.submit_entry()` accepts:

- `SignalEvent`
- approved `RiskDecisionEvent`
- event timestamp

It rejects submissions when:

- the risk decision is not approved/reduced-size
- signal and risk IDs do not match
- quantity is zero
- duplicate signal already exists
- hard/emergency kill switch is active
- live base URL is selected but live trading is not explicitly enabled

For V1, signal entries use marketable limit orders:

```text
internal MARKETABLE_LIMIT → Binance LIMIT + IOC
```

## Reduce-Only Safety

`submit_reduce_only_close()` is provided for emergency flattening and position reduction workflows. It always sends `reduceOnly=true` and uses the opposite side of the current position amount.

## User-Data Stream

`BinanceUserDataStream` manages listen-key creation, keepalive and close workflows, and exposes an async event iterator for user-stream messages. Production orchestration should route `ORDER_TRADE_UPDATE` messages into `BinanceLiveExecutionAdapter.on_order_trade_update()`. REST reconciliation remains the fallback if the stream disconnects.

## Reconciliation

`BinanceReconciler.reconcile()` compares:

- local open orders vs exchange open orders
- client order IDs
- executed quantity sanity
- reduce-only flag consistency
- exchange non-zero positions

Any discrepancy should trigger a hard trading halt in production orchestration.

## Required Environment

```env
BINANCE_API_KEY="your_key_here"
BINANCE_API_SECRET="your_secret_here"
BINANCE_TESTNET=true
BINANCE_ENABLE_LIVE_TRADING=false
BINANCE_RECV_WINDOW_MS=5000
BINANCE_REQUEST_TIMEOUT_S=5
BINANCE_MAX_RETRIES=2
BINANCE_RETRY_BACKOFF_S=0.25
BINANCE_ONE_WAY_MODE=true
BINANCE_CLIENT_ORDER_PREFIX=tb14
```

## Production Notes

Before connecting real capital:

1. Run on Binance futures testnet.
2. Confirm all symbol filters, quantity steps and notional limits.
3. Enable IP allowlisting for API keys.
4. Use keys with trading permission only, never withdrawal permission.
5. Confirm one-way vs hedge mode.
6. Confirm reduce-only close behaviour for every symbol.
7. Test forced reconciliation failures and kill-switch activation.
8. Run paper and testnet execution in parallel before live.
