from decimal import Decimal

import pytest

from trading_contracts.enums import EventType, MarketType, Venue
from trading_contracts.events import DepthUpdateEvent, OrderBookSnapshotEvent, PriceLevel
from trading_market_data.publisher import MemoryPublisher
from trading_order_book.service import OrderBookReconstructionService


def lvl(price: str, qty: str) -> PriceLevel:
    return PriceLevel(price=Decimal(price), quantity=Decimal(qty))


def snapshot() -> OrderBookSnapshotEvent:
    return OrderBookSnapshotEvent(
        event_type=EventType.ORDER_BOOK_SNAPSHOT,
        source="test",
        venue=Venue.BINANCE_USDM,
        market_type=MarketType.PERPETUAL_FUTURES,
        symbol="BTCUSDT",
        event_time_ms=1_000,
        received_time_ms=1_000,
        last_update_id=100,
        bids=[lvl("100", "2"), lvl("99", "3")],
        asks=[lvl("101", "2"), lvl("102", "3")],
        depth_limit=1000,
    )


def depth(first: int, final: int, pu: int, bids=None, asks=None) -> DepthUpdateEvent:
    return DepthUpdateEvent(
        event_type=EventType.DEPTH_UPDATE,
        source="test",
        venue=Venue.BINANCE_USDM,
        market_type=MarketType.PERPETUAL_FUTURES,
        symbol="BTCUSDT",
        event_time_ms=1_000 + final,
        received_time_ms=1_000 + final,
        first_update_id=first,
        final_update_id=final,
        previous_final_update_id=pu,
        bids=bids or [],
        asks=asks or [],
    )


@pytest.mark.asyncio
async def test_service_emits_reconstructed_book_events() -> None:
    publisher = MemoryPublisher()
    service = OrderBookReconstructionService("BTCUSDT", publisher=publisher)
    await service.start()
    try:
        snap_event = await service.on_snapshot(snapshot())
        book_event = await service.on_depth(depth(101, 101, 100, bids=[lvl("100", "1")]))
    finally:
        await service.stop()

    assert snap_event is not None
    assert book_event is not None
    assert book_event.event_type == EventType.RECONSTRUCTED_BOOK
    assert book_event.last_update_id == 101
    assert book_event.best_bid.quantity == Decimal("1")
    assert book_event.spread == Decimal("1")
    assert book_event.is_sequence_healthy is True
    assert len(publisher.events) == 2


@pytest.mark.asyncio
async def test_service_gap_does_not_emit_event_and_requests_resync() -> None:
    publisher = MemoryPublisher()
    service = OrderBookReconstructionService("BTCUSDT", publisher=publisher)
    await service.on_snapshot(snapshot())

    result = await service.on_depth(depth(105, 106, 104, bids=[lvl("100", "1")]))

    assert result is None
    assert service.health.sequence_gaps == 1
    assert service.health.resyncs_requested == 1
