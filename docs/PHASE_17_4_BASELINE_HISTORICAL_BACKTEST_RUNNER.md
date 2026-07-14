# Phase 17.4 — Baseline Historical Backtest Runner

This phase runs a baseline local historical backtest using the Phase 17 backtest datasets.

This phase does not approve:

- Real live trading
- Micro-live execution
- Production Binance order submission
- Production API-key usage

## Backtest Method

Baseline long-only moving-average strategy:

- Fast window: 5
- Slow window: 20
- Fee: 4 bps per side
- Slippage: 2 bps per side

## Output Evidence

data/processed/phase17_baseline_historical_backtest_runner.json

## Result Directory

data/processed/backtest_results/

## Expected Decision

BASELINE_HISTORICAL_BACKTEST_COMPLETE_REVIEW_REQUIRED_NOT_APPROVED_FOR_EXECUTION

## Next Phase

Phase 17.5 — Backtest Results Review and Strategy Quality Gate.
