from __future__ import annotations

import asyncio
import logging
from contextlib import suppress
from typing import Any

from .backoff import ExponentialBackoff
from .binance_mapper import UnsupportedBinancePayload, map_combined_stream_payload
from .config import RecorderConfig
from .health import RecorderHealth
from .publisher import EventPublisher, build_publisher
from .serialization import loads_json

logger = logging.getLogger(__name__)


class BinanceMarketDataRecorder:
    """High-throughput Binance public market-data recorder.

    Architecture:
    - One WebSocket reader task keeps the network read path lightweight.
    - Parsed JSON messages are pushed into a bounded queue.
    - N worker tasks normalize and publish events.
    - Reconnect uses exponential backoff and fail-safe logging.
    """

    def __init__(
        self,
        config: RecorderConfig,
        publisher: EventPublisher | None = None,
        worker_count: int = 2,
    ) -> None:
        self.config = config
        self.publisher = publisher or build_publisher(
            config.publisher,
            jsonl_path=config.jsonl_path,
            kafka_bootstrap_servers=config.kafka_bootstrap_servers,
            kafka_client_id=config.kafka_client_id,
        )
        self.worker_count = max(1, worker_count)
        self.queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=config.max_queue_size)
        self.health = RecorderHealth()
        self._stop = asyncio.Event()
        self._workers: list[asyncio.Task[None]] = []

    async def start(self) -> None:
        await self.publisher.start()
        self._workers = [asyncio.create_task(self._worker(i), name=f"md-worker-{i}") for i in range(self.worker_count)]
        try:
            await self._run_forever()
        finally:
            await self.stop()

    async def stop(self) -> None:
        self._stop.set()
        for task in self._workers:
            task.cancel()
        for task in self._workers:
            with suppress(asyncio.CancelledError):
                await task
        await self.publisher.stop()

    async def _run_forever(self) -> None:
        backoff = ExponentialBackoff(
            initial_delay_s=self.config.reconnect_initial_delay_s,
            max_delay_s=self.config.reconnect_max_delay_s,
            jitter_s=self.config.reconnect_jitter_s,
        )
        while not self._stop.is_set():
            try:
                await self._connect_and_read()
                backoff.reset()
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001 - top-level reconnect guard.
                self.health.on_disconnected()
                self.health.on_reconnect()
                delay = backoff.next_delay()
                logger.warning("Binance WS disconnected: %s. Reconnecting in %.2fs", exc, delay)
                await asyncio.sleep(delay)

    async def _connect_and_read(self) -> None:
        try:
            import websockets
        except ImportError as exc:  # pragma: no cover - optional runtime dependency.
            raise RuntimeError("Install websockets to run the Binance recorder") from exc

        url = self.config.combined_stream_url()
        logger.info("Connecting to Binance market-data stream: %s", url)
        async with websockets.connect(
            url,
            ping_interval=20,
            ping_timeout=20,
            max_queue=4096,
            close_timeout=5,
        ) as ws:
            self.health.on_connected()
            while not self._stop.is_set():
                try:
                    raw_message = await asyncio.wait_for(ws.recv(), timeout=self.config.websocket_read_timeout_s)
                except asyncio.TimeoutError as exc:
                    raise TimeoutError("No Binance WebSocket message received before read timeout") from exc
                self.health.on_message()
                try:
                    message = loads_json(raw_message)
                except Exception:  # noqa: BLE001
                    self.health.decode_errors += 1
                    logger.exception("Failed to decode Binance WS message")
                    continue
                await self.queue.put(message)

    async def _worker(self, worker_id: int) -> None:
        while not self._stop.is_set():
            message = await self.queue.get()
            try:
                event = map_combined_stream_payload(
                    message,
                    source=self.config.source,
                    venue=self.config.venue_value,
                    market_type=self.config.market_type_value,
                    include_raw=self.config.enable_raw_payload,
                )
                await self.publisher.publish(event)
                self.health.on_event(str(event.event_type), int(event.event_time_ms))
            except UnsupportedBinancePayload:
                self.health.mapping_errors += 1
                logger.debug("Unsupported Binance message skipped: %s", message)
            except Exception:  # noqa: BLE001
                self.health.publish_errors += 1
                logger.exception("Failed to normalize or publish Binance message in worker %s", worker_id)
            finally:
                self.queue.task_done()
