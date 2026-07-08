from __future__ import annotations

from dataclasses import dataclass

from trading_contracts.enums import KillSwitchLevel, MarketType, Venue
from trading_contracts.events import KillSwitchEvent

from .models import KillSwitchState


_PRIORITY = {
    KillSwitchLevel.NONE: 0,
    KillSwitchLevel.SOFT_STRATEGY_SUSPENSION: 1,
    KillSwitchLevel.HARD_TRADING_HALT: 2,
    KillSwitchLevel.EMERGENCY_FLATTEN: 3,
}


@dataclass(slots=True)
class KillSwitchRegistry:
    """In-memory kill-switch registry used by the risk hot path.

    Runtime services can back this with Redis/PostgreSQL in Phase 13+. The local
    structure keeps pre-trade checks allocation-light and deterministic in tests.
    """

    global_state: KillSwitchState = KillSwitchState()
    symbol_states: dict[str, KillSwitchState] | None = None
    strategy_states: dict[str, KillSwitchState] | None = None

    def __post_init__(self) -> None:
        if self.symbol_states is None:
            self.symbol_states = {}
        if self.strategy_states is None:
            self.strategy_states = {}

    def update_from_event(self, event: KillSwitchEvent) -> None:
        state = KillSwitchState(
            level=event.level,
            is_active=event.is_active,
            reason=event.reason,
            applies_to_strategy_id=event.applies_to_strategy_id,
            applies_to_symbol=event.applies_to_symbol,
        )
        if event.applies_to_symbol:
            self.symbol_states[event.applies_to_symbol.upper()] = state
        elif event.applies_to_strategy_id:
            self.strategy_states[event.applies_to_strategy_id] = state
        else:
            self.global_state = state

    def resolve(self, *, strategy_id: str, symbol: str) -> KillSwitchState:
        candidates = [self.global_state]
        candidates.append(self.symbol_states.get(symbol.upper(), KillSwitchState()))
        candidates.append(self.strategy_states.get(strategy_id, KillSwitchState()))
        applicable = [c for c in candidates if c.applies_to(strategy_id=strategy_id, symbol=symbol)]
        if not applicable:
            return KillSwitchState()
        return max(applicable, key=lambda s: _PRIORITY[s.level])


def make_kill_switch_event(
    *,
    level: KillSwitchLevel,
    active: bool,
    reason: str,
    triggered_by: str,
    symbol: str | None = None,
    strategy_id: str | None = None,
    event_time_ms: int,
) -> KillSwitchEvent:
    return KillSwitchEvent(
        source="risk_engine",
        venue=Venue.INTERNAL,
        market_type=MarketType.PAPER,
        symbol=symbol or "GLOBAL",
        event_time_ms=event_time_ms,
        received_time_ms=event_time_ms,
        level=level,
        is_active=active,
        reason=reason,
        triggered_by=triggered_by,
        applies_to_strategy_id=strategy_id,
        applies_to_symbol=symbol,
    )
