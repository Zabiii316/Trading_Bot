from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

from trading_contracts.enums import EventType
from trading_contracts.events import EventEnvelope, KillSwitchEvent, SignalEvent, model_for_event_type

from .engine import RiskEngine
from .kill_switch import KillSwitchRegistry
from .models import AccountState, PositionSnapshot, RiskLimits, RiskRequest


@dataclass(slots=True)
class RiskReplayState:
    account: AccountState
    kill_switches: KillSwitchRegistry = field(default_factory=KillSwitchRegistry)
    decisions: list[EventEnvelope] = field(default_factory=list)


def parse_event_line(line: str) -> EventEnvelope:
    payload = json.loads(line)
    event_type = payload.get("event_type")
    if not event_type:
        raise ValueError("event line missing event_type")
    model = model_for_event_type(str(event_type))
    return model.model_validate(payload)


def iter_jsonl_events(path: str | Path) -> Iterable[EventEnvelope]:
    with Path(path).open("r", encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, 1):
            text = line.strip()
            if not text:
                continue
            try:
                yield parse_event_line(text)
            except Exception as exc:  # pragma: no cover - CLI context includes line number
                raise ValueError(f"failed to parse {path}:{line_no}: {exc}") from exc


def run_risk_replay(
    events: Iterable[EventEnvelope],
    *,
    account: AccountState,
    limits: RiskLimits | None = None,
) -> list[EventEnvelope]:
    engine = RiskEngine(limits)
    state = RiskReplayState(account=account)
    for event in events:
        event_type = event.event_type.value if hasattr(event.event_type, "value") else str(event.event_type)
        if event_type == EventType.KILL_SWITCH.value:
            state.kill_switches.update_from_event(event)  # type: ignore[arg-type]
            state.decisions.append(event)
        elif event_type == EventType.SIGNAL.value:
            signal = event  # type: ignore[assignment]
            assert isinstance(signal, SignalEvent)
            kill = state.kill_switches.resolve(strategy_id=signal.strategy_id, symbol=signal.symbol)
            _, decision = engine.evaluate(
                RiskRequest(
                    signal=signal,
                    account=state.account,
                    event_time_ms=max(signal.event_time_ms, signal.expires_at_ms - 1),
                    mark_price=float(signal.entry_candidate),
                    kill_switch=kill,
                )
            )
            state.decisions.append(decision)
    return state.decisions
