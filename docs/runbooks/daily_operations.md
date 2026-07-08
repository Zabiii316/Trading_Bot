# Runbook — Daily Operations

## Start of Day

- Verify all services are healthy.
- Confirm no stale components.
- Confirm no open critical alerts.
- Confirm order-book sequencing is healthy.
- Confirm risk limits and capital allocation match current stage.
- Confirm exchange account state reconciles with internal state.

## During Trading

- Monitor spread, sequence gaps, latency, slippage, risk rejections, and reconciliation.
- Pause strategy on abnormal slippage or repeated false sweeps.
- Do not manually override risk rejections.

## End of Day

- Export order, fill, signal, risk, and PnL reports.
- Record drawdown, slippage, and execution integrity metrics.
- Archive manifest, readiness report, and operator notes.
- Rotate or verify credentials according to security policy.
