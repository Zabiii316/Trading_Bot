# Phase 17.12 — Walk-Forward Validation Runner

This phase performs walk-forward validation for candidates that passed the OOS review stage.

This phase does not approve:

- Real live trading
- Micro-live execution
- Production Binance order submission
- Production API-key usage

## Inputs

- data/processed/phase17_oos_results_review_overfitting_check.json
- data/processed/backtest_datasets/

## Output Evidence

data/processed/phase17_walk_forward_validation_runner.json

## Result Directory

data/processed/walk_forward_results/

## Expected Decision

WALK_FORWARD_VALIDATION_COMPLETE_CANDIDATES_REQUIRE_FINAL_REVIEW_NOT_APPROVED_FOR_EXECUTION

or

WALK_FORWARD_VALIDATION_FAILED_STRATEGY_REWORK_REQUIRED_NOT_APPROVED_FOR_EXECUTION

or

WALK_FORWARD_VALIDATION_SKIPPED_NO_FORWARD_CANDIDATES_STRATEGY_REWORK_REQUIRED_NOT_APPROVED_FOR_EXECUTION

## Next Phase

Phase 17.13 — Final Strategy Candidate Review.
