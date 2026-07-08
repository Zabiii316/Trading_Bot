from __future__ import annotations

from decimal import Decimal
from typing import Any

try:
    import orjson
except Exception:  # pragma: no cover
    orjson = None


def to_jsonable(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, dict):
        return {str(k): to_jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_jsonable(v) for v in value]
    return value


def json_dumps_bytes(value: Any) -> bytes:
    value = to_jsonable(value)
    if orjson is not None:
        return orjson.dumps(value)
    import json

    return json.dumps(value, separators=(",", ":"), ensure_ascii=False, default=str).encode("utf-8")


def json_dumps_str(value: Any) -> str:
    return json_dumps_bytes(value).decode("utf-8")


def decimal_to_str(value: Decimal | int | float | str | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return format(value, "f")
    return str(value)


def bool_to_u8(value: bool) -> int:
    return 1 if value else 0


def ms_to_ch_datetime64(value_ms: int) -> str:
    """Return ClickHouse DateTime64(3) compatible UTC string."""
    from datetime import datetime, timezone

    return datetime.fromtimestamp(value_ms / 1000, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S.%f")[:23]
