# Phase 20.7 — Candidate Rejection Rules Design

This phase creates Candidate Rejection Rules V2 for future strategy research results.

Reject candidates for:

- Negative net return after fees/slippage
- Profit factor at or below 1.0
- Drawdown not improved versus Phase 17
- Single-symbol dependency
- Low trade count
- Fee/slippage sensitivity failure
- Missing required metrics
- Missing symbol-level results
- Parameter overfitting
- Any execution approval flag being true

This phase does not approve:

- Backtest execution
- Paper shadow execution start
- Real live trading
- Micro-live execution
- Production Binance order submission
- Production API-key usage
- Real capital usage

## Output Evidence

data/processed/phase20_candidate_rejection_rules_design.json

## Runtime Record

runtime/phase20_candidate_rejection_rules_design_state.json

## Record File

data/processed/phase20_strategy_rework/candidate_rejection_rules_design.json

## Expected Decision

PHASE_20_CANDIDATE_REJECTION_RULES_DESIGNED_RESEARCH_ONLY_NOT_APPROVED_FOR_EXECUTION

## Next Phase

Phase 20.8 — Offline Reworked Strategy Runner Design.
