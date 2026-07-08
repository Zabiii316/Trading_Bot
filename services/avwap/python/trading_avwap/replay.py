from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from trading_contracts.events import (
    AnchoredVwapEvent,
    LiquidityLevelEvent,
    LiquiditySweepEvent,
    RawAggTradeEvent,
    RawTradeEvent,
    ReconstructedBookEvent,
    model_for_event_type,
)

from .engine import AnchoredVwapEngine


def parse_event(payload: dict):
    model = model_for_event_type(payload["event_type"])
    return model.model_validate(payload)


def replay_events(events: Iterable[object], engine: AnchoredVwapEngine | None = None) -> list[AnchoredVwapEvent]:
    engine = engine or AnchoredVwapEngine()
    out: list[AnchoredVwapEvent] = []
    for event in events:
        if isinstance(event, LiquidityLevelEvent):
            out.extend(engine.on_liquidity_level(event))
        elif isinstance(event, LiquiditySweepEvent):
            out.extend(engine.on_sweep(event))
        elif isinstance(event, (RawAggTradeEvent, RawTradeEvent)):
            out.extend(engine.on_trade(event))
        elif isinstance(event, ReconstructedBookEvent):
            out.extend(engine.on_book(event))
    return out


def replay_jsonl(path: str | Path, engine: AnchoredVwapEngine | None = None) -> list[AnchoredVwapEvent]:
    events = []
    with Path(path).open("r", encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            events.append(parse_event(json.loads(line)))
    return replay_events(events, engine)
