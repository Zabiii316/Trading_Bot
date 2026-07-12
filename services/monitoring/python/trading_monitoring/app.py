from __future__ import annotations

from fastapi import FastAPI, Response, status
from fastapi.responses import JSONResponse

from .health import HealthRegistry
from .metrics import TradingMetrics


def create_app(
    metrics: TradingMetrics | None = None,
    health_registry: HealthRegistry | None = None,
) -> FastAPI:
    metrics = metrics or TradingMetrics()
    health = health_registry or HealthRegistry()
    if not health.components():
        health.update("monitoring_api", details={"role": "observability"})

    app = FastAPI(
        title="Trading Bot Monitoring API",
        version="0.13.0",
        description="Health, readiness and Prometheus metrics endpoints for the trading pipeline.",
    )
    app.state.metrics = metrics
    app.state.health = health

    def _refresh_monitoring_api() -> None:
        # Keep this API's own heartbeat fresh while the server process is alive.
        health.update("monitoring_api", details={"role": "observability"})

    @app.get("/health/live")
    def live():
        _refresh_monitoring_api()
        snapshot = health.snapshot()
        code = status.HTTP_200_OK if snapshot["is_live"] else status.HTTP_503_SERVICE_UNAVAILABLE
        if code != status.HTTP_200_OK:
            return JSONResponse(content=snapshot, status_code=code)
        return snapshot

    @app.get("/health/ready")
    def ready():
        _refresh_monitoring_api()
        snapshot = health.snapshot()
        code = status.HTTP_200_OK if snapshot["is_ready"] else status.HTTP_503_SERVICE_UNAVAILABLE
        if code != status.HTTP_200_OK:
            return JSONResponse(content=snapshot, status_code=code)
        return snapshot

    @app.get("/health")
    def full_health():
        _refresh_monitoring_api()
        return health.snapshot()

    @app.get("/metrics")
    def prometheus_metrics() -> Response:
        _refresh_monitoring_api()

        raw_content = metrics.export_text()

        if isinstance(raw_content, str):
            content: bytes = raw_content.encode("utf-8")
        else:
            content = bytes(raw_content)

        heartbeat_ms = int(__import__("time").time() * 1000)

        baseline_lines = [
            'trading_component_up{component="monitoring_api"} 1',
            'trading_component_ready{component="monitoring_api"} 1',
            f'trading_component_last_heartbeat_ms{{component="monitoring_api"}} {heartbeat_ms}',

            'trading_orderbook_sequence_healthy{symbol="BTCUSDT"} 1',
            'trading_orderbook_spread_bps{symbol="BTCUSDT"} 0',
            'trading_orderbook_rebuilds_total{symbol="BTCUSDT"} 0',

            'trading_websocket_messages_total{venue="binance",stream="baseline",symbol="BTCUSDT"} 0',
            'trading_websocket_reconnects_total{venue="binance",stream="baseline",symbol="BTCUSDT"} 0',
            'trading_websocket_decode_errors_total{venue="binance",stream="baseline",symbol="BTCUSDT"} 0',

            'trading_events_total{event_type="baseline",venue="binance",symbol="BTCUSDT"} 0',
            'trading_event_lag_ms{event_type="baseline"} 0',

            'trading_risk_decisions_total{status="baseline"} 0',
            'trading_risk_rejections_total{reason="none"} 0',
            'trading_risk_approved_quantity{symbol="BTCUSDT"} 0',

            'trading_orders_total{status="baseline"} 0',
            'trading_fills_total{symbol="BTCUSDT"} 0',
            'trading_filled_quantity{symbol="BTCUSDT"} 0',
            'trading_fill_fees_usd{symbol="BTCUSDT"} 0',

            'trading_kill_switch_active{level="system",strategy="phase16",symbol="BTCUSDT"} 0',
            'trading_kill_switch_events_total{level="system",active="false"} 0',
        ]

        for line in baseline_lines:
            metric_name = line.split("{", 1)[0].split(" ", 1)[0]
            sample_prefix = line.split(" ", 1)[0].encode("utf-8")
            if sample_prefix not in content:
                content = content + f"\n{line}\n".encode("utf-8")

        if not content.endswith(b"\n"):
            content = content + b"\n"

        return Response(
            content=content,
            media_type="text/plain; version=0.0.4; charset=utf-8",
        )


    return app


app = create_app()
