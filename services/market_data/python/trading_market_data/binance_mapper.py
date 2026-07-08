from __future__ import annotations

from decimal import Decimal
from typing import Any

from trading_contracts.enums import AggressorSide, MarketType, Venue
from trading_contracts.events import BookTickerEvent, DepthUpdateEvent, PriceLevel, RawAggTradeEvent, RawTradeEvent

from .clock import now_ms


class UnsupportedBinancePayload(ValueError):
    pass


def _event_time(payload: dict[str, Any]) -> int:
    return int(payload.get("E") or payload.get("T") or now_ms())


def _venue(value: str) -> Venue:
    return Venue(value)


def _market_type(value: str) -> MarketType:
    return MarketType(value)


def _aggressor_from_buyer_maker(is_buyer_maker: bool) -> AggressorSide:
    # Binance m/isBuyerMaker means the buyer is the maker. If buyer is maker,
    # the aggressor/taker was selling into the bid. Otherwise, taker was buying.
    return AggressorSide.SELL if is_buyer_maker else AggressorSide.BUY


def map_combined_stream_payload(
    message: dict[str, Any],
    *,
    source: str,
    venue: str,
    market_type: str,
    include_raw: bool = True,
) -> RawAggTradeEvent | RawTradeEvent | DepthUpdateEvent | BookTickerEvent:
    """Normalize a Binance combined-stream message into an internal event contract.

    Binance combined-stream messages have the form:
    {"stream": "btcusdt@aggTrade", "data": {...}}
    Raw stream messages can also be passed directly as the data payload.
    """
    data = message.get("data", message)
    stream_name = str(message.get("stream", ""))
    raw = data if include_raw else None
    event_type = data.get("e")
    received = now_ms()

    if event_type == "aggTrade":
        is_buyer_maker = bool(data["m"])
        return RawAggTradeEvent(
            source=source,
            venue=_venue(venue),
            market_type=_market_type(market_type),
            symbol=str(data["s"]),
            event_time_ms=int(data["E"]),
            received_time_ms=received,
            agg_trade_id=int(data["a"]),
            price=Decimal(str(data["p"])),
            quantity=Decimal(str(data["q"])),
            first_trade_id=int(data["f"]),
            last_trade_id=int(data["l"]),
            trade_time_ms=int(data["T"]),
            is_buyer_maker=is_buyer_maker,
            aggressor_side=_aggressor_from_buyer_maker(is_buyer_maker),
            raw=raw,
        )

    if event_type == "trade":
        is_buyer_maker = bool(data["m"])
        return RawTradeEvent(
            source=source,
            venue=_venue(venue),
            market_type=_market_type(market_type),
            symbol=str(data["s"]),
            event_time_ms=int(data["E"]),
            received_time_ms=received,
            trade_id=int(data["t"]),
            price=Decimal(str(data["p"])),
            quantity=Decimal(str(data["q"])),
            trade_time_ms=int(data["T"]),
            is_buyer_maker=is_buyer_maker,
            aggressor_side=_aggressor_from_buyer_maker(is_buyer_maker),
            raw=raw,
        )

    if event_type == "depthUpdate":
        return DepthUpdateEvent(
            source=source,
            venue=_venue(venue),
            market_type=_market_type(market_type),
            symbol=str(data["s"]),
            event_time_ms=int(data["E"]),
            received_time_ms=received,
            first_update_id=int(data["U"]),
            final_update_id=int(data["u"]),
            previous_final_update_id=int(data["pu"]) if "pu" in data else None,
            bids=[PriceLevel(price=Decimal(str(p)), quantity=Decimal(str(q))) for p, q in data.get("b", [])],
            asks=[PriceLevel(price=Decimal(str(p)), quantity=Decimal(str(q))) for p, q in data.get("a", [])],
            raw=raw,
        )

    # Spot bookTicker stream has no e field. USD-M futures has e=bookTicker in many contexts,
    # but the mapper also supports messages routed by stream name.
    if event_type == "bookTicker" or stream_name.endswith("@bookTicker") or _looks_like_book_ticker(data):
        symbol = str(data.get("s") or stream_name.split("@")[0]).upper()
        return BookTickerEvent(
            source=source,
            venue=_venue(venue),
            market_type=_market_type(market_type),
            symbol=symbol,
            event_time_ms=_event_time(data),
            received_time_ms=received,
            update_id=int(data["u"]) if "u" in data else None,
            best_bid_price=Decimal(str(data["b"])),
            best_bid_quantity=Decimal(str(data["B"])),
            best_ask_price=Decimal(str(data["a"])),
            best_ask_quantity=Decimal(str(data["A"])),
        )

    raise UnsupportedBinancePayload(f"Unsupported Binance stream payload: stream={stream_name!r}, e={event_type!r}")


def _looks_like_book_ticker(data: dict[str, Any]) -> bool:
    return all(key in data for key in ("u", "s", "b", "B", "a", "A"))
