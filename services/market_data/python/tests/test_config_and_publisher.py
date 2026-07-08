import json

import pytest

from trading_market_data.config import BinanceMarket, RecorderConfig
from trading_market_data.publisher import JsonlPublisher, MemoryPublisher, build_publisher
from trading_market_data.topics import topic_for_event
from trading_contracts.enums import EventType
from trading_market_data.binance_mapper import map_combined_stream_payload


def test_combined_stream_url_for_usdm():
    config = RecorderConfig(symbols=("BTCUSDT",), market=BinanceMarket.USDM_FUTURES, streams=("aggTrade", "depth@100ms"))
    assert config.combined_stream_url() == "wss://fstream.binance.com/stream?streams=btcusdt@aggTrade/btcusdt@depth@100ms"


def test_config_from_env_parses_symbols_and_streams():
    config = RecorderConfig.from_env({"SYMBOLS": "btcusdt, ethusdt", "STREAMS": "aggTrade,bookTicker", "BINANCE_MARKET": "spot"})
    assert config.symbols == ("BTCUSDT", "ETHUSDT")
    assert config.streams == ("aggTrade", "bookTicker")
    assert config.market == BinanceMarket.SPOT


def test_topic_mapping():
    assert topic_for_event(EventType.RAW_AGG_TRADE.value, "BTCUSDT") == "raw.binance.agg_trade.BTCUSDT"
    with pytest.raises(ValueError):
        topic_for_event("unknown", "BTCUSDT")


@pytest.mark.asyncio
async def test_memory_publisher_collects_events():
    publisher = MemoryPublisher()
    await publisher.start()
    event = map_combined_stream_payload(
        {"stream": "btcusdt@bookTicker", "data": {"u": 1, "s": "BTCUSDT", "b": "1", "B": "2", "a": "3", "A": "4"}},
        source="test",
        venue="binance_spot",
        market_type="spot",
    )
    await publisher.publish(event)
    await publisher.stop()
    assert len(publisher.events) == 1


@pytest.mark.asyncio
async def test_jsonl_publisher_writes_events(tmp_path):
    path = tmp_path / "events.jsonl"
    publisher = JsonlPublisher(path)
    await publisher.start()
    event = map_combined_stream_payload(
        {"stream": "btcusdt@bookTicker", "data": {"u": 1, "s": "BTCUSDT", "b": "1", "B": "2", "a": "3", "A": "4"}},
        source="test",
        venue="binance_spot",
        market_type="spot",
    )
    await publisher.publish(event)
    await publisher.stop()
    line = path.read_text().strip()
    assert json.loads(line)["symbol"] == "BTCUSDT"


def test_build_publisher_rejects_unknown_kind():
    with pytest.raises(ValueError):
        build_publisher("unknown", jsonl_path="x.jsonl", kafka_bootstrap_servers="localhost:9092", kafka_client_id="x")
