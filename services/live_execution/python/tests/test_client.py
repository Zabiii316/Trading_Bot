from __future__ import annotations

import httpx
import pytest

from trading_live_execution.client import BinanceApiError, BinanceFuturesRestClient
from trading_live_execution.config import BinanceLiveExecutionConfig


@pytest.mark.asyncio
async def test_place_order_posts_signed_payload_and_parses_ack() -> None:
    seen: dict[str, str] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["body"] = request.content.decode()
        assert request.headers["X-MBX-APIKEY"] == "key"
        return httpx.Response(
            200,
            json={"symbol": "BTCUSDT", "orderId": 123, "clientOrderId": "tb14-a", "status": "NEW"},
        )

    transport = httpx.MockTransport(handler)
    http = httpx.AsyncClient(transport=transport, base_url="https://testnet.binancefuture.com")
    client = BinanceFuturesRestClient(
        BinanceLiveExecutionConfig(api_key="key", api_secret="secret"),
        http_client=http,
    )
    ack = await client.place_order([("symbol", "BTCUSDT"), ("timestamp", 1)])
    assert ack.venue_order_id == "123"
    assert ack.client_order_id == "tb14-a"
    assert "/fapi/v1/order" in seen["url"]
    assert "signature=" in seen["body"]
    await http.aclose()


@pytest.mark.asyncio
async def test_query_order_gets_signed_params_and_parses_snapshot() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert "signature=" in str(request.url)
        return httpx.Response(
            200,
            json={
                "symbol": "BTCUSDT",
                "orderId": 123,
                "clientOrderId": "tb14-a",
                "status": "FILLED",
                "side": "BUY",
                "type": "LIMIT",
                "origQty": "0.01",
                "executedQty": "0.01",
                "avgPrice": "62000",
                "reduceOnly": False,
                "updateTime": 10,
            },
        )

    http = httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="https://testnet.binancefuture.com")
    client = BinanceFuturesRestClient(BinanceLiveExecutionConfig(api_key="key", api_secret="secret"), http_client=http)
    snapshot = await client.query_order(symbol="BTCUSDT", orig_client_order_id="tb14-a")
    assert snapshot.status.value == "FILLED"
    assert snapshot.executed_quantity == snapshot.original_quantity
    await http.aclose()


@pytest.mark.asyncio
async def test_non_retryable_binance_error_raises() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={"code": -2019, "msg": "Margin is insufficient."})

    http = httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="https://testnet.binancefuture.com")
    client = BinanceFuturesRestClient(BinanceLiveExecutionConfig(api_key="key", api_secret="secret"), http_client=http)
    with pytest.raises(BinanceApiError):
        await client.place_order([("symbol", "BTCUSDT"), ("timestamp", 1)])
    await http.aclose()
