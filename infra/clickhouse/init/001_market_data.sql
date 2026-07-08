CREATE DATABASE IF NOT EXISTS tradingbot;

CREATE TABLE IF NOT EXISTS tradingbot.raw_trades
(
    event_id UUID,
    schema_version LowCardinality(String),
    event_type LowCardinality(String),
    source LowCardinality(String),
    venue LowCardinality(String),
    market_type LowCardinality(String),
    symbol LowCardinality(String),
    event_time DateTime64(3, 'UTC'),
    event_time_ms UInt64,
    received_time_ms UInt64,
    trace_id UUID,
    trade_id Nullable(UInt64),
    agg_trade_id Nullable(UInt64),
    price Decimal(38, 18),
    quantity Decimal(38, 18),
    first_trade_id Nullable(UInt64),
    last_trade_id Nullable(UInt64),
    trade_time_ms UInt64,
    is_buyer_maker UInt8,
    aggressor_side LowCardinality(String),
    raw_json String,
    ingested_at DateTime64(3, 'UTC') DEFAULT now64(3)
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(event_time)
ORDER BY (venue, market_type, symbol, event_time_ms, event_id)
SETTINGS index_granularity = 8192;

CREATE TABLE IF NOT EXISTS tradingbot.raw_depth_updates
(
    event_id UUID,
    schema_version LowCardinality(String),
    source LowCardinality(String),
    venue LowCardinality(String),
    market_type LowCardinality(String),
    symbol LowCardinality(String),
    event_time DateTime64(3, 'UTC'),
    event_time_ms UInt64,
    received_time_ms UInt64,
    trace_id UUID,
    first_update_id UInt64,
    final_update_id UInt64,
    previous_final_update_id Nullable(UInt64),
    bids_json String,
    asks_json String,
    raw_json String,
    ingested_at DateTime64(3, 'UTC') DEFAULT now64(3)
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(event_time)
ORDER BY (venue, market_type, symbol, event_time_ms, final_update_id)
SETTINGS index_granularity = 8192;

CREATE TABLE IF NOT EXISTS tradingbot.raw_order_book_snapshots
(
    event_id UUID,
    schema_version LowCardinality(String),
    source LowCardinality(String),
    venue LowCardinality(String),
    market_type LowCardinality(String),
    symbol LowCardinality(String),
    event_time DateTime64(3, 'UTC'),
    event_time_ms UInt64,
    received_time_ms UInt64,
    trace_id UUID,
    last_update_id UInt64,
    depth_limit UInt16,
    bids_json String,
    asks_json String,
    raw_json String,
    ingested_at DateTime64(3, 'UTC') DEFAULT now64(3)
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(event_time)
ORDER BY (venue, market_type, symbol, event_time_ms, last_update_id)
SETTINGS index_granularity = 8192;

CREATE TABLE IF NOT EXISTS tradingbot.reconstructed_books
(
    event_id UUID,
    schema_version LowCardinality(String),
    source LowCardinality(String),
    venue LowCardinality(String),
    market_type LowCardinality(String),
    symbol LowCardinality(String),
    event_time DateTime64(3, 'UTC'),
    event_time_ms UInt64,
    received_time_ms UInt64,
    trace_id UUID,
    last_update_id UInt64,
    best_bid_price Decimal(38, 18),
    best_bid_quantity Decimal(38, 18),
    best_ask_price Decimal(38, 18),
    best_ask_quantity Decimal(38, 18),
    spread Decimal(38, 18),
    spread_bps Decimal(38, 18),
    bid_depth_notional_10 Decimal(38, 18),
    ask_depth_notional_10 Decimal(38, 18),
    book_checksum Nullable(String),
    is_sequence_healthy UInt8,
    ingested_at DateTime64(3, 'UTC') DEFAULT now64(3)
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(event_time)
ORDER BY (venue, market_type, symbol, event_time_ms, last_update_id)
SETTINGS index_granularity = 8192;

CREATE TABLE IF NOT EXISTS tradingbot.system_health_events
(
    event_id UUID,
    component LowCardinality(String),
    status LowCardinality(String),
    severity LowCardinality(String),
    event_time DateTime64(3, 'UTC'),
    event_time_ms UInt64,
    symbol Nullable(String),
    counters_json String,
    message String,
    ingested_at DateTime64(3, 'UTC') DEFAULT now64(3)
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(event_time)
ORDER BY (component, event_time_ms, event_id)
SETTINGS index_granularity = 8192;

CREATE TABLE IF NOT EXISTS tradingbot.order_flow_features
(
    event_id UUID,
    schema_version LowCardinality(String),
    source LowCardinality(String),
    venue LowCardinality(String),
    market_type LowCardinality(String),
    symbol LowCardinality(String),
    event_time DateTime64(3, 'UTC'),
    event_time_ms UInt64,
    received_time_ms UInt64,
    trace_id UUID,
    window_ms UInt32,
    trade_count UInt32,
    buy_volume Decimal(38, 18),
    sell_volume Decimal(38, 18),
    delta Decimal(38, 18),
    normalized_delta Decimal(38, 18),
    cumulative_volume_delta Decimal(38, 18),
    queue_imbalance_l1 Nullable(Decimal(38, 18)),
    queue_imbalance_l5 Nullable(Decimal(38, 18)),
    queue_imbalance_l10 Nullable(Decimal(38, 18)),
    ofi_l1 Nullable(Decimal(38, 18)),
    ofi_l5 Nullable(Decimal(38, 18)),
    absorption_ratio Nullable(Decimal(38, 18)),
    depth_depletion_bid Nullable(Decimal(38, 18)),
    depth_depletion_ask Nullable(Decimal(38, 18)),
    depth_replenishment_bid Nullable(Decimal(38, 18)),
    depth_replenishment_ask Nullable(Decimal(38, 18)),
    ingested_at DateTime64(3, 'UTC') DEFAULT now64(3)
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(event_time)
ORDER BY (venue, market_type, symbol, event_time_ms, window_ms, event_id)
SETTINGS index_granularity = 8192;

CREATE TABLE IF NOT EXISTS tradingbot.liquidity_levels
(
    event_id UUID,
    schema_version LowCardinality(String),
    source LowCardinality(String),
    venue LowCardinality(String),
    market_type LowCardinality(String),
    symbol LowCardinality(String),
    event_time DateTime64(3, 'UTC'),
    event_time_ms UInt64,
    received_time_ms UInt64,
    trace_id UUID,
    level_id UUID,
    level_type LowCardinality(String),
    price Decimal(38, 18),
    zone_low Decimal(38, 18),
    zone_high Decimal(38, 18),
    quality_score Decimal(18, 8),
    touches UInt32,
    first_seen_ms UInt64,
    last_seen_ms UInt64,
    is_active UInt8,
    metadata_json String,
    ingested_at DateTime64(3, 'UTC') DEFAULT now64(3)
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(event_time)
ORDER BY (venue, market_type, symbol, level_type, event_time_ms, price, event_id)
SETTINGS index_granularity = 8192;


CREATE TABLE IF NOT EXISTS tradingbot.liquidity_sweeps
(
    event_id UUID,
    schema_version LowCardinality(String),
    source LowCardinality(String),
    venue LowCardinality(String),
    market_type LowCardinality(String),
    symbol LowCardinality(String),
    event_time DateTime64(3, 'UTC'),
    event_time_ms UInt64,
    received_time_ms UInt64,
    trace_id UUID,
    sweep_id UUID,
    level_id UUID,
    state LowCardinality(String),
    outcome LowCardinality(String),
    level_price Decimal(38, 18),
    sweep_extreme_price Nullable(Decimal(38, 18)),
    penetration_ticks Nullable(Decimal(38, 18)),
    penetration_atr Nullable(Decimal(38, 18)),
    reclaim_time_ms Nullable(UInt64),
    liquidity_score Decimal(18, 8),
    order_flow_score Nullable(Decimal(18, 8)),
    avwap_score Nullable(Decimal(18, 8)),
    notes Nullable(String),
    ingested_at DateTime64(3, 'UTC') DEFAULT now64(3)
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(event_time)
ORDER BY (venue, market_type, symbol, event_time_ms, sweep_id, state)
SETTINGS index_granularity = 8192;

CREATE TABLE IF NOT EXISTS tradingbot.anchored_vwaps
(
    event_id UUID,
    schema_version LowCardinality(String),
    source LowCardinality(String),
    venue LowCardinality(String),
    market_type LowCardinality(String),
    symbol LowCardinality(String),
    event_time DateTime64(3, 'UTC'),
    event_time_ms UInt64,
    received_time_ms UInt64,
    trace_id UUID,
    avwap_id UUID,
    anchor_name LowCardinality(String),
    anchor_type LowCardinality(String),
    anchor_time_ms UInt64,
    anchor_price Decimal(38, 18),
    avwap Decimal(38, 18),
    slope Decimal(38, 18),
    upper_band_1 Nullable(Decimal(38, 18)),
    lower_band_1 Nullable(Decimal(38, 18)),
    band_z_score Nullable(Decimal(38, 18)),
    distance_from_price_bps Decimal(38, 18),
    confirmation LowCardinality(String),
    confirmation_score Decimal(18, 8),
    is_reclaim UInt8,
    is_failure UInt8,
    sweep_id Nullable(UUID),
    ingested_at DateTime64(3, 'UTC') DEFAULT now64(3)
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(event_time)
ORDER BY (venue, market_type, symbol, event_time_ms, avwap_id, anchor_type)
SETTINGS index_granularity = 8192;

CREATE TABLE IF NOT EXISTS tradingbot.signals
(
    event_id UUID,
    schema_version LowCardinality(String),
    source LowCardinality(String),
    venue LowCardinality(String),
    market_type LowCardinality(String),
    symbol LowCardinality(String),
    event_time DateTime64(3, 'UTC'),
    event_time_ms UInt64,
    received_time_ms UInt64,
    trace_id UUID,
    signal_id UUID,
    strategy_id LowCardinality(String),
    sweep_id Nullable(UUID),
    side LowCardinality(String),
    outcome LowCardinality(String),
    entry_candidate Decimal(38, 18),
    stop Decimal(38, 18),
    target_1 Decimal(38, 18),
    target_2 Nullable(Decimal(38, 18)),
    liquidity_score Decimal(18, 8),
    order_flow_score Decimal(18, 8),
    avwap_score Decimal(18, 8),
    regime_score Decimal(18, 8),
    execution_score Decimal(18, 8),
    final_score Decimal(18, 8),
    expected_net_return_bps Decimal(38, 18),
    expires_at_ms UInt64,
    feature_snapshot_id UUID,
    rationale_json String,
    ingested_at DateTime64(3, 'UTC') DEFAULT now64(3)
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(event_time)
ORDER BY (venue, market_type, symbol, event_time_ms, strategy_id, signal_id)
SETTINGS index_granularity = 8192;
