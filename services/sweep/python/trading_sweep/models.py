from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from uuid import UUID, uuid4

from trading_contracts.enums import LiquidityLevelType, SweepOutcome, SweepState
from trading_contracts.events import LiquidityLevelEvent, OrderFlowFeatureEvent


class SweepDirection(str, Enum):
    """Direction in which the liquidity level is expected to be swept."""

    UPSIDE = "upside"      # liquidity above price; upside stop run
    DOWNSIDE = "downside"  # liquidity below price; downside stop run


class ResolutionBias(str, Enum):
    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"


HIGH_LEVEL_TYPES = {
    LiquidityLevelType.PREVIOUS_DAY_HIGH.value,
    LiquidityLevelType.PREVIOUS_WEEK_HIGH.value,
    LiquidityLevelType.SESSION_HIGH.value,
    LiquidityLevelType.SWING_HIGH.value,
    LiquidityLevelType.EQUAL_HIGHS.value,
}
LOW_LEVEL_TYPES = {
    LiquidityLevelType.PREVIOUS_DAY_LOW.value,
    LiquidityLevelType.PREVIOUS_WEEK_LOW.value,
    LiquidityLevelType.SESSION_LOW.value,
    LiquidityLevelType.SWING_LOW.value,
    LiquidityLevelType.EQUAL_LOWS.value,
}


def classify_level_direction(level: LiquidityLevelEvent, current_price: float | None = None) -> SweepDirection | None:
    """Classify a level as upside/downside liquidity.

    Round numbers are context-dependent. If current_price is unavailable we keep the
    direction unassigned until the engine sees a book update.
    """

    level_type = str(level.level_type)
    if level_type in HIGH_LEVEL_TYPES:
        return SweepDirection.UPSIDE
    if level_type in LOW_LEVEL_TYPES:
        return SweepDirection.DOWNSIDE
    if level_type == LiquidityLevelType.ROUND_NUMBER.value and current_price is not None:
        return SweepDirection.UPSIDE if current_price <= float(level.price) else SweepDirection.DOWNSIDE
    return None


def rejection_outcome(direction: SweepDirection) -> SweepOutcome:
    return SweepOutcome.BEARISH_REJECTION if direction == SweepDirection.UPSIDE else SweepOutcome.BULLISH_REJECTION


def acceptance_outcome(direction: SweepDirection) -> SweepOutcome:
    return SweepOutcome.BULLISH_ACCEPTANCE if direction == SweepDirection.UPSIDE else SweepOutcome.BEARISH_ACCEPTANCE


def outcome_bias(outcome: SweepOutcome) -> ResolutionBias:
    outcome_value = outcome.value if hasattr(outcome, "value") else str(outcome)
    if outcome_value in {SweepOutcome.BULLISH_REJECTION.value, SweepOutcome.BULLISH_ACCEPTANCE.value}:
        return ResolutionBias.BULLISH
    if outcome_value in {SweepOutcome.BEARISH_REJECTION.value, SweepOutcome.BEARISH_ACCEPTANCE.value}:
        return ResolutionBias.BEARISH
    return ResolutionBias.NEUTRAL


@dataclass(slots=True)
class SweepContext:
    sweep_id: UUID
    level: LiquidityLevelEvent
    state: SweepState
    direction: SweepDirection | None
    created_ms: int
    updated_ms: int
    approach_time_ms: int | None = None
    penetration_time_ms: int | None = None
    consumption_time_ms: int | None = None
    resolution_time_ms: int | None = None
    sweep_extreme_price: float | None = None
    penetration_ticks: float | None = None
    penetration_atr: float | None = None
    outcome: SweepOutcome = SweepOutcome.UNRESOLVED
    order_flow_score: float | None = None
    last_feature: OrderFlowFeatureEvent | None = None
    last_mid_price: float | None = None
    last_notes: list[str] = field(default_factory=list)

    @classmethod
    def create(cls, level: LiquidityLevelEvent, now_ms: int, direction: SweepDirection | None = None) -> "SweepContext":
        return cls(
            sweep_id=uuid4(),
            level=level,
            state=SweepState.LEVEL_ARMED,
            direction=direction,
            created_ms=now_ms,
            updated_ms=now_ms,
        )

    @property
    def zone_low(self) -> float:
        return float(self.level.zone_low)

    @property
    def zone_high(self) -> float:
        return float(self.level.zone_high)

    @property
    def level_price(self) -> float:
        return float(self.level.price)

    @property
    def liquidity_score(self) -> float:
        return float(self.level.quality_score)

    def set_state(self, state: SweepState, now_ms: int, note: str | None = None) -> None:
        self.state = state
        self.updated_ms = now_ms
        if note:
            self.last_notes.append(note)
