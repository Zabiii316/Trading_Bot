from __future__ import annotations

import json
from pathlib import Path

from trading_contracts.events import LiquidityLevelEvent, OrderFlowFeatureEvent, ReconstructedBookEvent
from trading_features.book_view import BookView

from .state_machine import LiquiditySweepStateMachine


def _load_event(payload: dict):
    event_type = payload.get("event_type")
    if event_type == "liquidity.level":
        return LiquidityLevelEvent.model_validate(payload)
    if event_type == "features.order_flow":
        return OrderFlowFeatureEvent.model_validate(payload)
    if event_type == "book.reconstructed":
        return ReconstructedBookEvent.model_validate(payload)
    return None


def replay_file(path: str | Path, engine: LiquiditySweepStateMachine | None = None) -> list:
    engine = engine or LiquiditySweepStateMachine()
    emitted = []
    with Path(path).open("r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            event = _load_event(json.loads(line))
            if event is None:
                continue
            if isinstance(event, LiquidityLevelEvent):
                emitted.extend(engine.on_liquidity_level(event))
            elif isinstance(event, OrderFlowFeatureEvent):
                emitted.extend(engine.on_order_flow(event))
            elif isinstance(event, ReconstructedBookEvent):
                emitted.extend(engine.on_book(BookView.from_reconstructed(event)))
    return emitted
