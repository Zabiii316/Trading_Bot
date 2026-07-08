# Phase 4 — Raw Data Storage

## Objective

Persist replay-ready market data and operational events with strict schema consistency and high-throughput write paths.

## Storage split

| Store | Responsibility |
|---|---|
| ClickHouse | High-volume immutable market data, depth updates, snapshots, reconstructed books, health event history |
| PostgreSQL | Transactional audit state, replay manifests, latest health state |
| JSONL dead letter | Failed event writes for manual repair/replay |

## ClickHouse design

The DDL in `infra/clickhouse/init/001_market_data.sql` uses MergeTree tables partitioned by month and sorted by venue, market, symbol, timestamp, and sequence/update identifier. This supports efficient replay ranges and symbol-specific feature research.

Tables:

- `raw_trades`
- `raw_depth_updates`
- `raw_order_book_snapshots`
- `reconstructed_books`
- `system_health_events`

Depth levels are stored as compact JSON strings in raw tables to preserve exact replay input. Computed top-of-book and depth features are stored as typed numeric columns where fast filtering is needed.

## PostgreSQL design

The DDL in `infra/postgres/init/001_audit_state.sql` stores:

- `storage_write_audit`
- `event_replay_manifest`
- `system_health_state`

PostgreSQL is intentionally kept low-volume and transactional. It should not receive every depth update in production.

## Writer architecture

`BatchingStorageWriter` decouples ingestion from database write latency using:

- bounded async queue
- max batch rows
- max linger interval
- dead-letter output
- fail-fast option for test/staging

Supported sink implementations:

- `MemoryStorageSink` for tests
- `ClickHouseEventSink` via HTTP JSONEachRow
- `PostgresAuditSink` for operational state/audit workflows

## Replay readiness

Every event row keeps:

- event ID
- schema version
- source
- venue
- market type
- symbol
- exchange event timestamp
- local received timestamp
- trace ID
- exchange update/trade identifiers where available

For order book replay, use:

1. `raw_order_book_snapshots`
2. `raw_depth_updates`
3. `reconstructed_books` for verification only

Reconstructed books should not be used as a substitute for raw depth replay when validating sequencing logic.

## Run locally

```bash
pip install -e '.[dev,storage]'
docker compose up -d postgres clickhouse
python scripts/run_clickhouse_migrations.py
python scripts/run_storage_writer.py --input examples/order_book/depth_replay.jsonl --sink memory
```

For real ClickHouse persistence:

```bash
STORAGE_SINK=clickhouse python scripts/run_storage_writer.py --input data/raw/binance_market_data.jsonl
```

## Failure policy

- Unsupported event type: reject immediately.
- Queue overflow: dead-letter event and optionally fail fast.
- Database write failure: dead-letter every event in the failed batch.
- Storage services must never place orders; they are persistence-only.
