# Runbook — Emergency Response

## Emergency Levels

### Soft Strategy Suspension
Stops new signals for the affected strategy but does not cancel all orders.

### Hard Trading Halt
Stops new orders and cancels all open orders.

### Emergency Flatten
Cancels all open orders and closes live exposure using reduce-only orders.

## Immediate Actions

1. Identify trigger source: risk, execution, market data, reconciliation, or manual operator action.
2. Verify kill-switch level in Redis/PostgreSQL and dashboard.
3. For hard halt, execute `cancel_all` and confirm exchange open orders are zero.
4. For emergency flatten, submit reduce-only close orders and confirm position size is zero.
5. Start reconciliation rebuild.
6. Disable live trading until root cause is documented.

## Evidence to Capture

- Timestamp of trigger.
- Active orders before and after intervention.
- Position snapshot before and after intervention.
- Risk decision events.
- Execution order/fill events.
- Exchange query responses.
- Operator notes.

## Re-enable Criteria

Re-enable is prohibited until all blocking gates pass again and manual approval is recorded.
