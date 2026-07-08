from decimal import Decimal

import pytest

from trading_contracts.enums import AggressorSide, EventType
from trading_market_data.binance_mapper import UnsupportedBinancePayload, map_combined_stream_payload


def test_maps_agg_trade_combined_payload():
    payload = {
        "stream": "btcusdt@aggTrade",
        "data": {
            "e": "aggTrade",
            "E": 1672515782136,
            "s": "BTCUSDT",
            "a": 12345,
            "p": "62000.10",
            "q": "0.25",
            "f": 100,
            "l": 105,
            "T": 1672515782130,
            "m": False,
            "M": True,
        },
    }
    event = map_combined_stream_payload(
        payload,
        source="test",
        venue="binance_usdm",
        market_type="perpetual_futures",
    )
    assert event.event_type == EventType.RAW_AGG_TRADE
    assert event.symbol == "BTCUSDT"
    assert event.price == Decimal("62000.10")
    assert event.quantity == Decimal("0.25")
    assert event.aggressor_side == AggressorSide.BUY


def test_maps_trade_payload_and_aggressor_side():
    payload = {
        "stream": "ethusdt@trade",
        "data": {
            "e": "trade",
            "E": 1672515782136,
            "s": "ETHUSDT",
            "t": 987,
            "p": "3500.00",
            "q": "1.5",
            "T": 1672515782130,
            "m": True,
            "M": True,
        },
    }
    event = map_combined_stream_payload(
        payload,
        source="test",
        venue="binance_spot",
        market_type="spot",
    )
    assert event.event_type == EventType.RAW_TRADE
    assert event.aggressor_side == AggressorSide.SELL


def test_maps_depth_update_with_previous_update_id():
    payload = {
        "stream": "btcusdt@depth@100ms",
        "data": {
            "e": "depthUpdate",
            "E": 1672515782136,
            "s": "BTCUSDT",
            "U": 1000,
            "u": 1005,
            "pu": 999,
            "b": [["61999.90", "0.50"]],
            "a": [["62000.20", "0.40"]],
        },
    }
    event = map_combined_stream_payload(
        payload,
        source="test",
        venue="binance_usdm",
        market_type="perpetual_futures",
    )
    assert event.event_type == EventType.DEPTH_UPDATE
    assert event.first_update_id == 1000
    assert event.final_update_id == 1005
    assert event.previous_final_update_id == 999
    assert event.bids[0].price == Decimal("61999.90")


def test_maps_book_ticker_without_event_type():
    payload = {
        "stream": "btcusdt@bookTicker",
        "data": {
            "u": 400900217,
            "s": "BTCUSDT",
            "b": "62000.00",
            "B": "1.25",
            "a": "62000.10",
            "A": "0.95",
        },
    }
    event = map_combined_stream_payload(
        payload,
        source="test",
        venue="binance_spot",
        market_type="spot",
    )
    assert event.event_type == EventType.BOOK_TICKER
    assert event.best_ask_price == Decimal("62000.10")


def test_rejects_unknown_payload():
    with pytest.raises(UnsupportedBinancePayload):
        map_combined_stream_payload(
            {"stream": "btcusdt@unknown", "data": {"e": "unknown"}},
            source="test",
            venue="binance_spot",
            market_type="spot",
        )
