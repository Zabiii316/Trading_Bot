# Production Readiness Checklist

## Build and Release
- [ ] CI tests pass.
- [ ] Immutable commit SHA recorded.
- [ ] Immutable image tag recorded.
- [ ] Deployment manifest generated.
- [ ] Config hash recorded.

## Market Data
- [ ] WebSocket feeds healthy.
- [ ] Order-book sequence gaps are zero or below threshold.
- [ ] Rebuild/resync logic tested.
- [ ] Data freshness is within configured SLA.

## Strategy and Risk
- [ ] Risk engine healthy.
- [ ] Kill-switch tested.
- [ ] Exposure caps configured.
- [ ] Daily/weekly/drawdown limits configured.
- [ ] Position-sizing validation enabled.

## Execution
- [ ] Binance testnet order lifecycle tested.
- [ ] Partial fills tested.
- [ ] Cancel-all tested.
- [ ] Reduce-only close tested.
- [ ] Reconciliation healthy.

## Security
- [ ] Withdrawal permissions disabled.
- [ ] API keys IP-restricted where possible.
- [ ] Secrets loaded from managed source.
- [ ] Mainnet live flag disabled until final approval.

## Monitoring
- [ ] Prometheus scraping healthy.
- [ ] Grafana dashboards available.
- [ ] Alertmanager routing tested.
- [ ] Critical alerts are zero before rollout.

## Emergency Drills
- [ ] Cancel-all drill completed.
- [ ] Emergency-flatten drill completed.
- [ ] Reconciliation-rebuild drill completed.
- [ ] Service-restart drill completed.

## Approval
- [ ] Readiness report reviewed.
- [ ] Manual approval recorded.
- [ ] Approved capital allocation recorded.
- [ ] Rollback operator assigned.
