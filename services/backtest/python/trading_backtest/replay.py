from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path

from trading_contracts.events import EventEnvelope, model_for_event_type

from .engine import EventDrivenBacktestEngine
from .models import BacktestConfig, BacktestReport


def parse_event_line(line: str) -> EventEnvelope:
    payload = json.loads(line)
    event_type = payload.get("event_type")
    if event_type is None:
        raise ValueError("event payload is missing event_type")
    model = model_for_event_type(str(event_type))
    return model.model_validate(payload)


def iter_jsonl_events(path: str | Path) -> Iterable[EventEnvelope]:
    with Path(path).open("r", encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            try:
                yield parse_event_line(stripped)
            except Exception as exc:  # pragma: no cover - exact pydantic text is version-specific
                raise ValueError(f"failed to parse event at {path}:{line_no}: {exc}") from exc


def replay_events(events: Iterable[EventEnvelope], config: BacktestConfig | None = None) -> BacktestReport:
    engine = EventDrivenBacktestEngine(config)
    last_time = -1
    for event in events:
        # Fail early on non-monotonic replay files. This protects deterministic
        # performance reporting from accidental time travel in fixture data.
        if event.event_time_ms < last_time:
            raise ValueError(
                f"events must be sorted by event_time_ms: {event.event_time_ms} < {last_time}"
            )
        last_time = event.event_time_ms
        engine.on_event(event)
    return engine.finalize()


def replay_backtest_file(path: str | Path, config: BacktestConfig | None = None) -> BacktestReport:
    return replay_events(iter_jsonl_events(path), config)
