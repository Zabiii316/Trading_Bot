from __future__ import annotations

import asyncio
import time
from collections.abc import Sequence
from typing import Any

import httpx

from .config import BinanceLiveExecutionConfig
from .models import BinanceOrderAck, BinanceOrderStatus, ExchangeOrderSnapshot, ExchangePositionSnapshot
from .signing import signed_query
from .mapping import parse_exchange_order, parse_position


class BinanceApiError(RuntimeError):
    def __init__(self, message: str, *, status_code: int | None = None, payload: Any = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.payload = payload


class BinanceFuturesRestClient:
    """Small signed REST client for Binance USD-M Futures trading endpoints.

    This client is intentionally narrow and dependency-light. It is designed for
    live execution/reconciliation paths, not bulk historical data ingestion.
    """

    def __init__(
        self,
        config: BinanceLiveExecutionConfig,
        *,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        config.validate()
        self.config = config
        self._client = http_client or httpx.AsyncClient(
            base_url=config.base_url,
            timeout=config.request_timeout_s,
            headers={"X-MBX-APIKEY": config.api_key},
        )
        self._owns_client = http_client is None

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    def timestamp_ms(self) -> int:
        return int(time.time() * 1000)

    async def signed_request(
        self,
        method: str,
        path: str,
        params: Sequence[tuple[str, str | int | float | bool | None]],
    ) -> Any:
        query = signed_query(params, self.config.api_secret)
        headers = {"X-MBX-APIKEY": self.config.api_key}
        last_exc: Exception | None = None
        for attempt in range(self.config.max_retries + 1):
            try:
                response = await self._client.request(
                    method,
                    path,
                    content=query if method.upper() in {"POST", "PUT", "DELETE"} else None,
                    params=query if method.upper() == "GET" else None,
                    headers={**self._client.headers, **headers, "Content-Type": "application/x-www-form-urlencoded"},
                )
                if response.status_code >= 400:
                    payload: Any
                    try:
                        payload = response.json()
                    except Exception:
                        payload = response.text
                    raise BinanceApiError(
                        f"Binance API error {response.status_code}: {payload}",
                        status_code=response.status_code,
                        payload=payload,
                    )
                return response.json()
            except (httpx.TimeoutException, httpx.TransportError, BinanceApiError) as exc:
                last_exc = exc
                if isinstance(exc, BinanceApiError) and exc.status_code not in {418, 429, 500, 502, 503, 504}:
                    raise
                if attempt >= self.config.max_retries:
                    raise
                await asyncio.sleep(self.config.retry_backoff_s * (2**attempt))
        raise RuntimeError(f"unreachable retry state: {last_exc}")

    async def place_order(self, params: Sequence[tuple[str, str | int | float | bool | None]]) -> BinanceOrderAck:
        raw = await self.signed_request("POST", "/fapi/v1/order", params)
        return BinanceOrderAck(
            symbol=str(raw.get("symbol", "")).upper(),
            venue_order_id=str(raw.get("orderId", "")),
            client_order_id=str(raw.get("clientOrderId", "")),
            status=BinanceOrderStatus(str(raw.get("status", "NEW"))),
            raw=raw,
        )

    async def cancel_order(
        self,
        *,
        symbol: str,
        orig_client_order_id: str | None = None,
        order_id: str | None = None,
    ) -> ExchangeOrderSnapshot:
        params: list[tuple[str, str | int | bool | None]] = [
            ("symbol", symbol.upper()),
            ("timestamp", self.timestamp_ms()),
            ("recvWindow", self.config.recv_window_ms),
        ]
        if orig_client_order_id:
            params.append(("origClientOrderId", orig_client_order_id))
        if order_id:
            params.append(("orderId", order_id))
        raw = await self.signed_request("DELETE", "/fapi/v1/order", params)
        return parse_exchange_order(raw)

    async def query_order(
        self,
        *,
        symbol: str,
        orig_client_order_id: str | None = None,
        order_id: str | None = None,
    ) -> ExchangeOrderSnapshot:
        params: list[tuple[str, str | int | bool | None]] = [
            ("symbol", symbol.upper()),
            ("timestamp", self.timestamp_ms()),
            ("recvWindow", self.config.recv_window_ms),
        ]
        if orig_client_order_id:
            params.append(("origClientOrderId", orig_client_order_id))
        if order_id:
            params.append(("orderId", order_id))
        raw = await self.signed_request("GET", "/fapi/v1/order", params)
        return parse_exchange_order(raw)

    async def open_orders(self, *, symbol: str | None = None) -> list[ExchangeOrderSnapshot]:
        params: list[tuple[str, str | int | bool | None]] = [
            ("timestamp", self.timestamp_ms()),
            ("recvWindow", self.config.recv_window_ms),
        ]
        if symbol:
            params.insert(0, ("symbol", symbol.upper()))
        raw = await self.signed_request("GET", "/fapi/v1/openOrders", params)
        return [parse_exchange_order(item) for item in raw]

    async def position_risk(self, *, symbol: str | None = None) -> list[ExchangePositionSnapshot]:
        params: list[tuple[str, str | int | bool | None]] = [
            ("timestamp", self.timestamp_ms()),
            ("recvWindow", self.config.recv_window_ms),
        ]
        if symbol:
            params.insert(0, ("symbol", symbol.upper()))
        raw = await self.signed_request("GET", "/fapi/v2/positionRisk", params)
        return [parse_position(item) for item in raw]
