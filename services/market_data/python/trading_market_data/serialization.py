from __future__ import annotations

from typing import Any

try:  # orjson is faster and preferred in production.
    import orjson
except Exception:  # pragma: no cover - fallback for minimal environments.
    orjson = None


def dumps_json_bytes(value: Any) -> bytes:
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json")
    if orjson is not None:
        return orjson.dumps(value)
    import json

    return json.dumps(value, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def loads_json(value: str | bytes | bytearray) -> Any:
    if orjson is not None:
        return orjson.loads(value)
    import json

    return json.loads(value)
