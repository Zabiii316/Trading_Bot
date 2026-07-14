# Phase 17.15 — Candidate Stress Test Runner

This phase runs stress tests against final strategy candidates using fee, slippage, latency, and stress-case scenarios.

This phase does not approve:

- Real live trading
- Micro-live execution
- Production Binance order submission
- Production API-key usage

## Inputs

- data/processed/phase17_candidate_risk_sizing_stress_test_plan.json
- data/processed/risk_stress_plans/
- data/processed/backtest_datasets/

## Output Evidence

data/processed/phase17_candidate_stress_test_runner.json

## Result Directory

data/processed/stress_test_results/

## Expected Decision

CANDIDATE_STRESS_TEST_COMPLETE_CANDIDATES_REQUIRE_REVIEW_NOT_APPROVED_FOR_EXECUTION

or

CANDIDATE_STRESS_TEST_FAILED_STRATEGY_REWORK_REQUIRED_NOT_APPROVED_FOR_EXECUTION

or

CANDIDATE_STRESS_TEST_SKIPPED_NO_RISK_PLANS_STRATEGY_REWORK_REQUIRED_NOT_APPROVED_FOR_EXECUTION

## Next Phase

Phase 17.16 — Stress Test Results Review.
