# Phase 20.5 — Offline Reworked Strategy Backtest Spec

This phase creates the offline backtest specification for the reworked strategy.

This phase does not run the backtest.

Backtest spec areas:

- Reworked entry logic
- Regime filters
- Multi-timeframe confirmation
- Volatility-aware exits
- Fee/slippage sensitivity
- Candidate rejection rules
- Research-only quality limits

This phase does not approve:

- Backtest execution
- Paper shadow execution start
- Real live trading
- Micro-live execution
- Production Binance order submission
- Production API-key usage
- Real capital usage

## Output Evidence

data/processed/phase20_offline_reworked_strategy_backtest_spec.json

## Runtime Record

runtime/phase20_offline_reworked_strategy_backtest_spec_state.json

## Record File

data/processed/phase20_strategy_rework/offline_reworked_strategy_backtest_spec.json

## Expected Decision

PHASE_20_OFFLINE_REWORKED_STRATEGY_BACKTEST_SPEC_CREATED_RESEARCH_ONLY_NOT_EXECUTED

## Next Phase

Phase 20.6 — Strategy Quality Gate V2 Design.
