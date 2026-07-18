# Phase 20.6 — Strategy Quality Gate V2 Design

This phase creates Strategy Quality Gate V2 for future reworked strategy research.

Gate V2 checks:

- Positive net return after fees and slippage
- Profit factor above 1.0
- Improved drawdown versus Phase 17 baseline
- Passes both BTCUSDT and ETHUSDT
- Does not depend on one symbol
- Has enough trades per symbol
- Includes fee/slippage sensitivity
- Does not request execution approval

This phase does not approve:

- Backtest execution
- Paper shadow execution start
- Real live trading
- Micro-live execution
- Production Binance order submission
- Production API-key usage
- Real capital usage

## Output Evidence

data/processed/phase20_strategy_quality_gate_v2_design.json

## Runtime Record

runtime/phase20_strategy_quality_gate_v2_design_state.json

## Record File

data/processed/phase20_strategy_rework/strategy_quality_gate_v2_design.json

## Expected Decision

PHASE_20_STRATEGY_QUALITY_GATE_V2_DESIGNED_RESEARCH_ONLY_NOT_APPROVED_FOR_EXECUTION

## Next Phase

Phase 20.7 — Candidate Rejection Rules Design.
