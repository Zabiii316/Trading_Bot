from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from trading_contracts.events import EVENT_MODEL_REGISTRY
from trading_market_data.serialization import loads_json
from trading_storage.clickhouse import ClickHouseEventSink, ClickHouseHttpClient
from trading_storage.config import ClickHouseConfig, StorageWriterConfig
from trading_storage.dead_letter import DeadLetterWriter
from trading_storage.writer import BatchPolicy, BatchingStorageWriter, MemoryStorageSink


def event_from_json(line: str):
    payload = loads_json(line)
    event_type = payload.get("event_type")
    for model in EVENT_MODEL_REGISTRY.values():
        try:
            if model.model_fields["event_type"].default.value == event_type:
                return model.model_validate(payload)
        except Exception:
            continue
    raise ValueError(f"Unsupported event_type: {event_type}")


def build_sink(kind: str):
    normalized = kind.strip().lower()
    if normalized == "memory":
        return MemoryStorageSink()
    if normalized == "clickhouse":
        return ClickHouseEventSink(ClickHouseHttpClient(ClickHouseConfig.from_env()))
    raise ValueError(f"Unsupported storage sink: {kind}")


async def main() -> None:
    parser = argparse.ArgumentParser(description="Persist JSONL events into the configured storage sink")
    parser.add_argument("--input", required=True, help="JSONL event file from recorder/reconstructor")
    parser.add_argument("--sink", default=None, help="memory or clickhouse")
    args = parser.parse_args()

    config = StorageWriterConfig.from_env()
    sink = build_sink(args.sink or config.sink)
    writer = BatchingStorageWriter(
        sink,
        policy=BatchPolicy(
            max_batch_rows=config.max_batch_rows,
            max_linger_ms=config.max_linger_ms,
            max_queue_size=config.max_queue_size,
            fail_fast=config.fail_fast,
        ),
        dead_letter=DeadLetterWriter(config.dead_letter_path),
    )
    await writer.start()
    try:
        with Path(args.input).open("r", encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    await writer.publish(event_from_json(line))
        await writer.flush_now()
    finally:
        await writer.stop()
    print(writer.counters)


if __name__ == "__main__":
    asyncio.run(main())
