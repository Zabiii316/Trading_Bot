CREATE TABLE IF NOT EXISTS risk_decisions
(
    event_id String,
    schema_version UInt16,
    source LowCardinality(String),
    venue LowCardinality(String),
    market_type LowCardinality(String),
    symbol LowCardinality(String),
    event_time DateTime64(3, 'UTC'),
    event_time_ms UInt64,
    received_time_ms UInt64,
    trace_id String,
    risk_snapshot_id String,
    signal_id String,
    status LowCardinality(String),
    approved_quantity Decimal(38, 18),
    max_loss_quote Decimal(38, 18),
    account_equity_quote Decimal(38, 18),
    risk_fraction Decimal(18, 10),
    rejection_reasons_json String
)
ENGINE = MergeTree
ORDER BY (symbol, event_time_ms, risk_snapshot_id);

CREATE TABLE IF NOT EXISTS kill_switch_events
(
    event_id String,
    schema_version UInt16,
    source LowCardinality(String),
    venue LowCardinality(String),
    market_type LowCardinality(String),
    symbol LowCardinality(String),
    event_time DateTime64(3, 'UTC'),
    event_time_ms UInt64,
    received_time_ms UInt64,
    trace_id String,
    level LowCardinality(String),
    is_active UInt8,
    reason String,
    triggered_by LowCardinality(String),
    applies_to_strategy_id Nullable(String),
    applies_to_symbol Nullable(String)
)
ENGINE = MergeTree
ORDER BY (event_time_ms, level, symbol);
