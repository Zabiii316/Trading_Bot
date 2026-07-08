from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from .serialization import json_dumps_bytes


class DeadLetterWriter:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._lock = asyncio.Lock()

    async def write(self, *, event: Any | None, error: BaseException | str, context: dict[str, Any] | None = None) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "error": str(error),
            "context": context or {},
            "event": event.model_dump(mode="json") if hasattr(event, "model_dump") else event,
        }
        async with self._lock:
            with self.path.open("ab") as handle:
                handle.write(json_dumps_bytes(payload) + b"\n")
