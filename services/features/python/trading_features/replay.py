from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from trading_contracts.enums import EventType
from trading_contracts.events import (
    DepthUpdateEvent,
    OrderBookSnapshotEvent,
    RawAggTradeEvent,
    RawTradeEvent,
    ReconstructedBookEvent,
)
from trading_order_book.book import LocalOrderBook

from .book_view import BookView
from .engine import OrderFlowEngine


def _event_type_value(value) -> str:
    """Normalize enum/string event_type values into a plain string."""
    return getattr(value, "value", value)


def _event_type_matches(event_type: str, candidate) -> bool:
    return event_type == _event_type_value(candidate)


def _load_event(line: str):
    data = json.loads(line)
    event_type = _event_type_value(data.get("event_type"))

    if _event_type_matches(event_type, EventType.RAW_AGG_TRADE) or event_type == "raw.agg_trade":
        return RawAggTradeEvent.model_validate(data)

    if _event_type_matches(event_type, EventType.RAW_TRADE) or event_type == "raw.trade":
        return RawTradeEvent.model_validate(data)

    if _event_type_matches(event_type, EventType.ORDER_BOOK_SNAPSHOT) or event_type == "raw.order_book_snapshot":
        return OrderBookSnapshotEvent.model_validate(data)

    if _event_type_matches(event_type, EventType.DEPTH_UPDATE) or event_type == "raw.depth_update":
        return DepthUpdateEvent.model_validate(data)

    # This is the important fix for your current pipeline.
    if event_type in {"book.reconstructed", "reconstructed_book"}:
        return ReconstructedBookEvent.model_validate(data)

    return None


def _book_view_from_reconstructed(event: ReconstructedBookEvent, depth: int) -> BookView:
    """
    Build a BookView from a ReconstructedBookEvent.

    ReconstructedBookEvent normally carries best_bid/best_ask plus depth notional.
    For Phase 5 replay, top-of-book is enough to trigger feature emission and calculate
    queue imbalance/spread/top-level context.
    """
    bids = []
    asks = []

    if getattr(event, "best_bid", None) is not None:
        bids.append(event.best_bid)

    if getattr(event, "best_ask", None) is not None:
        asks.append(event.best_ask)

    return BookView.from_levels(
        symbol=event.symbol,
        event_time_ms=event.event_time_ms,
        received_time_ms=event.received_time_ms,
        venue=event.venue,
        market_type=event.market_type,
        last_update_id=event.last_update_id,
        bids=bids[:depth],
        asks=asks[:depth],
        is_sequence_healthy=event.is_sequence_healthy,
    )


def replay_order_flow(events: Iterable[str], depth: int = 20) -> list[str]:
    """Replay JSONL events into order-flow feature JSON lines.

    Supported input event types:
    - raw.trade
    - raw.agg_trade
    - raw.order_book_snapshot
    - raw.depth_update
    - book.reconstructed
    """

    engine = OrderFlowEngine()
    books: dict[str, LocalOrderBook] = {}
    output: list[str] = []

    for line in events:
        if not line.strip():
            continue

        event = _load_event(line)
        if event is None:
            continue

        if isinstance(event, (RawAggTradeEvent, RawTradeEvent)):
            engine.on_trade(event)
            continue

        if isinstance(event, OrderBookSnapshotEvent):
            book = books.setdefault(event.symbol, LocalOrderBook(event.symbol))
            book.load_snapshot(
                last_update_id=event.last_update_id,
                bids=event.bids,
                asks=event.asks,
                snapshot_time_ms=event.event_time_ms,
            )

            engine.on_book(BookView.from_snapshot(event, depth=depth))

            try:
                output.append(engine.to_event().model_dump_json())
            except RuntimeError:
                pass

            continue

        if isinstance(event, ReconstructedBookEvent):
            view = _book_view_from_reconstructed(event, depth=depth)
            engine.on_book(view)

            try:
                output.append(engine.to_event().model_dump_json())
            except RuntimeError:
                pass

            continue

        if isinstance(event, DepthUpdateEvent):
            book = books.get(event.symbol)

            if book is None or book.last_update_id is None:
                continue

            book.apply_delta(
                update_id=event.final_update_id,
                bids=event.bids,
                asks=event.asks,
            )

            view = BookView.from_levels(
                symbol=event.symbol,
                event_time_ms=event.event_time_ms,
                received_time_ms=event.received_time_ms,
                venue=event.venue,
                market_type=event.market_type,
                last_update_id=event.final_update_id,
                bids=book.bids.top_n(depth),
                asks=book.asks.top_n(depth),
                is_sequence_healthy=book.sequence_healthy,
            )

            engine.on_book(view)

            try:
                output.append(engine.to_event().model_dump_json())
            except RuntimeError:
                pass

    return output


def replay_file(input_path: Path, output_path: Path, depth: int = 20) -> int:
    lines = replay_order_flow(input_path.read_text().splitlines(), depth=depth)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines) + ("\n" if lines else ""))
    return len(lines)