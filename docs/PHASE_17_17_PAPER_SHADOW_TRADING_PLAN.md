# Phase 17.17 — Paper Shadow Trading Plan

This phase creates a paper shadow trading plan for candidates that passed stress test review.

This phase does not approve:

- Real live trading
- Micro-live execution
- Production Binance order submission
- Production API-key usage

## Inputs

- data/processed/phase17_stress_test_results_review.json
- data/processed/stress_review_candidates/

## Output Evidence

data/processed/phase17_paper_shadow_trading_plan.json

## Plan Directory

data/processed/paper_shadow_plans/

## Paper Shadow Rules

- Duration: 7 days
- Minimum shadow signals: 25
- Real capital: not allowed
- Exchange order submission: disabled
- Manual review required after shadow period

## Expected Decision

PAPER_SHADOW_TRADING_PLAN_CREATED_NOT_STARTED_NOT_APPROVED_FOR_EXECUTION

or

PAPER_SHADOW_TRADING_PLAN_SKIPPED_NO_FORWARD_CANDIDATES_STRATEGY_REWORK_REQUIRED

## Next Phase

Phase 17.18 — Paper Shadow Execution Harness.
