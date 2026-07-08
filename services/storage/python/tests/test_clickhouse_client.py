from decimal import Decimal

import pytest

from trading_storage.clickhouse import ClickHouseHttpClient
from trading_storage.config import ClickHouseConfig


class FakeResponse:
    def __init__(self) -> None:
        self.raised = False

    def raise_for_status(self) -> None:
        self.raised = True


class FakeHttpClient:
    def __init__(self) -> None:
        self.calls = []

    async def post(self, path, params=None, content=None):
        response = FakeResponse()
        self.calls.append((path, params, content, response))
        return response


@pytest.mark.asyncio
async def test_clickhouse_insert_uses_json_each_row_payload() -> None:
    client = ClickHouseHttpClient(ClickHouseConfig(database="tradingbot"))
    fake = FakeHttpClient()
    client._client = fake
    result = await client.insert_json_each_row("raw_trades", [{"symbol": "BTCUSDT", "price": Decimal("1.23")}])
    assert result.row_count == 1
    path, params, content, response = fake.calls[0]
    assert path == "/"
    assert params["query"] == "INSERT INTO tradingbot.raw_trades FORMAT JSONEachRow"
    assert b'"symbol":"BTCUSDT"' in content
    assert b'"price":"1.23"' in content
    assert response.raised is True
