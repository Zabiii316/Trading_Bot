CREATE TABLE IF NOT EXISTS backtest_runs
(
    run_id String,
    created_at DateTime64(3, 'UTC'),
    strategy_id String,
    symbols Array(String),
    config_json String,
    summary_json String
)
ENGINE = MergeTree
ORDER BY (created_at, run_id);

CREATE TABLE IF NOT EXISTS backtest_trades
(
    run_id String,
    trade_id String,
    signal_id String,
    symbol LowCardinality(String),
    side LowCardinality(String),
    quantity Float64,
    entry_price Float64,
    exit_price Float64,
    entry_time_ms UInt64,
    exit_time_ms UInt64,
    entry_fee_quote Float64,
    exit_fee_quote Float64,
    gross_pnl_quote Float64,
    net_pnl_quote Float64,
    return_bps Float64,
    r_multiple Float64,
    exit_reason LowCardinality(String)
)
ENGINE = MergeTree
ORDER BY (symbol, entry_time_ms, trade_id);
