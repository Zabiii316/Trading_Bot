from __future__ import annotations

from pathlib import Path
from typing import Iterable


def load_sql_files(directory: str | Path) -> list[str]:
    path = Path(directory)
    return [file.read_text(encoding="utf-8") for file in sorted(path.glob("*.sql"))]


def split_sql_statements(sql: str) -> list[str]:
    statements: list[str] = []
    current: list[str] = []
    in_single = False
    in_double = False
    for char in sql:
        if char == "'" and not in_double:
            in_single = not in_single
        elif char == '"' and not in_single:
            in_double = not in_double
        if char == ";" and not in_single and not in_double:
            statement = "".join(current).strip()
            if statement:
                statements.append(statement)
            current = []
        else:
            current.append(char)
    tail = "".join(current).strip()
    if tail:
        statements.append(tail)
    return statements


async def run_clickhouse_migrations(client, sql_files: Iterable[str]) -> int:
    count = 0
    for sql in sql_files:
        for statement in split_sql_statements(sql):
            await client.execute(statement)
            count += 1
    return count
