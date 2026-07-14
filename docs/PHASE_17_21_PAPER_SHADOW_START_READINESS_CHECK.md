# Phase 17.21 — Paper Shadow Start Readiness Check

This phase checks whether the paper shadow system is ready to start.

This phase does not approve:

- Paper shadow start
- Real live trading
- Micro-live execution
- Production Binance order submission
- Production API-key usage
- Real capital usage

## Inputs

- data/processed/phase17_paper_shadow_execution_harness.json
- runtime/phase17_paper_shadow_state.json
- data/processed/phase17_paper_shadow_start_gate.json
- runtime/phase17_paper_shadow_start_gate.json
- data/processed/phase17_paper_shadow_manual_approval_record.json
- runtime/phase17_paper_shadow_manual_approval_record.json

## Output Evidence

data/processed/phase17_paper_shadow_start_readiness_check.json

## Runtime Readiness File

runtime/phase17_paper_shadow_start_readiness_check.json

## Expected Decision

PAPER_SHADOW_START_READINESS_CHECK_FAILED_MANUAL_APPROVAL_REQUIRED_NOT_STARTED

or

PAPER_SHADOW_START_READINESS_CHECK_PASSED_MANUAL_START_ACTION_REQUIRED_NOT_STARTED

or

PAPER_SHADOW_START_READINESS_CHECK_SKIPPED_NO_HARNESS_SESSIONS_STRATEGY_REWORK_REQUIRED

## Next Phase

Phase 17.22 — Paper Shadow Safe Start Stub.
