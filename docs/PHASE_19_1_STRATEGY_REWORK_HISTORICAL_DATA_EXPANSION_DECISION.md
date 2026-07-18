# Phase 19.1 — Strategy Rework And Historical Data Expansion Decision

This phase selects the Phase 19 research path after Phase 18 safety closeout.

Selected path:

historical_data_expansion_first_then_strategy_rework

This phase does not approve:

- Paper shadow execution start
- Real live trading
- Micro-live execution
- Production Binance order submission
- Production API-key usage
- Real capital usage

## Inputs

- data/processed/phase18_final_safety_closeout.json
- data/processed/phase17_backtest_results_review_quality_gate.json
- data/processed/phase17_historical_data_coverage_audit.json
- data/processed/phase17_historical_backtest_dataset_builder.json
- data/processed/phase17_final_strategy_candidate_review.json

## Output Evidence

data/processed/phase19_strategy_rework_historical_data_expansion_decision.json

## Runtime Decision

runtime/phase19_strategy_rework_historical_data_expansion_decision_state.json

## Decision File

data/processed/phase19_strategy_rework/strategy_rework_historical_data_expansion_decision.json

## Expected Decision

PHASE_19_STRATEGY_REWORK_AND_DATA_EXPANSION_DECISION_CREATED_NOT_APPROVED_FOR_EXECUTION

## Next Phase

Phase 19.2 — Historical Data Expansion Plan.
