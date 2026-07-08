from fastapi.testclient import TestClient

from trading_monitoring.app import create_app
from trading_monitoring.health import HealthRegistry
from trading_monitoring.metrics import TradingMetrics


def test_monitoring_app_health_and_metrics_endpoints():
    health = HealthRegistry()
    health.update("monitoring_api", max_stale_ms=10_000_000_000)
    metrics = TradingMetrics()
    metrics.observe_component("monitoring_api", True, True, heartbeat_ms=10_000)
    app = create_app(metrics=metrics, health_registry=health)
    client = TestClient(app)

    live = client.get("/health/live")
    ready = client.get("/health/ready")
    metrics_response = client.get("/metrics")

    assert live.status_code == 200
    assert ready.status_code == 200
    assert live.json()["status"] == "ok"
    assert "trading_component_up" in metrics_response.text


def test_monitoring_app_ready_fails_when_component_not_ready():
    health = HealthRegistry()
    health.update("risk", is_ready=False, max_stale_ms=10_000_000_000)
    app = create_app(metrics=TradingMetrics(), health_registry=health)
    client = TestClient(app)

    response = client.get("/health/ready")

    assert response.status_code == 503
    assert response.json()["status"] == "degraded"
