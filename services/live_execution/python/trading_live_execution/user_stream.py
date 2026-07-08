from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass

import httpx
import websockets

from .config import BinanceLiveExecutionConfig


@dataclass(frozen=True, slots=True)
class UserDataStreamConfig:
    keepalive_interval_s: int = 30 * 60
    read_timeout_s: float = 60.0
    reconnect_delay_s: float = 2.0


class BinanceUserDataStream:
    """Manages Binance USD-M Futures user-data stream listen keys.

    The stream is optional for unit tests but required in production to receive
    asynchronous ORDER_TRADE_UPDATE events. REST reconciliation remains the
    authoritative fallback when the stream disconnects or a gap is suspected.
    """

    def __init__(
        self,
        config: BinanceLiveExecutionConfig,
        *,
        http_client: httpx.AsyncClient | None = None,
        stream_config: UserDataStreamConfig | None = None,
    ) -> None:
        self.config = config
        self.stream_config = stream_config or UserDataStreamConfig()
        self._client = http_client or httpx.AsyncClient(
            base_url=config.base_url,
            timeout=config.request_timeout_s,
            headers={"X-MBX-APIKEY": config.api_key},
        )
        self._owns_client = http_client is None
        self.listen_key: str | None = None

    @property
    def websocket_base_url(self) -> str:
        # Binance uses the same USD-M futures stream host for user streams; testnet routing
        # is controlled by the listen-key source. A base override can be supplied in wrappers.
        return "wss://fstream.binance.com/ws"

    async def aclose(self) -> None:
        if self.listen_key:
            try:
                await self.close_listen_key()
            except Exception:
                pass
        if self._owns_client:
            await self._client.aclose()

    async def start_listen_key(self) -> str:
        response = await self._client.post("/fapi/v1/listenKey", headers={"X-MBX-APIKEY": self.config.api_key})
        response.raise_for_status()
        payload = response.json()
        self.listen_key = str(payload["listenKey"])
        return self.listen_key

    async def keepalive(self) -> None:
        if not self.listen_key:
            raise RuntimeError("listen_key has not been started")
        response = await self._client.put(
            "/fapi/v1/listenKey",
            headers={"X-MBX-APIKEY": self.config.api_key},
            params={"listenKey": self.listen_key},
        )
        response.raise_for_status()

    async def close_listen_key(self) -> None:
        if not self.listen_key:
            return
        response = await self._client.delete(
            "/fapi/v1/listenKey",
            headers={"X-MBX-APIKEY": self.config.api_key},
            params={"listenKey": self.listen_key},
        )
        response.raise_for_status()
        self.listen_key = None

    async def events(self) -> AsyncIterator[dict]:
        if not self.listen_key:
            await self.start_listen_key()
        assert self.listen_key is not None
        url = f"{self.websocket_base_url}/{self.listen_key}"
        async with websockets.connect(url, ping_interval=None) as ws:
            while True:
                raw = await asyncio.wait_for(ws.recv(), timeout=self.stream_config.read_timeout_s)
                if isinstance(raw, bytes):
                    raw = raw.decode("utf-8")
                yield json.loads(raw)

    async def run_forever(self, handler: Callable[[dict], None | object]) -> None:
        while True:
            try:
                async for event in self.events():
                    result = handler(event)
                    if asyncio.iscoroutine(result):
                        await result
            except asyncio.CancelledError:
                raise
            except Exception:
                await asyncio.sleep(self.stream_config.reconnect_delay_s)
