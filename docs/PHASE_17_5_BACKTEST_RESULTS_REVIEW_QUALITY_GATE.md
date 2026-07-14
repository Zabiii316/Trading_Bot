# Phase 17.5 — Backtest Results Review and Strategy Quality Gate

This phase reviews Phase 17 baseline historical backtest results.

This phase does not approve:

- Real live trading
- Micro-live execution
- Production Binance order submission
- Production API-key usage

## Quality Gate Thresholds

- Minimum profit factor: 1.20
- Minimum win rate: 45%
- Maximum drawdown: 20%
- Minimum trades: 30
- Net return must be positive

## Output Evidence

data/processed/phase17_backtest_results_review_quality_gate.json

## Expected Decision

BACKTEST_QUALITY_GATE_FAILED_STRATEGY_REWORK_REQUIRED_NOT_APPROVED_FOR_EXECUTION

## Next Phase

Phase 17.6 — Strategy Rework Plan and Parameter Sweep Design.
