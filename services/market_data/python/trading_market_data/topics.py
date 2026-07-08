from __future__ import annotations

from trading_contracts.enums import EventType


def topic_for_event(event_type: str, symbol: str) -> str:
    """Map normalized events to stable bus topics."""
    clean_symbol = symbol.upper()
    mapping = {
        EventType.RAW_AGG_TRADE.value: f"raw.binance.agg_trade.{clean_symbol}",
        EventType.RAW_TRADE.value: f"raw.binance.trade.{clean_symbol}",
        EventType.DEPTH_UPDATE.value: f"raw.binance.depth.{clean_symbol}",
        EventType.BOOK_TICKER.value: f"raw.binance.book_ticker.{clean_symbol}",
        EventType.ORDER_BOOK_SNAPSHOT.value: f"raw.binance.snapshot.{clean_symbol}",
        EventType.RECONSTRUCTED_BOOK.value: f"book.reconstructed.{clean_symbol}",
    }
    try:
        return mapping[event_type]
    except KeyError as exc:
        raise ValueError(f"Unsupported event_type for market-data topic: {event_type}") from exc
