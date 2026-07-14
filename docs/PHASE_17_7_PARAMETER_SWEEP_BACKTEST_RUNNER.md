# Phase 17.7 — Parameter Sweep Backtest Runner

This phase runs a controlled local parameter sweep after the baseline strategy failed the Phase 17.5 quality gate.

This phase does not approve:

- Real live trading
- Micro-live execution
- Production Binance order submission
- Production API-key usage

## Parameter Sweep Inputs

- Phase 17.6 strategy rework design
- Phase 17.3 backtest datasets

## Output Evidence

data/processed/phase17_parameter_sweep_backtest_runner.json

## Full Sweep Results

data/processed/backtest_results/phase17_parameter_sweep_results.jsonl

## Expected Decision

PARAMETER_SWEEP_BACKTEST_COMPLETE_REVIEW_REQUIRED_NOT_APPROVED_FOR_EXECUTION

## Next Phase

Phase 17.8 — Parameter Sweep Results Review and Candidate Selection.
