from decimal import Decimal

import pytest

from trading_contracts.enums import EventType, MarketType, Venue
from trading_contracts.events import DepthUpdateEvent, OrderBookSnapshotEvent, PriceLevel
from trading_order_book.sequencer import BookSyncState, DepthSequencer, SequenceGapError


def lvl(price: str, qty: str) -> PriceLevel:
    return PriceLevel(price=Decimal(price), quantity=Decimal(qty))


def depth(first: int, final: int, *, pu: int | None = None, bids=None, asks=None) -> DepthUpdateEvent:
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


def snapshot(last_update_id: int) -> OrderBookSnapshotEvent:
    return OrderBookSnapshotEvent(
        event_type=EventType.ORDER_BOOK_SNAPSHOT,
        source="test",
        venue=Venue.BINANCE_USDM,
        market_type=MarketType.PERPETUAL_FUTURES,
        symbol="BTCUSDT",
        event_time_ms=1_000,
        received_time_ms=1_000,
        last_update_id=last_update_id,
        bids=[lvl("100", "1"), lvl("99", "2")],
        asks=[lvl("101", "1"), lvl("102", "2")],
        depth_limit=1000,
    )


def test_buffers_until_snapshot_then_applies_crossing_update() -> None:
    seq = DepthSequencer("BTCUSDT")
    assert seq.on_depth(depth(8, 10, pu=7, bids=[lvl("100", "0.5")])) is False
    assert seq.state == BookSyncState.BUFFERING

    applied = seq.on_snapshot(snapshot(9))

    assert len(applied) == 1
    assert seq.book.last_update_id == 10
    assert seq.book.best_bid().quantity == Decimal("0.5")
    assert seq.state == BookSyncState.LIVE


def test_discards_stale_buffered_updates() -> None:
    seq = DepthSequencer("BTCUSDT")
    seq.on_depth(depth(1, 5, bids=[lvl("100", "9")]))
    applied = seq.on_snapshot(snapshot(10))

    assert applied == []
    assert seq.dropped_stale == 1
    assert seq.book.best_bid().quantity == Decimal("1")


def test_futures_pu_gap_triggers_resync_required() -> None:
    seq = DepthSequencer("BTCUSDT")
    seq.on_snapshot(snapshot(10))

    with pytest.raises(SequenceGapError):
        seq.on_depth(depth(11, 12, pu=8, bids=[lvl("100", "2")]))

    assert seq.state == BookSyncState.RESYNC_REQUIRED
    assert seq.gap_count == 1


def test_spot_style_update_without_pu_requires_range_continuity() -> None:
    seq = DepthSequencer("BTCUSDT")
    seq.on_snapshot(snapshot(10))
    assert seq.on_depth(depth(11, 12, pu=None, bids=[lvl("100", "2")])) is True
    assert seq.book.last_update_id == 12

    with pytest.raises(SequenceGapError):
        seq.on_depth(depth(14, 15, pu=None, bids=[lvl("100", "3")]))
