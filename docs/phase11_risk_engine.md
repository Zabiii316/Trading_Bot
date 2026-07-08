# Phase 11: Risk Engine

Phase 11 introduces a deterministic, fail-closed pre-trade risk layer. The module consumes `SignalEvent` objects and account/position snapshots, then emits contract-valid `RiskDecisionEvent` objects.

## Responsibilities

- Risk-fraction based position sizing
- Stop-distance validation
- Exposure caps
- Symbol, strategy, net, gross and correlated-cluster limits
- Leverage validation
- Margin-buffer validation
- Daily and weekly realized-loss limits
- Portfolio and strategy drawdown controls
- Duplicate signal protection
- Signal stale/expiry rejection
- Kill-switch integration

## Hot-path design

The `RiskEngine.evaluate()` method performs no network or database I/O. It accepts immutable snapshots and returns deterministic decisions. This allows the service to be called from live execution, replay, backtesting and paper trading without changing semantics.

## Kill-switch levels

1. `soft_strategy_suspension`: stops new strategy-level signals when scoped to a symbol or strategy.
2. `hard_trading_halt`: halts new orders and should trigger open-order cancellation in the execution layer.
3. `emergency_flatten`: halts new orders and instructs later execution modules to flatten exposure using reduce-only orders.

The risk service treats unavailable or invalid state as a rejection condition wherever possible.

## Sizing formula

```text
risk_budget_quote = account_equity_quote * risk_fraction_per_trade
risk_per_unit = abs(entry_candidate - stop)
raw_quantity = risk_budget_quote / risk_per_unit
approved_quantity = min(raw_quantity, exposure_caps, leverage_caps, margin_caps)
```

Quantities are rounded down to the configured `quantity_step`.

## CLI

```bash
python scripts/run_risk_engine.py examples/risk/risk_replay.jsonl --equity 100000
```

## Benchmark

```bash
python scripts/benchmark_risk_engine.py
```
