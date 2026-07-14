# Phase 18.1 — Next Action Selection

This phase selects the next path after Phase 17 safety closeout.

This phase does not approve:

- Paper shadow execution start
- Real live trading
- Micro-live execution
- Production Binance order submission
- Production API-key usage
- Real capital usage

## Valid Options

- remain_on_hold
- paper_shadow_approval_path
- strategy_rework_path
- expand_historical_data_path
- monitoring_dashboard_review

## Inputs

- data/processed/phase17_safety_closeout_next_action_options.json
- runtime/phase17_safety_closeout_state.json

## Output Evidence

data/processed/phase18_next_action_selection.json

## Runtime State

runtime/phase18_next_action_selection_state.json

## Expected Decision

PHASE_18_NEXT_ACTION_SELECTED_REMAIN_ON_HOLD_NOT_APPROVED_FOR_EXECUTION

## Next Phase

Phase 18.2 — Hold State Monitoring Plan.
