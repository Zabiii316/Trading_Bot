from __future__ import annotations

from dataclasses import dataclass, field
from typing import DefaultDict
from collections import defaultdict

from .clock import now_ms


@dataclass
class RecorderHealth:
    started_at_ms: int = field(default_factory=now_ms)
    connected: bool = False
    reconnect_count: int = 0
    messages_received: int = 0
    events_published: int = 0
    decode_errors: int = 0
    mapping_errors: int = 0
    publish_errors: int = 0
    last_message_ms: int | None = None
    last_event_time_ms: int | None = None
    counts_by_event_type: DefaultDict[str, int] = field(default_factory=lambda: defaultdict(int))

    def on_connected(self) -> None:
        self.connected = True

    def on_disconnected(self) -> None:
        self.connected = False

    def on_reconnect(self) -> None:
        self.reconnect_count += 1

    def on_message(self) -> None:
        self.messages_received += 1
        self.last_message_ms = now_ms()

    def on_event(self, event_type: str, event_time_ms: int) -> None:
        self.events_published += 1
        self.last_event_time_ms = event_time_ms
        self.counts_by_event_type[event_type] += 1

    def snapshot(self) -> dict[str, object]:
        return {
            "started_at_ms": self.started_at_ms,
            "connected": self.connected,
            "reconnect_count": self.reconnect_count,
            "messages_received": self.messages_received,
            "events_published": self.events_published,
            "decode_errors": self.decode_errors,
            "mapping_errors": self.mapping_errors,
            "publish_errors": self.publish_errors,
            "last_message_ms": self.last_message_ms,
            "last_event_time_ms": self.last_event_time_ms,
            "counts_by_event_type": dict(self.counts_by_event_type),
        }
