#!/usr/bin/env python3
from __future__ import annotations

import os

import uvicorn

from trading_monitoring.app import create_app
from trading_monitoring.health import HealthRegistry
from trading_monitoring.metrics import TradingMetrics


def main() -> None:
    metrics = TradingMetrics()
    health = HealthRegistry()
    for component in os.getenv(
        "MONITORING_COMPONENTS",
        "monitoring_api,market_data,order_book,features,liquidity,sweep,avwap,signals,risk,paper_execution",
    ).split(","):
        name = component.strip()
        if name:
            health.update(name, details={"source": "bootstrap"})
    app = create_app(metrics=metrics, health_registry=health)
    uvicorn.run(app, host=os.getenv("MONITORING_HOST", "0.0.0.0"), port=int(os.getenv("MONITORING_PORT", "8080")))


if __name__ == "__main__":
    main()
