CREATE TABLE IF NOT EXISTS execution_orders
(
    event_time DateTime64(3, 'UTC'),
    event_time_ms UInt64,
    received_time_ms UInt64,
    event_id UUID,
    trace_id UUID,
    schema_version LowCardinality(String),
    source LowCardinality(String),
    venue LowCardinality(String),
    market_type LowCardinality(String),
    symbol LowCardinality(String),
    order_id UUID,
    client_order_id String,
    signal_id UUID,
    risk_snapshot_id UUID,
    side LowCardinality(String),
    order_type LowCardinality(String),
    time_in_force LowCardinality(String),
    status LowCardinality(String),
    quantity Decimal(38, 18),
    limit_price Nullable(Decimal(38, 18)),
    stop_price Nullable(Decimal(38, 18)),
    reduce_only UInt8,
    venue_order_id Nullable(String)
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(event_time)
ORDER BY (symbol, event_time, order_id, status)
TTL toDateTime(event_time) + INTERVAL 365 DAY;

CREATE TABLE IF NOT EXISTS execution_fills
(
    event_time DateTime64(3, 'UTC'),
    event_time_ms UInt64,
    received_time_ms UInt64,
    event_id UUID,
    trace_id UUID,
    schema_version LowCardinality(String),
    source LowCardinality(String),
    venue LowCardinality(String),
    market_type LowCardinality(String),
    symbol LowCardinality(String),
    fill_id UUID,
    order_id UUID,
    client_order_id String,
    venue_order_id Nullable(String),
    side LowCardinality(String),
    fill_price Decimal(38, 18),
    fill_quantity Decimal(38, 18),
    fee_asset Nullable(String),
    fee_amount Decimal(38, 18),
    is_maker Nullable(UInt8),
    liquidity_tag Nullable(String)
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(event_time)
ORDER BY (symbol, event_time, order_id, fill_id)
TTL toDateTime(event_time) + INTERVAL 365 DAY;
