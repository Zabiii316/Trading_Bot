from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from trading_contracts.events import (
    EventEnvelope,
    ReconstructedBookEvent,
    RiskDecisionEvent,
    SignalEvent,
    model_for_event_type,
)

from .engine import PaperExecutionEngine
from .models import PaperExecutionConfig


def load_jsonl_events(path: Path) -> list[EventEnvelope]:
    events: list[EventEnvelope] = []
    for line_number, line in enumerate(path.read_text().splitlines(), start=1):
        if not line.strip():
            continue
        payload = json.loads(line)
        model = model_for_event_type(payload["event_type"])
        try:
            events.append(model.model_validate(payload))
        except Exception as exc:  # pragma: no cover - aids CLI debugging
            raise ValueError(f"invalid event on line {line_number}: {exc}") from exc
    return events


def run_paper_replay(events: Iterable[EventEnvelope], config: PaperExecutionConfig | None = None) -> dict[str, object]:
    engine = PaperExecutionEngine(config=config)
    signals: dict[str, SignalEvent] = {}
    pending_risks: dict[str, RiskDecisionEvent] = {}
    emitted: list[EventEnvelope] = []
    rejected: list[tuple[str, tuple[str, ...]]] = []
    sorted_events = sorted(events, key=lambda e: (e.event_time_ms, str(e.event_id)))
    for event in sorted_events:
        if isinstance(event, SignalEvent):
            signals[str(event.signal_id)] = event
        elif isinstance(event, RiskDecisionEvent):
            if str(event.signal_id) not in signals:
                rejected.append((str(event.signal_id), ("missing_signal",)))
                continue
            pending_risks[str(event.signal_id)] = event
        elif isinstance(event, ReconstructedBookEvent):
            engine.mark_positions(event)
            # For deterministic examples, submit all approved risk decisions observed before this book.
            for signal_id, risk_event in list(pending_risks.items()):
                signal = signals[signal_id]
                order_event, reasons = engine.submit(signal=signal, risk_decision=risk_event, book=event, event_time_ms=event.event_time_ms)
                if order_event is None:
                    rejected.append((signal_id, reasons))
                else:
                    emitted.append(order_event)
                del pending_risks[signal_id]
            emitted.extend(engine.on_book(event))
    report = engine.reconcile(event_time_ms=max((event.event_time_ms for event in sorted_events), default=0))
    return {
        "orders": len(engine.orders),
        "positions": len(engine.positions),
        "emitted_events": emitted,
        "rejected": rejected,
        "reconciliation": report,
    }
