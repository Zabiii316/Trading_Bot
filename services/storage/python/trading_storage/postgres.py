from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID, uuid4

from .config import PostgresConfig


@dataclass(frozen=True)
class AuditRecord:
    batch_id: UUID
    sink_name: str
    table_name: str
    row_count: int
    first_event_time_ms: int | None
    last_event_time_ms: int | None
    status: str
    error_message: str | None = None


class PostgresAuditSink:
    """Transactional state/audit sink.

    ClickHouse is the primary high-volume market data store. PostgreSQL stores
    low-volume operational state and audit records, which must be consistent and
    queryable by support tooling.
    """

    def __init__(self, config: PostgresConfig) -> None:
        self.config = config
        self._pool: Any | None = None
        self.name = "postgres"

    async def start(self) -> None:
        try:
            import asyncpg
        except ImportError as exc:  # pragma: no cover - optional dependency.
            raise RuntimeError("Install asyncpg to use PostgresAuditSink") from exc
        self._pool = await asyncpg.create_pool(
            dsn=self.config.dsn,
            min_size=self.config.min_pool_size,
            max_size=self.config.max_pool_size,
            command_timeout=self.config.command_timeout_s,
        )

    async def stop(self) -> None:
        if self._pool is not None:
            await self._pool.close()
            self._pool = None

    async def write_audit(self, record: AuditRecord) -> None:
        if self._pool is None:
            raise RuntimeError("PostgresAuditSink.start() must be called before write_audit()")
        query = """
        INSERT INTO storage_write_audit (
            batch_id, sink_name, table_name, row_count,
            first_event_time_ms, last_event_time_ms,
            status, error_message, committed_at
        ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8, CASE WHEN $7 = 'committed' THEN now() ELSE NULL END)
        """
        await self._pool.execute(
            query,
            record.batch_id,
            record.sink_name,
            record.table_name,
            record.row_count,
            record.first_event_time_ms,
            record.last_event_time_ms,
            record.status,
            record.error_message,
        )

    async def upsert_health_state(
        self,
        *,
        component: str,
        status: str,
        severity: str,
        last_event_time_ms: int,
        last_message: str,
        counters: dict[str, Any],
    ) -> None:
        if self._pool is None:
            raise RuntimeError("PostgresAuditSink.start() must be called before upsert_health_state()")
        query = """
        INSERT INTO system_health_state (
            component, status, severity, last_event_time_ms, last_message, counters, updated_at
        ) VALUES ($1,$2,$3,$4,$5,$6::jsonb,now())
        ON CONFLICT (component) DO UPDATE SET
            status = EXCLUDED.status,
            severity = EXCLUDED.severity,
            last_event_time_ms = EXCLUDED.last_event_time_ms,
            last_message = EXCLUDED.last_message,
            counters = EXCLUDED.counters,
            updated_at = now()
        """
        import json

        await self._pool.execute(
            query,
            component,
            status,
            severity,
            last_event_time_ms,
            last_message,
            json.dumps(counters, separators=(",", ":")),
        )


def audit_record_from_events(
    *,
    sink_name: str,
    table_name: str,
    events: list[Any],
    status: str,
    batch_id: UUID | None = None,
    error_message: str | None = None,
) -> AuditRecord:
    times = [int(event.event_time_ms) for event in events if hasattr(event, "event_time_ms")]
    return AuditRecord(
        batch_id=batch_id or uuid4(),
        sink_name=sink_name,
        table_name=table_name,
        row_count=len(events),
        first_event_time_ms=min(times) if times else None,
        last_event_time_ms=max(times) if times else None,
        status=status,
        error_message=error_message,
    )
