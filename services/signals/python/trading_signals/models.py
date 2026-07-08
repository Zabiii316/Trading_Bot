from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Sequence
from uuid import UUID

from trading_contracts.enums import SweepOutcome, TradeSide
from trading_contracts.events import (
    AnchoredVwapEvent,
    LiquiditySweepEvent,
    OrderFlowFeatureEvent,
    ReconstructedBookEvent,
)


class SignalDecision(str, Enum):
    READY = "ready"
    REJECTED = "rejected"
    WAITING_FOR_CONFIRMATION = "waiting_for_confirmation"
    DUPLICATE = "duplicate"


@dataclass(frozen=True, slots=True)
class RegimeSnapshot:
    """Small internal market-regime input.

    Phase 9 intentionally avoids introducing a new external RegimeEvent contract.
    Later phases can replace this with a streamed regime service without changing
    signal scoring semantics.
    """

    symbol: str
    score: float = 0.65
    name: str = "neutral_tradeable"
    is_tradeable: bool = True
    event_time_ms: int = 0
    reasons: tuple[str, ...] = ()

    def normalized_symbol(self) -> str:
        return self.symbol.upper()


@dataclass(frozen=True, slots=True)
class ExecutionSnapshot:
    symbol: str
    best_bid: float
    best_ask: float
    spread_bps: float
    bid_depth_notional_10: float
    ask_depth_notional_10: float
    is_sequence_healthy: bool
    event_time_ms: int

    @classmethod
    def from_book(cls, book: ReconstructedBookEvent) -> "ExecutionSnapshot":
        return cls(
            symbol=book.symbol,
            best_bid=float(book.best_bid.price),
            best_ask=float(book.best_ask.price),
            spread_bps=float(book.spread_bps),
            bid_depth_notional_10=float(book.bid_depth_notional_10),
            ask_depth_notional_10=float(book.ask_depth_notional_10),
            is_sequence_healthy=bool(book.is_sequence_healthy),
            event_time_ms=book.event_time_ms,
        )

    @property
    def mid_price(self) -> float:
        return (self.best_bid + self.best_ask) / 2.0


@dataclass(frozen=True, slots=True)
class SignalCandidate:
    sweep: LiquiditySweepEvent
    order_flow: OrderFlowFeatureEvent | None
    avwap: AnchoredVwapEvent | None
    execution: ExecutionSnapshot | None
    regime: RegimeSnapshot

    @property
    def symbol(self) -> str:
        return self.sweep.symbol

    @property
    def sweep_id(self) -> UUID:
        return self.sweep.sweep_id

    @property
    def side(self) -> TradeSide:
        outcome = self.sweep.outcome.value if hasattr(self.sweep.outcome, "value") else str(self.sweep.outcome)
        if outcome in {SweepOutcome.BULLISH_REJECTION.value, SweepOutcome.BULLISH_ACCEPTANCE.value}:
            return TradeSide.LONG
        if outcome in {SweepOutcome.BEARISH_REJECTION.value, SweepOutcome.BEARISH_ACCEPTANCE.value}:
            return TradeSide.SHORT
        return TradeSide.FLAT


@dataclass(slots=True)
class ScoreBreakdown:
    liquidity_score: float
    order_flow_score: float
    avwap_score: float
    regime_score: float
    execution_score: float
    final_score: float
    expected_net_return_bps: float
    rejection_reasons: list[str] = field(default_factory=list)
    rationale: list[str] = field(default_factory=list)

    @property
    def is_rejected(self) -> bool:
        return bool(self.rejection_reasons)


def as_tuple(values: Sequence[str]) -> tuple[str, ...]:
    return tuple(str(v) for v in values)
