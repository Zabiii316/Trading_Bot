from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any, Protocol
from uuid import uuid4

from .dead_letter import DeadLetterWriter
from .table_map import group_events_for_clickhouse, table_for_event


class EventSink(Protocol):
    name: str

    async def start(self) -> None: ...

    async def stop(self) -> None: ...

    async def write_events(self, events: list[Any]) -> Any: ...


@dataclass
class StorageCounters:
    accepted_events: int = 0
    written_events: int = 0
    failed_events: int = 0
    flush_count: int = 0
    dropped_events: int = 0
    last_flush_latency_ms: float = 0.0
    last_error: str | None = None


@dataclass(frozen=True)
class BatchPolicy:
    max_batch_rows: int = 5000
    max_linger_ms: int = 250
    max_queue_size: int = 250000
    fail_fast: bool = False


class BatchingStorageWriter:
    """Low-latency asynchronous event writer with bounded queue and timed flush.

    The writer keeps ingestion decoupled from database latency. It groups events
    by event table at flush time and writes them through the configured sink.
    """

    def __init__(
        self,
        sink: EventSink,
        *,
        policy: BatchPolicy | None = None,
        dead_letter: DeadLetterWriter | None = None,
    ) -> None:
        self.sink = sink
        self.policy = policy or BatchPolicy()
        self.dead_letter = dead_letter
        self.counters = StorageCounters()
        self._queue: asyncio.Queue[Any] = asyncio.Queue(maxsize=self.policy.max_queue_size)
        self._worker: asyncio.Task[None] | None = None
        self._stop_event = asyncio.Event()
        self._started = False

    async def start(self) -> None:
        if self._started:
            return
        await self.sink.start()
        self._stop_event.clear()
        self._worker = asyncio.create_task(self._run(), name="storage-writer")
        self._started = True

    async def stop(self) -> None:
        if not self._started:
            return
        self._stop_event.set()
        if self._worker is not None:
            await self._worker
            self._worker = None
        await self.sink.stop()
        self._started = False

    async def publish(self, event: Any) -> None:
        # Fail early if no table mapping exists.
        table_for_event(event)
        try:
            self._queue.put_nowait(event)
            self.counters.accepted_events += 1
        except asyncio.QueueFull:
            self.counters.dropped_events += 1
            error = RuntimeError("storage queue full")
            if self.dead_letter is not None:
                await self.dead_letter.write(event=event, error=error, context={"sink": self.sink.name})
            if self.policy.fail_fast:
                raise error

    async def flush_now(self) -> None:
        batch: list[Any] = []
        while not self._queue.empty() and len(batch) < self.policy.max_batch_rows:
            batch.append(self._queue.get_nowait())
        if batch:
            await self._flush(batch)

    async def _run(self) -> None:
        batch: list[Any] = []
        deadline = time.monotonic() + self.policy.max_linger_ms / 1000
        while not self._stop_event.is_set() or not self._queue.empty() or batch:
            timeout = max(0.0, deadline - time.monotonic())
            try:
                event = await asyncio.wait_for(self._queue.get(), timeout=timeout)
                batch.append(event)
                if len(batch) >= self.policy.max_batch_rows:
                    await self._flush(batch)
                    batch = []
                    deadline = time.monotonic() + self.policy.max_linger_ms / 1000
            except asyncio.TimeoutError:
                if batch:
                    await self._flush(batch)
                    batch = []
                deadline = time.monotonic() + self.policy.max_linger_ms / 1000

    async def _flush(self, events: list[Any]) -> None:
        batch_id = uuid4()
        start = time.perf_counter()
        try:
            await self.sink.write_events(events)
            self.counters.written_events += len(events)
            self.counters.flush_count += 1
            self.counters.last_flush_latency_ms = (time.perf_counter() - start) * 1000
            self.counters.last_error = None
        except Exception as exc:
            self.counters.failed_events += len(events)
            self.counters.last_error = str(exc)
            if self.dead_letter is not None:
                for event in events:
                    await self.dead_letter.write(
                        event=event,
                        error=exc,
                        context={"sink": self.sink.name, "batch_id": str(batch_id)},
                    )
            if self.policy.fail_fast:
                raise


class MemoryStorageSink:
    """Test sink that still exercises table grouping and storage interfaces."""

    def __init__(self) -> None:
        self.name = "memory"
        self.batches: list[tuple[str, list[dict[str, Any]]]] = []

    async def start(self) -> None:
        return None

    async def stop(self) -> None:
        return None

    async def write_events(self, events: list[Any]) -> list[tuple[str, int]]:
        written: list[tuple[str, int]] = []
        for batch in group_events_for_clickhouse(events):
            self.batches.append((batch.table_name, batch.rows))
            written.append((batch.table_name, len(batch.rows)))
        return written
