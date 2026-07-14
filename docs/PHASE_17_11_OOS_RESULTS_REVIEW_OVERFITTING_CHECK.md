# Phase 17.11 — OOS Results Review and Overfitting Check

This phase reviews out-of-sample validation and test results for selected strategy candidates.

This phase does not approve:

- Real live trading
- Micro-live execution
- Production Binance order submission
- Production API-key usage

## Inputs

- data/processed/phase17_out_of_sample_candidate_validation_runner.json
- data/processed/phase17_parameter_sweep_results_review_candidate_selection.json

## Output Evidence

data/processed/phase17_oos_results_review_overfitting_check.json

## Review Checks

- Test net return must be positive
- Test profit factor must be acceptable
- Test win rate must be acceptable
- Test drawdown must be acceptable
- Test trade count must be acceptable
- Validation and test must point in the same direction
- In-sample to test degradation must not be excessive

## Expected Decision

OOS_REVIEW_COMPLETE_CANDIDATES_FORWARD_WALK_FORWARD_REQUIRED_NOT_APPROVED_FOR_EXECUTION

or

OOS_REVIEW_COMPLETE_OVERFITTING_OR_WEAK_OOS_DETECTED_STRATEGY_REWORK_REQUIRED_NOT_APPROVED_FOR_EXECUTION

## Next Phase

Phase 17.12 — Walk-Forward Validation Runner.
