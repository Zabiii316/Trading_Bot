from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from trading_contracts.enums import EventType
from trading_contracts.events import (
    AnchoredVwapEvent,
    LiquiditySweepEvent,
    OrderFlowFeatureEvent,
    ReconstructedBookEvent,
    SignalEvent,
    model_for_event_type,
)

from .engine import SignalScorerEngine, SignalEngineConfig


SUPPORTED = {
    EventType.LIQUIDITY_SWEEP.value,
    EventType.ORDER_FLOW_FEATURE.value,
    EventType.ANCHORED_VWAP.value,
    EventType.RECONSTRUCTED_BOOK.value,
}


def replay_events(events: Iterable[dict], config: SignalEngineConfig | None = None) -> list[SignalEvent]:
    engine = SignalScorerEngine(config)
    output: list[SignalEvent] = []
    for payload in events:
        event_type = payload.get("event_type")
        if event_type not in SUPPORTED:
            continue
        model = model_for_event_type(event_type)
        event = model.model_validate(payload)
        if isinstance(event, LiquiditySweepEvent):
            output.extend(engine.on_sweep(event))
        elif isinstance(event, OrderFlowFeatureEvent):
            output.extend(engine.on_order_flow(event))
        elif isinstance(event, AnchoredVwapEvent):
            output.extend(engine.on_avwap(event))
        elif isinstance(event, ReconstructedBookEvent):
            output.extend(engine.on_book(event))
    return output


def replay_file(path: str | Path, config: SignalEngineConfig | None = None) -> list[SignalEvent]:
    path = Path(path)
    def read() -> Iterable[dict]:
        with path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                yield json.loads(line)
    return replay_events(read(), config=config)
