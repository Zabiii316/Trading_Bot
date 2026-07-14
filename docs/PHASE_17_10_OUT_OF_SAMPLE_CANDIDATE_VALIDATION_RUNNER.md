# Phase 17.10 — Out-of-Sample Candidate Validation Runner

This phase validates selected parameter-sweep candidates using out-of-sample validation and test datasets.

This phase does not approve:

- Real live trading
- Micro-live execution
- Production Binance order submission
- Production API-key usage

## Inputs

- data/processed/phase17_parameter_sweep_results_review_candidate_selection.json
- data/processed/phase17_out_of_sample_validation_dataset_split.json
- data/processed/oos_datasets/

## Output Evidence

data/processed/phase17_out_of_sample_candidate_validation_runner.json

## Result Directory

data/processed/oos_results/

## Expected Decision

OOS_CANDIDATE_VALIDATION_COMPLETE_CANDIDATES_REQUIRE_REVIEW_NOT_APPROVED_FOR_EXECUTION

or

OOS_CANDIDATE_VALIDATION_FAILED_STRATEGY_REWORK_REQUIRED_NOT_APPROVED_FOR_EXECUTION

## Next Phase

Phase 17.11 — OOS Results Review and Overfitting Check.
