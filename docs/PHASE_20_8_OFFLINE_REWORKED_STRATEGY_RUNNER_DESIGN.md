# Phase 20.8 — Offline Reworked Strategy Runner Design

This phase designs the offline reworked strategy runner.

Runner design stages:

- Load existing local datasets only
- Validate dataset schema
- Generate reworked strategy variants
- Apply regime filters
- Apply multi-timeframe confirmation
- Apply fee/slippage edge filters
- Simulate entries and exits offline only
- Calculate metrics
- Apply Candidate Rejection Rules V2
- Apply Strategy Quality Gate V2
- Write research-only results

This phase does not approve:

- Backtest execution
- Paper shadow execution start
- Real live trading
- Micro-live execution
- Production Binance order submission
- Production API-key usage
- Real capital usage

## Output Evidence

data/processed/phase20_offline_reworked_strategy_runner_design.json

## Runtime Record

runtime/phase20_offline_reworked_strategy_runner_design_state.json

## Record File

data/processed/phase20_strategy_rework/offline_reworked_strategy_runner_design.json

## Expected Decision

PHASE_20_OFFLINE_REWORKED_STRATEGY_RUNNER_DESIGNED_RESEARCH_ONLY_NOT_EXECUTED

## Next Phase

Phase 20.9 — Offline Reworked Strategy Runner Dry Run Plan.
