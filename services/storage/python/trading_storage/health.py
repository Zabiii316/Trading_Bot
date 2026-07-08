from __future__ import annotations

from dataclasses import dataclass, field
from time import time
from typing import Any
from uuid import uuid4

from .serialization import ms_to_ch_datetime64, json_dumps_str


@dataclass(frozen=True)
class SystemHealthEvent:
    event_id: str
    component: str
    status: str
    severity: str
    event_time_ms: int
    symbol: str | None = None
    counters: dict[str, Any] = field(default_factory=dict)
    message: str = ""

    @classmethod
    def now(
        cls,
        *,
        component: str,
        status: str,
        severity: str = "info",
        symbol: str | None = None,
        counters: dict[str, Any] | None = None,
        message: str = "",
    ) -> "SystemHealthEvent":
        return cls(
            event_id=str(uuid4()),
            component=component,
            status=status,
            severity=severity,
            event_time_ms=int(time() * 1000),
            symbol=symbol,
            counters=counters or {},
            message=message,
        )


def health_row(event: SystemHealthEvent) -> dict[str, Any]:
    return {
        "event_id": event.event_id,
        "component": event.component,
        "status": event.status,
        "severity": event.severity,
        "event_time": ms_to_ch_datetime64(event.event_time_ms),
        "event_time_ms": event.event_time_ms,
        "symbol": event.symbol,
        "counters_json": json_dumps_str(event.counters),
        "message": event.message,
    }
