# Phase 23.27 — Capital Limit Approval Record

This phase records the hard risk and capital limits that will apply to
any later deployment approval process.

The recorded limits include:

- Micro trade notional
- Maximum single-order notional
- Maximum daily loss
- Maximum position size

Passing this phase validates and records the limits only.

It does not approve those limits for production use and does not enable
live execution.

## Expected State

capital_limit_approval_record_created=true
capital_limits_technically_valid=true
capital_limits_approved_for_next_review=true
capital_limits_approved_for_live_use=false
manual_owner_live_approval_present=false
production_execution_started=false
execution_allowed=false
approved_for_micro_live_execution=false
approved_for_real_live_trading=false
production_exchange_order_submission=false
real_capital_usage=false

## Expected Decision

PHASE_23_CAPITAL_LIMIT_APPROVAL_RECORD_CREATED_READY_FOR_MANUAL_OWNER_APPROVAL_RECORD_NOT_APPROVED_FOR_LIVE_EXECUTION

## Next Phase

Phase 23.28 — Manual Owner Approval Record.
