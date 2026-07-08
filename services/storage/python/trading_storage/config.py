from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "y", "on"}


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    return default if raw is None or raw == "" else int(raw)


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    return default if raw is None or raw == "" else float(raw)


@dataclass(frozen=True)
class ClickHouseConfig:
    url: str = "http://localhost:8123"
    database: str = "tradingbot"
    username: str = "default"
    password: str = ""
    request_timeout_s: float = 10.0
    compression: bool = True

    @classmethod
    def from_env(cls) -> "ClickHouseConfig":
        return cls(
            url=os.getenv("CLICKHOUSE_URL", cls.url),
            database=os.getenv("CLICKHOUSE_DATABASE", cls.database),
            username=os.getenv("CLICKHOUSE_USER", cls.username),
            password=os.getenv("CLICKHOUSE_PASSWORD", cls.password),
            request_timeout_s=_env_float("CLICKHOUSE_TIMEOUT_S", cls.request_timeout_s),
            compression=_env_bool("CLICKHOUSE_COMPRESSION", cls.compression),
        )


@dataclass(frozen=True)
class PostgresConfig:
    dsn: str = "postgresql://tradingbot:tradingbot@localhost:5432/tradingbot"
    min_pool_size: int = 1
    max_pool_size: int = 5
    command_timeout_s: float = 10.0

    @classmethod
    def from_env(cls) -> "PostgresConfig":
        return cls(
            dsn=os.getenv("POSTGRES_DSN", cls.dsn),
            min_pool_size=_env_int("POSTGRES_MIN_POOL_SIZE", cls.min_pool_size),
            max_pool_size=_env_int("POSTGRES_MAX_POOL_SIZE", cls.max_pool_size),
            command_timeout_s=_env_float("POSTGRES_COMMAND_TIMEOUT_S", cls.command_timeout_s),
        )


@dataclass(frozen=True)
class StorageWriterConfig:
    sink: str = "clickhouse"
    max_batch_rows: int = 5000
    max_linger_ms: int = 250
    max_queue_size: int = 250000
    dead_letter_path: Path = Path("data/dead_letter/storage_failures.jsonl")
    fail_fast: bool = False

    @classmethod
    def from_env(cls) -> "StorageWriterConfig":
        return cls(
            sink=os.getenv("STORAGE_SINK", cls.sink),
            max_batch_rows=_env_int("STORAGE_MAX_BATCH_ROWS", cls.max_batch_rows),
            max_linger_ms=_env_int("STORAGE_MAX_LINGER_MS", cls.max_linger_ms),
            max_queue_size=_env_int("STORAGE_MAX_QUEUE_SIZE", cls.max_queue_size),
            dead_letter_path=Path(os.getenv("STORAGE_DEAD_LETTER_PATH", str(cls.dead_letter_path))),
            fail_fast=_env_bool("STORAGE_FAIL_FAST", cls.fail_fast),
        )
