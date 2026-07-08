from trading_monitoring.health import HealthRegistry, HealthStatus


def test_health_registry_reports_ready_when_components_ok():
    registry = HealthRegistry()
    registry.update("market_data", heartbeat_ms=1_000, max_stale_ms=5_000)
    registry.update("risk", heartbeat_ms=1_000, max_stale_ms=5_000)

    snapshot = registry.snapshot(now_ms=2_000)

    assert snapshot["status"] == HealthStatus.OK.value
    assert snapshot["is_ready"] is True
    assert len(snapshot["components"]) == 2


def test_health_registry_fails_closed_on_stale_component():
    registry = HealthRegistry()
    registry.update("order_book", heartbeat_ms=1_000, max_stale_ms=100)

    snapshot = registry.snapshot(now_ms=2_000)

    assert snapshot["status"] == HealthStatus.DOWN.value
    assert snapshot["is_live"] is False
    assert snapshot["components"][0]["is_stale"] is True


def test_mark_not_ready_degrades_without_downing_component():
    registry = HealthRegistry()
    registry.update("signals", heartbeat_ms=10_000, max_stale_ms=10_000)
    registry.mark_not_ready("signals", "warming_up")

    snapshot = registry.snapshot(now_ms=10_500)

    assert snapshot["status"] == HealthStatus.DEGRADED.value
    assert snapshot["is_live"] is True
    assert snapshot["is_ready"] is False
