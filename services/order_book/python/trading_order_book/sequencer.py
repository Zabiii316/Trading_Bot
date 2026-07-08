from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Deque

from trading_contracts.events import DepthUpdateEvent, OrderBookSnapshotEvent

from .book import LocalOrderBook


class SequenceGapError(RuntimeError):
    """Raised when diff-depth update IDs prove the local book is no longer reliable."""


class StaleDepthUpdate(RuntimeError):
    """Raised when a depth update is older than the synchronized local book."""


class BookSyncState(str, Enum):
    WAITING_FOR_SNAPSHOT = "waiting_for_snapshot"
    BUFFERING = "buffering"
    LIVE = "live"
    RESYNC_REQUIRED = "resync_required"


@dataclass(slots=True)
class DepthSequencer:
    """Apply Binance snapshot + diff update sequencing rules.

    The service buffers depth updates until a snapshot is loaded. After initialization:
    - stale events with u <= local lastUpdateId are ignored
    - first crossing update must cover lastUpdateId + 1
    - live updates must be contiguous; for USD-M futures, pu must match previous u
      where provided; otherwise U must be <= previous_u + 1 <= u.
    """

    symbol: str
    max_buffer_size: int = 10_000
    state: BookSyncState = BookSyncState.WAITING_FOR_SNAPSHOT
    book: LocalOrderBook = field(init=False)
    buffered: Deque[DepthUpdateEvent] = field(init=False)
    dropped_stale: int = 0
    gap_count: int = 0
    applied_count: int = 0
    snapshot_count: int = 0
    applied_since_snapshot: int = 0

    def __post_init__(self) -> None:
        self.symbol = self.symbol.upper()
        self.book = LocalOrderBook(self.symbol)
        self.buffered = deque(maxlen=self.max_buffer_size)

    def on_depth(self, event: DepthUpdateEvent) -> bool:
        self._assert_symbol(event.symbol)
        if self.state in {BookSyncState.WAITING_FOR_SNAPSHOT, BookSyncState.BUFFERING}:
            if len(self.buffered) == self.max_buffer_size:
                self.state = BookSyncState.RESYNC_REQUIRED
                self.gap_count += 1
                raise SequenceGapError("depth buffer overflow before snapshot")
            self.buffered.append(event)
            self.state = BookSyncState.BUFFERING
            return False

        if self.state == BookSyncState.RESYNC_REQUIRED:
            return False

        return self._apply_live_depth(event)

    def on_snapshot(self, event: OrderBookSnapshotEvent) -> list[DepthUpdateEvent]:
        self._assert_symbol(event.symbol)
        self.book.load_snapshot(
            last_update_id=event.last_update_id,
            bids=event.bids,
            asks=event.asks,
            snapshot_time_ms=event.event_time_ms,
        )
        self.snapshot_count += 1
        self.applied_since_snapshot = 0
        self.state = BookSyncState.LIVE
        applied: list[DepthUpdateEvent] = []

        pending = list(self.buffered)
        self.buffered.clear()
        pending.sort(key=lambda item: item.final_update_id)
        for depth in pending:
            if depth.final_update_id <= event.last_update_id:
                self.dropped_stale += 1
                continue
            if self._apply_live_depth(depth):
                applied.append(depth)
        return applied

    def reset_for_resync(self) -> None:
        self.buffered.clear()
        self.book = LocalOrderBook(self.symbol)
        self.state = BookSyncState.WAITING_FOR_SNAPSHOT

    def _apply_live_depth(self, event: DepthUpdateEvent) -> bool:
        assert self.book.last_update_id is not None
        previous_u = self.book.last_update_id

        if event.final_update_id <= previous_u:
            self.dropped_stale += 1
            return False

        is_first_after_snapshot = self.applied_since_snapshot == 0

        if is_first_after_snapshot:
            # First update after the REST snapshot must bridge/cross the next update ID.
            # Accept either:
            # - buffered crossing update: U <= snapshot_id and u >= snapshot_id + 1
            # - direct next update: U == snapshot_id + 1 and, for futures, pu == snapshot_id
            expected_next = previous_u + 1
            bridges_next_id = event.first_update_id <= expected_next <= event.final_update_id
            futures_direct_next_ok = (
                event.previous_final_update_id is not None
                and event.first_update_id == expected_next
                and event.previous_final_update_id == previous_u
            )
            buffered_crossing_ok = event.first_update_id <= previous_u and event.final_update_id >= expected_next
            spot_next_ok = event.previous_final_update_id is None and bridges_next_id
            if not (buffered_crossing_ok or futures_direct_next_ok or spot_next_ok):
                self._mark_gap(
                    f"first depth update does not bridge next id: U={event.first_update_id}, u={event.final_update_id}, expected_next={expected_next}, pu={event.previous_final_update_id}"
                )
        elif event.previous_final_update_id is not None:
            # Binance USD-M futures includes pu. It must equal the previous event's u.
            if event.previous_final_update_id != previous_u:
                self._mark_gap(
                    f"non-contiguous futures depth update: pu={event.previous_final_update_id}, expected={previous_u}"
                )
        else:
            # Spot streams do not include pu. The update range must cover previous_u + 1.
            expected_next = previous_u + 1
            if event.first_update_id > expected_next or event.final_update_id < expected_next:
                self._mark_gap(
                    f"non-contiguous spot depth update: U={event.first_update_id}, u={event.final_update_id}, expected_next={expected_next}"
                )

        self.book.apply_delta(update_id=event.final_update_id, bids=event.bids, asks=event.asks)
        self.applied_count += 1
        self.applied_since_snapshot += 1
        self.state = BookSyncState.LIVE
        return True

    def _mark_gap(self, message: str) -> None:
        self.state = BookSyncState.RESYNC_REQUIRED
        self.book.sequence_healthy = False
        self.gap_count += 1
        raise SequenceGapError(message)

    def _assert_symbol(self, symbol: str) -> None:
        if symbol.upper() != self.symbol:
            raise ValueError(f"event symbol {symbol} does not match sequencer symbol {self.symbol}")
