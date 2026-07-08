from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request
from decimal import Decimal

from trading_contracts.enums import EventType, MarketType, Venue
from trading_contracts.events import OrderBookSnapshotEvent, PriceLevel


class SnapshotFetchError(RuntimeError):
    pass


class BinanceDepthSnapshotClient:
    """Minimal dependency-free REST snapshot client.

    It intentionally avoids exchange abstraction libraries so live reconstruction can follow
    Binance-specific sequence semantics and error handling.
    """

    SPOT_BASE = "https://api.binance.com"
    USDM_BASE = "https://fapi.binance.com"

    def __init__(self, *, venue: Venue, timeout_sec: float = 5.0) -> None:
        self.venue = venue
        self.timeout_sec = timeout_sec
        if venue == Venue.BINANCE_SPOT:
            self.base_url = self.SPOT_BASE
            self.path = "/api/v3/depth"
            self.market_type = MarketType.SPOT
        elif venue == Venue.BINANCE_USDM:
            self.base_url = self.USDM_BASE
            self.path = "/fapi/v1/depth"
            self.market_type = MarketType.PERPETUAL_FUTURES
        else:
            raise ValueError("only BINANCE_SPOT and BINANCE_USDM are supported in Phase 3")

    def fetch(self, symbol: str, limit: int = 1000) -> OrderBookSnapshotEvent:
        if limit not in {5, 10, 20, 50, 100, 500, 1000, 5000}:
            raise ValueError("invalid Binance depth limit")
        query = urllib.parse.urlencode({"symbol": symbol.upper(), "limit": limit})
        url = f"{self.base_url}{self.path}?{query}"
        received_ms = int(time.time() * 1000)
        try:
            with urllib.request.urlopen(url, timeout=self.timeout_sec) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except Exception as exc:  # pragma: no cover - network failure depends on environment.
            raise SnapshotFetchError(f"failed to fetch Binance depth snapshot: {exc}") from exc

        try:
            last_update_id = int(payload["lastUpdateId"])
            bids = [PriceLevel(price=Decimal(p), quantity=Decimal(q)) for p, q in payload["bids"]]
            asks = [PriceLevel(price=Decimal(p), quantity=Decimal(q)) for p, q in payload["asks"]]
        except Exception as exc:
            raise SnapshotFetchError("malformed Binance depth snapshot") from exc

        return OrderBookSnapshotEvent(
            event_type=EventType.ORDER_BOOK_SNAPSHOT,
            source="binance_rest_snapshot",
            venue=self.venue,
            market_type=self.market_type,
            symbol=symbol.upper(),
            event_time_ms=received_ms,
            received_time_ms=received_ms,
            last_update_id=last_update_id,
            bids=bids,
            asks=asks,
            depth_limit=limit,
            raw=payload,
        )
