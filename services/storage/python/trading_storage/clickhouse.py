from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import quote

from .config import ClickHouseConfig
from .serialization import json_dumps_bytes
from .table_map import TableBatch, group_events_for_clickhouse


@dataclass(frozen=True)
class ClickHouseWriteResult:
    table_name: str
    row_count: int


class ClickHouseHttpClient:
    """Minimal async ClickHouse JSONEachRow client.

    The implementation intentionally uses ClickHouse's HTTP interface so the
    write path stays transparent and easy to test. `httpx` is optional at import
    time to keep contract tests lightweight.
    """

    def __init__(self, config: ClickHouseConfig) -> None:
        self.config = config
        self._client: Any | None = None

    async def start(self) -> None:
        try:
            import httpx
        except ImportError as exc:  # pragma: no cover - optional dependency.
            raise RuntimeError("Install httpx to use ClickHouseHttpClient") from exc
        headers = {"X-ClickHouse-User": self.config.username}
        if self.config.password:
            headers["X-ClickHouse-Key"] = self.config.password
        if self.config.compression:
            headers["Accept-Encoding"] = "gzip"
        self._client = httpx.AsyncClient(
            base_url=self.config.url.rstrip("/"),
            headers=headers,
            timeout=self.config.request_timeout_s,
        )

    async def stop(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def execute(self, sql: str) -> None:
        if self._client is None:
            raise RuntimeError("ClickHouseHttpClient.start() must be called before execute()")
        response = await self._client.post("/", content=sql.encode("utf-8"))
        response.raise_for_status()

    async def insert_json_each_row(self, table_name: str, rows: list[dict[str, Any]]) -> ClickHouseWriteResult:
        if self._client is None:
            raise RuntimeError("ClickHouseHttpClient.start() must be called before insert_json_each_row()")
        if not rows:
            return ClickHouseWriteResult(table_name=table_name, row_count=0)
        safe_table = quote(table_name, safe="")
        query = f"INSERT INTO {self.config.database}.{safe_table} FORMAT JSONEachRow"
        payload = b"\n".join(json_dumps_bytes(row) for row in rows) + b"\n"
        response = await self._client.post("/", params={"query": query}, content=payload)
        response.raise_for_status()
        return ClickHouseWriteResult(table_name=table_name, row_count=len(rows))


class ClickHouseEventSink:
    def __init__(self, client: ClickHouseHttpClient) -> None:
        self.client = client
        self.name = "clickhouse"

    async def start(self) -> None:
        await self.client.start()

    async def stop(self) -> None:
        await self.client.stop()

    async def write_events(self, events: list[Any]) -> list[ClickHouseWriteResult]:
        results: list[ClickHouseWriteResult] = []
        for batch in group_events_for_clickhouse(events):
            results.append(await self.write_batch(batch))
        return results

    async def write_batch(self, batch: TableBatch) -> ClickHouseWriteResult:
        return await self.client.insert_json_each_row(batch.table_name, batch.rows)
