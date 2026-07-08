from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from decimal import Decimal

from trading_contracts.enums import EventType
from trading_contracts.events import DepthUpdateEvent, OrderBookSnapshotEvent, ReconstructedBookEvent

from trading_market_data.publisher import EventPublisher

from .book import BookIntegrityError
from .sequencer import BookSyncState, DepthSequencer, SequenceGapError
from .snapshot import BinanceDepthSnapshotClient


@dataclass(slots=True)
class ReconstructionHealth:
    processed_depth_updates: int = 0
    emitted_books: int = 0
    snapshots_loaded: int = 0
    stale_updates: int = 0
    sequence_gaps: int = 0
    integrity_errors: int = 0
    resyncs_requested: int = 0


@dataclass(slots=True)
class OrderBookReconstructionService:
    """Event-driven local order-book reconstruction service.

    The service consumes normalized DepthUpdateEvent objects, synchronizes against a REST
    OrderBookSnapshotEvent, applies updates through DepthSequencer, and publishes compact
    ReconstructedBookEvent snapshots after each accepted diff update.
    """

    symbol: str
    snapshot_client: BinanceDepthSnapshotClient | None = None
    publisher: EventPublisher | None = None
    emit_depth_levels: int = 10
    sequencer: DepthSequencer = field(init=False)
    health: ReconstructionHealth = field(default_factory=ReconstructionHealth)

    def __post_init__(self) -> None:
        self.symbol = self.symbol.upper()
        self.sequencer = DepthSequencer(self.symbol)

    async def start(self) -> None:
        if self.publisher is not None:
            await self.publisher.start()

    async def stop(self) -> None:
        if self.publisher is not None:
            await self.publisher.stop()

    async def bootstrap_snapshot(self, limit: int = 1000) -> ReconstructedBookEvent | None:
        if self.snapshot_client is None:
            raise RuntimeError("snapshot_client is required for bootstrap_snapshot")
        snapshot = await asyncio.to_thread(self.snapshot_client.fetch, self.symbol, limit)
        return await self.on_snapshot(snapshot)

    async def on_snapshot(self, snapshot: OrderBookSnapshotEvent) -> ReconstructedBookEvent | None:
        applied = self.sequencer.on_snapshot(snapshot)
        self.health.snapshots_loaded += 1
        # If snapshot alone created a valid book, emit once. Buffered events will have
        # advanced the book by the time this method returns, so one final compact emit is enough.
        event = self._build_book_event(snapshot.event_time_ms, snapshot.received_time_ms)
        await self._publish(event)
        return event

    async def on_depth(self, depth: DepthUpdateEvent) -> ReconstructedBookEvent | None:
        self.health.processed_depth_updates += 1
        try:
            applied = self.sequencer.on_depth(depth)
        except SequenceGapError:
            self.health.sequence_gaps += 1
            self.health.resyncs_requested += 1
            return None
        except BookIntegrityError:
            self.health.integrity_errors += 1
            self.sequencer.state = BookSyncState.RESYNC_REQUIRED
            self.sequencer.book.sequence_healthy = False
            self.health.resyncs_requested += 1
            return None

        if not applied:
            self.health.stale_updates = self.sequencer.dropped_stale
            return None

        event = self._build_book_event(depth.event_time_ms, depth.received_time_ms)
        await self._publish(event)
        return event

    async def _publish(self, event: ReconstructedBookEvent) -> None:
        if self.publisher is not None:
            await self.publisher.publish(event)
        self.health.emitted_books += 1

    def _build_book_event(self, event_time_ms: int, received_time_ms: int) -> ReconstructedBookEvent:
        book = self.sequencer.book
        top = book.top()
        return ReconstructedBookEvent(
            event_type=EventType.RECONSTRUCTED_BOOK,
            source="local_order_book_reconstructor",
            venue=self._infer_venue(),
            market_type=self._infer_market_type(),
            symbol=self.symbol,
            event_time_ms=event_time_ms,
            received_time_ms=received_time_ms,
            last_update_id=book.last_update_id or 0,
            best_bid=top.bid,
            best_ask=top.ask,
            spread=top.spread,
            spread_bps=top.spread_bps.quantize(Decimal("0.00000001")),
            bid_depth_notional_10=book.depth_notional("bid", self.emit_depth_levels),
            ask_depth_notional_10=book.depth_notional("ask", self.emit_depth_levels),
            book_checksum=book.checksum(self.emit_depth_levels),
            is_sequence_healthy=book.sequence_healthy and self.sequencer.state == BookSyncState.LIVE,
        )

    def _infer_venue(self):
        # Prefer the snapshot client's explicit venue. Fallback keeps unit tests simple.
        from trading_contracts.enums import Venue

        return self.snapshot_client.venue if self.snapshot_client is not None else Venue.BINANCE_USDM

    def _infer_market_type(self):
        from trading_contracts.enums import MarketType

        return (
            self.snapshot_client.market_type
            if self.snapshot_client is not None
            else MarketType.PERPETUAL_FUTURES
        )
