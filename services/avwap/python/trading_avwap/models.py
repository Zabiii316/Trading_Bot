from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from math import sqrt
from uuid import UUID, uuid4

from trading_contracts.enums import SweepOutcome


class AnchorKind(str, Enum):
    STRUCTURAL = "structural"
    SESSION = "session"
    SWEEP_EVENT = "sweep_event"
    CUSTOM = "custom"


@dataclass(frozen=True, slots=True)
class AvwapUpdate:
    symbol: str
    event_time_ms: int
    received_time_ms: int
    venue: str
    market_type: str
    price: float
    quantity: float


@dataclass(slots=True)
class AvwapAnchor:
    """Incremental anchored VWAP accumulator.

    Maintains weighted sums only; no historical arrays are retained on the hot path.
    Variance is calculated as E[p^2] - E[p]^2 for deviation bands.
    """

    anchor_id: UUID
    symbol: str
    anchor_name: str
    anchor_kind: AnchorKind
    anchor_time_ms: int
    anchor_price: float
    created_ms: int
    sweep_id: UUID | None = None
    sweep_outcome: SweepOutcome | None = None
    sum_pv: float = 0.0
    sum_v: float = 0.0
    sum_p2v: float = 0.0
    trade_count: int = 0
    last_price: float | None = None
    last_event_time_ms: int | None = None
    last_avwap: float | None = None
    last_slope: float = 0.0
    last_side: int | None = None
    metadata: dict[str, str] = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        *,
        symbol: str,
        anchor_name: str,
        anchor_kind: AnchorKind,
        anchor_time_ms: int,
        anchor_price: float,
        created_ms: int,
        sweep_id: UUID | None = None,
        sweep_outcome: SweepOutcome | None = None,
    ) -> "AvwapAnchor":
        return cls(
            anchor_id=uuid4(),
            symbol=symbol.upper(),
            anchor_name=anchor_name,
            anchor_kind=anchor_kind,
            anchor_time_ms=anchor_time_ms,
            anchor_price=anchor_price,
            created_ms=created_ms,
            sweep_id=sweep_id,
            sweep_outcome=sweep_outcome,
        )

    def update(self, update: AvwapUpdate) -> None:
        if update.quantity <= 0 or update.price <= 0:
            return
        if update.event_time_ms < self.anchor_time_ms:
            return
        prev_avwap = self.avwap
        prev_time = self.last_event_time_ms
        self.sum_pv += update.price * update.quantity
        self.sum_v += update.quantity
        self.sum_p2v += update.price * update.price * update.quantity
        self.trade_count += 1
        self.last_price = update.price
        self.last_event_time_ms = update.event_time_ms
        if prev_avwap is not None and prev_time is not None and update.event_time_ms > prev_time:
            minutes = max((update.event_time_ms - prev_time) / 60_000.0, 1e-9)
            self.last_slope = (self.avwap - prev_avwap) / minutes if self.avwap is not None else 0.0
        self.last_avwap = self.avwap

    @property
    def avwap(self) -> float | None:
        if self.sum_v <= 0:
            return None
        return self.sum_pv / self.sum_v

    @property
    def variance(self) -> float | None:
        if self.sum_v <= 0:
            return None
        mean = self.sum_pv / self.sum_v
        var = (self.sum_p2v / self.sum_v) - (mean * mean)
        return max(var, 0.0)

    @property
    def sigma(self) -> float | None:
        var = self.variance
        if var is None:
            return None
        return sqrt(var)

    def current_side(self, price: float) -> int:
        avwap = self.avwap
        if avwap is None:
            return 0
        if price > avwap:
            return 1
        if price < avwap:
            return -1
        return 0

    def update_side_and_flags(self, price: float, bullish_bias: bool | None) -> tuple[bool, bool]:
        """Return reclaim/failure flags after comparing prior and current AVWAP side.

        For bullish bias, reclaim means crossing from below to above AVWAP; failure
        means crossing from above to below. For bearish bias, definitions invert.
        """
        current = self.current_side(price)
        previous = self.last_side
        self.last_side = current
        if previous is None or bullish_bias is None or previous == 0 or current == 0:
            return False, False
        if bullish_bias:
            return previous < 0 and current > 0, previous > 0 and current < 0
        return previous > 0 and current < 0, previous < 0 and current > 0
