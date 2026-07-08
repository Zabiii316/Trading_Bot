# Runbook — Testnet to Live Transition

## Preconditions

- Latest image tag is built from an immutable commit SHA.
- All tests pass in CI.
- Binance testnet order lifecycle has been validated.
- Paper execution has reached the required trade count.
- Emergency drills are completed and documented.
- API key has no withdrawal permission.
- Mainnet live trading flag is disabled until final approval.

## Procedure

1. Freeze configuration and generate a config hash.
2. Generate a deployment manifest.
3. Run production-readiness check with latest operational snapshot.
4. Review every warning and blocking gate.
5. Confirm manual approval from the responsible operator.
6. Enable `BINANCE_ENABLE_LIVE_TRADING=true` only for `micro_live` or higher.
7. Deploy using the immutable image tag.
8. Watch market-data, risk, execution, and reconciliation dashboards.
9. Submit no more than the approved allocation.
10. Keep operator supervision active throughout the first live window.

## Rollback

- Disable live trading flag.
- Trigger hard trading halt.
- Cancel all open orders.
- Reconcile internal and exchange state.
- Flatten exposure only if required and only via reduce-only orders.
- Preserve all logs, events, manifests, and alert evidence.
