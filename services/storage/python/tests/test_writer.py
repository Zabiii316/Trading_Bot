import asyncio
from decimal import Decimal

import pytest

from trading_contracts.enums import EventType, MarketType, Venue
from trading_contracts.events import RawAggTradeEvent
from trading_storage.writer import BatchPolicy, BatchingStorageWriter, MemoryStorageSink


def trade(agg_id: int) -> RawAggTradeEvent:
    return RawAggTradeEvent(
        event_type=EventType.RAW_AGG_TRADE,
        source="unit_test",
        venue=Venue.BINANCE_USDM,
        market_type=MarketType.PERPETUAL_FUTURES,
        symbol="BTCUSDT",
        event_time_ms=1_783_086_819_245 + agg_id,
        received_time_ms=1_783_086_819_250 + agg_id,
        agg_trade_id=agg_id,
        price=Decimal("62175.80"),
        quantity=Decimal("0.001"),
        first_trade_id=agg_id,
        last_trade_id=agg_id,
        trade_time_ms=1_783_086_819_245 + agg_id,
        is_buyer_maker=False,
        aggressor_side="buy",
    )


@pytest.mark.asyncio
async def test_batching_writer_flushes_by_size() -> None:
    sink = MemoryStorageSink()
    writer = BatchingStorageWriter(sink, policy=BatchPolicy(max_batch_rows=2, max_linger_ms=5000))
    await writer.start()
    try:
        await writer.publish(trade(1))
        await writer.publish(trade(2))
        await asyncio.sleep(0.05)
    finally:
        await writer.stop()
    assert writer.counters.written_events == 2
    assert sink.batches[0][0] == "raw_trades"
    assert len(sink.batches[0][1]) == 2


@pytest.mark.asyncio
async def test_flush_now_writes_pending_events() -> None:
    sink = MemoryStorageSink()
    writer = BatchingStorageWriter(sink, policy=BatchPolicy(max_batch_rows=100, max_linger_ms=5000))
    await writer.start()
    try:
        await writer.publish(trade(1))
        await writer.flush_now()
    finally:
        await writer.stop()
    assert writer.counters.written_events == 1
    assert writer.counters.flush_count >= 1
