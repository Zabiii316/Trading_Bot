# Phase 15 — Controlled Live Deployment

This phase finalizes the operational framework required before the trading bot is allowed to move from testnet, paper execution, and shadow validation into a live Binance USD-M deployment.

## Objectives

- Define deployment runbooks and operator responsibilities.
- Enforce testnet-to-live transition gates.
- Apply staged capital allocation controls.
- Validate emergency response drills before mainnet exposure.
- Provide a machine-readable production-readiness checker.
- Ensure the live adapter remains fail-closed unless every critical gate passes.

## Deployment Stages

| Stage | Purpose | Capital | Live Trading |
|---|---:|---:|---:|
| `testnet_shadow` | Signals and risk decisions only | 0% | No |
| `testnet_paper` | Paper orders against live books | 0% | No |
| `testnet_execution` | Signed testnet order lifecycle | 0% | No |
| `micro_live` | Mainnet micro allocation | <= 1% | Yes |
| `pilot_live` | Small monitored allocation | <= 3% | Yes |
| `controlled_live` | Controlled production allocation | <= 10% | Yes |

## Live Transition Rules

The system must not enter a live stage unless:

1. CI test suite passes.
2. Risk engine is healthy.
3. Monitoring and alerting are healthy.
4. Order-book sequencing is healthy.
5. Reconciliation is healthy.
6. Kill-switch tests have been completed.
7. Emergency drills have been completed.
8. No open critical alerts exist.
9. No stale services exist.
10. API withdrawal permissions are disabled.
11. Secrets are loaded from a managed secret source.
12. Live trading is explicitly enabled only for live stages.
13. Manual approval is recorded.

## Capital Controls

The deployment validator enforces the more conservative of the global account cap and the current rollout-stage cap. If requested allocation exceeds the allowed stage allocation, the request is reduced and the report returns `approve_with_limits` rather than silently accepting the larger request.

## Emergency Drills

Required drills:

- `cancel_all`: cancel all open orders.
- `emergency_flatten`: close open exposure using reduce-only orders.
- `reconciliation_rebuild`: rebuild exchange-vs-internal state.
- `service_restart`: restart critical services and verify recovery.

Each drill should record evidence references and latency. A drill latency above the target threshold generates a warning.

## Readiness CLI

```bash
python scripts/run_production_readiness_check.py       --snapshot examples/deployment/readiness_pass_snapshot.json       --capital examples/deployment/capital_controls.json       --output artifacts/readiness_report.json
```

The command exits with status code `0` only when there are no blocking failures.

## Design Principle

Phase 15 does not attempt to guarantee profitability or eliminate all operational risk. It ensures the system fails closed, uses explicit approval gates, limits initial capital exposure, and provides auditable evidence before live trading is enabled.
