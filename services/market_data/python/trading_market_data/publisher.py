from __future__ import annotations

import abc
import asyncio
from pathlib import Path
from typing import Any

from .serialization import dumps_json_bytes
from .topics import topic_for_event


class EventPublisher(abc.ABC):
    @abc.abstractmethod
    async def start(self) -> None: ...

    @abc.abstractmethod
    async def publish(self, event: Any) -> None: ...

    @abc.abstractmethod
    async def stop(self) -> None: ...


class StdoutPublisher(EventPublisher):
    async def start(self) -> None:
        return None

    async def publish(self, event: Any) -> None:
        print(dumps_json_bytes(event).decode("utf-8"), flush=False)

    async def stop(self) -> None:
        return None


class JsonlPublisher(EventPublisher):
    """Append normalized events to JSONL.

    This is useful for local development and deterministic replay before Redpanda is
    introduced. Writes are protected by an asyncio lock so multiple workers can share
    the same publisher safely.
    """

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._file = None
        self._lock = asyncio.Lock()

    async def start(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._file = self.path.open("ab")

    async def publish(self, event: Any) -> None:
        if self._file is None:
            raise RuntimeError("JsonlPublisher.start() must be called before publish()")
        payload = dumps_json_bytes(event) + b"\n"
        async with self._lock:
            self._file.write(payload)
            self._file.flush()

    async def stop(self) -> None:
        if self._file is not None:
            self._file.close()
            self._file = None


class MemoryPublisher(EventPublisher):
    def __init__(self) -> None:
        self.events: list[Any] = []

    async def start(self) -> None:
        return None

    async def publish(self, event: Any) -> None:
        self.events.append(event)

    async def stop(self) -> None:
        return None


class RedpandaPublisher(EventPublisher):
    """Kafka-compatible publisher for Redpanda/Kafka.

    aiokafka is optional to keep unit tests lightweight. Install the `streaming`
    extra before using this publisher.
    """

    def __init__(self, bootstrap_servers: str, client_id: str) -> None:
        self.bootstrap_servers = bootstrap_servers
        self.client_id = client_id
        self._producer = None

    async def start(self) -> None:
        try:
            from aiokafka import AIOKafkaProducer
        except ImportError as exc:  # pragma: no cover - optional dependency.
            raise RuntimeError("Install aiokafka to use RedpandaPublisher") from exc
        self._producer = AIOKafkaProducer(
            bootstrap_servers=self.bootstrap_servers,
            client_id=self.client_id,
            acks="all",
            enable_idempotence=True,
            linger_ms=5,
            compression_type="zstd",
            value_serializer=lambda value: dumps_json_bytes(value),
        )
        await self._producer.start()

    async def publish(self, event: Any) -> None:
        if self._producer is None:
            raise RuntimeError("RedpandaPublisher.start() must be called before publish()")
        topic = topic_for_event(event.event_type, event.symbol)
        key = str(event.symbol).encode("utf-8")
        await self._producer.send_and_wait(topic, key=key, value=event)

    async def stop(self) -> None:
        if self._producer is not None:
            await self._producer.stop()
            self._producer = None


def build_publisher(kind: str, *, jsonl_path: str, kafka_bootstrap_servers: str, kafka_client_id: str) -> EventPublisher:
    normalized = kind.lower().strip()
    if normalized == "stdout":
        return StdoutPublisher()
    if normalized == "jsonl":
        return JsonlPublisher(jsonl_path)
    if normalized == "memory":
        return MemoryPublisher()
    if normalized in {"redpanda", "kafka"}:
        return RedpandaPublisher(kafka_bootstrap_servers, kafka_client_id)
    raise ValueError(f"Unsupported publisher kind: {kind}")
