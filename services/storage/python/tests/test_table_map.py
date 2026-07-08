from decimal import Decimal

from trading_contracts.enums import EventType, MarketType, Venue
from trading_contracts.events import (
    DepthUpdateEvent,
    OrderBookSnapshotEvent,
    PriceLevel,
    RawAggTradeEvent,
    ReconstructedBookEvent,
)
from trading_storage.table_map import group_events_for_clickhouse, row_for_event, table_for_event


def base(event_type: EventType) -> dict:
    return {
        "event_type": event_type,
        "source": "unit_test",
        "venue": Venue.BINANCE_USDM,
        "market_type": MarketType.PERPETUAL_FUTURES,
        "symbol": "btcusdt",
        "event_time_ms": 1_783_086_819_245,
        "received_time_ms": 1_783_086_819_250,
    }


def lvl(price: str, qty: str) -> PriceLevel:
    return PriceLevel(price=Decimal(price), quantity=Decimal(qty))


def test_raw_agg_trade_maps_to_clickhouse_row() -> None:
    event = RawAggTradeEvent(
        **base(EventType.RAW_AGG_TRADE),
        agg_trade_id=10,
        price=Decimal("62175.80"),
        quantity=Decimal("0.010"),
        first_trade_id=10,
        last_trade_id=12,
        trade_time_ms=1_783_086_819_245,
        is_buyer_maker=True,
        aggressor_side="sell",
    )
    row = row_for_event(event)
    assert table_for_event(event) == "raw_trades"
    assert row["symbol"] == "BTCUSDT"
    assert row["price"] == "62175.80"
    assert row["quantity"] == "0.010"
    assert row["is_buyer_maker"] == 1
    assert row["aggressor_side"] == "sell"


def test_depth_update_levels_are_json_encoded() -> None:
    event = DepthUpdateEvent(
        **base(EventType.DEPTH_UPDATE),
        first_update_id=101,
        final_update_id=102,
        previous_final_update_id=100,
        bids=[lvl("100", "1")],
        asks=[lvl("101", "2")],
    )
    row = row_for_event(event)
    assert row["first_update_id"] == 101
    assert '"price":"100"' in row["bids_json"]
    assert '"quantity":"2"' in row["asks_json"]


def test_snapshot_and_reconstructed_grouping() -> None:
    snapshot = OrderBookSnapshotEvent(
        **base(EventType.ORDER_BOOK_SNAPSHOT),
        last_update_id=100,
        bids=[lvl("100", "1")],
        asks=[lvl("101", "1")],
        depth_limit=1000,
    )
    book = ReconstructedBookEvent(
        **base(EventType.RECONSTRUCTED_BOOK),
        last_update_id=101,
        best_bid=lvl("100", "2"),
        best_ask=lvl("101", "2"),
        spread=Decimal("1"),
        spread_bps=Decimal("99.0099009900990099"),
        bid_depth_notional_10=Decimal("200"),
        ask_depth_notional_10=Decimal("202"),
        is_sequence_healthy=True,
        book_checksum="abc",
    )
    batches = group_events_for_clickhouse([snapshot, book])
    assert {batch.table_name for batch in batches} == {"raw_order_book_snapshots", "reconstructed_books"}
