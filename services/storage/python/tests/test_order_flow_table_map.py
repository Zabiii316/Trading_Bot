from trading_features.book_view import BookView
from trading_features.engine import OrderFlowEngine
from trading_storage.table_map import row_for_event, table_for_event


def test_order_flow_feature_storage_mapping() -> None:
    engine = OrderFlowEngine()
    engine.on_book(
        BookView.from_levels(
            symbol="BTCUSDT",
            venue="binance_usdm",
            market_type="perpetual_futures",
            event_time_ms=1_000,
            received_time_ms=1_001,
            last_update_id=1,
            bids=[(100.0, 10.0)],
            asks=[(100.1, 8.0)],
        )
    )
    event = engine.to_event()
    assert table_for_event(event) == "order_flow_features"
    row = row_for_event(event)
    assert row["window_ms"] == 1000
    assert row["queue_imbalance_l1"] is not None
