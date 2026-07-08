# Phase 13 — Monitoring Dashboards and Observability

## Purpose

Phase 13 adds a production-style observability layer for the trading-bot pipeline. It exposes Prometheus metrics, health/readiness endpoints, Grafana dashboard templates, Prometheus alert rules, Alertmanager routing, and kill-switch telemetry.

The objective is to make the system operationally measurable before live execution is introduced.

## Components

```text
services/monitoring/python/trading_monitoring/
  metrics.py      Prometheus metric facade
  health.py       Component liveness/readiness registry
  app.py          FastAPI /health and /metrics API
  alerts.py       Prometheus alert-rule loader/validator
  dashboard.py    Grafana dashboard loader/validator
```

## Metrics categories

### Pipeline events

- `trading_events_total`
- `trading_event_lag_ms`

### Component health

- `trading_component_up`
- `trading_component_ready`
- `trading_component_last_heartbeat_ms`

### WebSocket health

- `trading_websocket_messages_total`
- `trading_websocket_reconnects_total`
- `trading_websocket_decode_errors_total`

### Order-book health

- `trading_orderbook_sequence_healthy`
- `trading_orderbook_spread_bps`
- `trading_orderbook_rebuilds_total`

### Strategy health

- `trading_orderflow_delta`
- `trading_orderflow_cvd`
- `trading_orderflow_queue_imbalance_l1`
- `trading_orderflow_absorption_ratio`
- `trading_liquidity_level_quality`
- `trading_liquidity_sweeps_total`
- `trading_avwap_confirmation_score`
- `trading_signal_final_score`

### Risk and execution

- `trading_risk_decisions_total`
- `trading_risk_rejections_total`
- `trading_risk_approved_quantity`
- `trading_account_equity_quote`
- `trading_execution_orders_total`
- `trading_execution_fills_total`
- `trading_execution_filled_quantity_total`
- `trading_execution_fill_fee_amount_total`

### Kill-switch observability

- `trading_kill_switch_active`
- `trading_kill_switch_events_total`

## Health endpoints

The monitoring API exposes:

```text
GET /health/live
GET /health/ready
GET /health
GET /metrics
```

Readiness is fail-closed: stale or down components prevent a ready response.

## Grafana dashboards

Three dashboard templates are included:

```text
infra/grafana/dashboards/market_data_health.json
infra/grafana/dashboards/strategy_health.json
infra/grafana/dashboards/execution_risk.json
```

They cover:

1. Market-data and order-book health
2. Strategy and signal health
3. Risk, execution, and kill-switch state

## Alerts

Prometheus alert rules are defined in:

```text
infra/prometheus/rules/trading_bot_alerts.yml
```

Included alerts:

- `TradingComponentDown`
- `TradingComponentNotReady`
- `OrderBookSequenceUnhealthy`
- `OrderBookSpreadTooWide`
- `WebSocketReconnectSpike`
- `RiskRejectionSpike`
- `KillSwitchActive`
- `EmergencyFlattenActive`
- `EventLagHigh`

## Running locally

```bash
docker compose up monitoring-api prometheus alertmanager grafana
```

Open:

```text
Monitoring API: http://localhost:8080/health
Prometheus:     http://localhost:9090
Alertmanager:   http://localhost:9093
Grafana:        http://localhost:3000
```

Default Grafana credentials are controlled by `.env.example`:

```text
GRAFANA_ADMIN_USER=admin
GRAFANA_ADMIN_PASSWORD=admin
```

## Benchmark

```bash
PYTHONPATH=libs/python:services/monitoring/python python scripts/benchmark_monitoring_metrics.py
```

Local result in the build environment:

```text
50,000 metric observations
7.351 microseconds per observation
```

## Design constraints

- Bounded metric label sets to avoid high-cardinality Prometheus blowups.
- No exchange keys required.
- Monitoring can run independently from live execution.
- Kill-switch state is surfaced as a first-class metric.
- Health state is explicit and fail-closed.
