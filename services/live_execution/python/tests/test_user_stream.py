from __future__ import annotations

import httpx
import pytest

from trading_live_execution.config import BinanceLiveExecutionConfig
from trading_live_execution.user_stream import BinanceUserDataStream


@pytest.mark.asyncio
async def test_user_stream_listen_key_lifecycle() -> None:
    calls: list[str] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.method)
        if request.method == "POST":
            return httpx.Response(200, json={"listenKey": "abc"})
        return httpx.Response(200, json={})

    http = httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="https://testnet.binancefuture.com")
    stream = BinanceUserDataStream(BinanceLiveExecutionConfig(api_key="key", api_secret="secret"), http_client=http)
    listen_key = await stream.start_listen_key()
    assert listen_key == "abc"
    await stream.keepalive()
    await stream.close_listen_key()
    assert calls == ["POST", "PUT", "DELETE"]
    await http.aclose()
