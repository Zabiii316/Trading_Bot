from __future__ import annotations

import asyncio
from pathlib import Path

from trading_storage.clickhouse import ClickHouseHttpClient
from trading_storage.config import ClickHouseConfig
from trading_storage.migrations import load_sql_files, run_clickhouse_migrations


async def main() -> None:
    client = ClickHouseHttpClient(ClickHouseConfig.from_env())
    await client.start()
    try:
        sql_files = load_sql_files(Path("infra/clickhouse/init"))
        count = await run_clickhouse_migrations(client, sql_files)
        print(f"Applied {count} ClickHouse statements")
    finally:
        await client.stop()


if __name__ == "__main__":
    asyncio.run(main())
