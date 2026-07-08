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
        return Response(content=metrics.export_text(), media_type=metrics.content_type)

    return app


app = create_app()
