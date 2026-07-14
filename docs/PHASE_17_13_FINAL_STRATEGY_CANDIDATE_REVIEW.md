# Phase 17.13 — Final Strategy Candidate Review

This phase reviews walk-forward validation results and selects final strategy candidates for risk sizing and stress testing.

This phase does not approve:

- Real live trading
- Micro-live execution
- Production Binance order submission
- Production API-key usage

## Inputs

- data/processed/phase17_walk_forward_validation_runner.json
- data/processed/phase17_oos_results_review_overfitting_check.json
- data/processed/phase17_parameter_sweep_results_review_candidate_selection.json

## Output Evidence

data/processed/phase17_final_strategy_candidate_review.json

## Candidate Output Directory

data/processed/final_strategy_candidates/

## Expected Decision

FINAL_STRATEGY_CANDIDATE_REVIEW_COMPLETE_CANDIDATES_SELECTED_RISK_REVIEW_REQUIRED_NOT_APPROVED_FOR_EXECUTION

or

FINAL_STRATEGY_CANDIDATE_REVIEW_COMPLETE_NO_CANDIDATES_STRATEGY_REWORK_REQUIRED_NOT_APPROVED_FOR_EXECUTION

## Next Phase

Phase 17.14 — Candidate Risk Sizing and Stress Test Plan.
