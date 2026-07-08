from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from time import time
from typing import Any


class HealthStatus(str, Enum):
    OK = "ok"
    DEGRADED = "degraded"
    DOWN = "down"


@dataclass(slots=True)
class ComponentHealth:
    name: str
    is_live: bool = True
    is_ready: bool = True
    last_heartbeat_ms: int = field(default_factory=lambda: int(time() * 1000))
    max_stale_ms: int = 10_000
    details: dict[str, Any] = field(default_factory=dict)

    def is_stale(self, now_ms: int | None = None) -> bool:
        now = now_ms or int(time() * 1000)
        return now - self.last_heartbeat_ms > self.max_stale_ms

    def status(self, now_ms: int | None = None) -> HealthStatus:
        if not self.is_live or self.is_stale(now_ms):
            return HealthStatus.DOWN
        if not self.is_ready:
            return HealthStatus.DEGRADED
        return HealthStatus.OK

    def as_dict(self, now_ms: int | None = None) -> dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status(now_ms).value,
            "is_live": self.is_live,
            "is_ready": self.is_ready,
            "last_heartbeat_ms": self.last_heartbeat_ms,
            "max_stale_ms": self.max_stale_ms,
            "is_stale": self.is_stale(now_ms),
            "details": self.details,
        }


class HealthRegistry:
    """Thread-light component-health registry.

    Services call heartbeat/update on each event loop tick or critical state transition.
    The monitoring API exposes aggregate liveness/readiness from this registry.
    """

    def __init__(self) -> None:
        self._components: dict[str, ComponentHealth] = {}

    def update(
        self,
        name: str,
        *,
        is_live: bool = True,
        is_ready: bool = True,
        heartbeat_ms: int | None = None,
        max_stale_ms: int = 10_000,
        details: dict[str, Any] | None = None,
    ) -> ComponentHealth:
        health = ComponentHealth(
            name=name,
            is_live=is_live,
            is_ready=is_ready,
            last_heartbeat_ms=heartbeat_ms or int(time() * 1000),
            max_stale_ms=max_stale_ms,
            details=details or {},
        )
        self._components[name] = health
        return health

    def heartbeat(self, name: str, heartbeat_ms: int | None = None) -> ComponentHealth:
        if name not in self._components:
            return self.update(name, heartbeat_ms=heartbeat_ms)
        component = self._components[name]
        component.last_heartbeat_ms = heartbeat_ms or int(time() * 1000)
        component.is_live = True
        return component

    def mark_down(self, name: str, reason: str) -> ComponentHealth:
        component = self._components.get(name) or self.update(name)
        component.is_live = False
        component.is_ready = False
        component.details = {**component.details, "reason": reason}
        return component

    def mark_not_ready(self, name: str, reason: str) -> ComponentHealth:
        component = self._components.get(name) or self.update(name)
        component.is_ready = False
        component.details = {**component.details, "reason": reason}
        return component

    def components(self) -> list[ComponentHealth]:
        return list(self._components.values())

    def overall_status(self, now_ms: int | None = None) -> HealthStatus:
        if not self._components:
            return HealthStatus.DOWN
        statuses = [component.status(now_ms) for component in self._components.values()]
        if any(status == HealthStatus.DOWN for status in statuses):
            return HealthStatus.DOWN
        if any(status == HealthStatus.DEGRADED for status in statuses):
            return HealthStatus.DEGRADED
        return HealthStatus.OK

    def is_live(self, now_ms: int | None = None) -> bool:
        return self.overall_status(now_ms) != HealthStatus.DOWN

    def is_ready(self, now_ms: int | None = None) -> bool:
        return self.overall_status(now_ms) == HealthStatus.OK

    def snapshot(self, now_ms: int | None = None) -> dict[str, Any]:
        now = now_ms or int(time() * 1000)
        return {
            "status": self.overall_status(now).value,
            "is_live": self.is_live(now),
            "is_ready": self.is_ready(now),
            "time_ms": now,
            "components": [component.as_dict(now) for component in self._components.values()],
        }
