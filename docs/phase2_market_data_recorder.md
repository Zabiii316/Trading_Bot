# Phase 2 — Binance Market-Data Recorder

## Objective

The recorder ingests Binance public WebSocket market data at high throughput, normalizes raw exchange payloads into the Phase 1 event contracts, and publishes immutable events to either JSONL or a Kafka-compatible bus such as Redpanda.

## Stream coverage

Default V1 streams per symbol:

```text
aggTrade
trade
depth@100ms
bookTicker
```

The recorder is intentionally public-data only. Trading keys are not needed in this phase.

## Runtime flow

```text
Binance combined WebSocket
        │
        ▼
JSON decode with orjson fallback
        │
        ▼
Bounded asyncio queue
        │
        ▼
Worker pool
        │
        ▼
Pydantic event normalization and validation
        │
        ▼
Publisher abstraction
        │
        ├── JSONL for local replay
        ├── stdout for debugging
        └── Redpanda/Kafka for production streaming
```

## Reconnection and safety

The recorder includes:

- Exponential reconnect backoff
- Configurable read timeout
- Bounded internal queue to prevent uncontrolled memory growth
- Decode, mapping, and publish error counters
- Health snapshot object for later monitoring integration
- Fail-safe shutdown handling through SIGINT/SIGTERM in the runner script

## Redpanda publishing

Install the streaming extra and run Redpanda:

```bash
pip install -e '.[dev,streaming]'
docker compose up -d redpanda
PUBLISHER=redpanda python scripts/run_binance_recorder.py
```

## Local JSONL publishing

```bash
pip install -e '.[dev]'
python scripts/run_binance_recorder.py
```

The default output path is:

```text
data/raw/binance_market_data.jsonl
```

## Design constraints

- CCXT is not used for live WebSocket ingestion.
- Native Binance stream fields are mapped directly into normalized contracts.
- Raw payloads can be retained for audit and replay.
- Execution is not implemented in Phase 2.
- Local order-book reconstruction is Phase 3; this phase records depth updates faithfully.
