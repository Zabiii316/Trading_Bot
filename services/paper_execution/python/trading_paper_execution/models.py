from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from math import isfinite
from uuid import UUID

from trading_contracts.enums import OrderSide, OrderStatus, OrderType, TimeInForce, TradeSide
from trading_contracts.events import ExecutionOrderEvent, SignalEvent


class OrderRejectReason(str, Enum):
    RISK_NOT_APPROVED = "risk_not_approved"
    BOOK_UNHEALTHY = "book_unhealthy"
    STALE_BOOK = "stale_book"
    INVALID_QUANTITY = "invalid_quantity"
    INVALID_PRICE = "invalid_price"
    DUPLICATE_SIGNAL = "duplicate_signal"
    KILL_SWITCH_ACTIVE = "kill_switch_active"
    NO_EXECUTABLE_BOOK = "no_executable_book"


class CancelReason(str, Enum):
    USER_CANCELLED = "user_cancelled"
    EXPIRED = "expired"
    KILL_SWITCH = "kill_switch"
    STALE_BOOK = "stale_book"
    RECONCILIATION_FAILURE = "reconciliation_failure"
    REPLACED = "replaced"


@dataclass(frozen=True, slots=True)
class PaperExecutionConfig:
    """Runtime parameters for the paper execution hot path.

    The defaults intentionally model marketable-limit taker fills with a small
    slippage buffer. The implementation is deterministic and exchange-agnostic;
    the live Binance adapter should later expose the same contracts.
    """

    fee_bps: float = 4.0
    slippage_bps: float = 1.0
    marketable_limit_buffer_bps: float = 2.0
    order_ttl_ms: int = 5_000
    max_book_age_ms: int = 2_000
    min_quantity: float = 0.0
    quantity_step: float = 0.0
    min_notional_quote: float = 0.0
    max_top_level_participation: float = 1.0
    allow_partial_fills: bool = True
    fill_latency_ms: int = 0
    fail_closed_on_unhealthy_book: bool = True

    def validate(self) -> None:
        numeric = {
            "fee_bps": self.fee_bps,
            "slippage_bps": self.slippage_bps,
            "marketable_limit_buffer_bps": self.marketable_limit_buffer_bps,
            "min_quantity": self.min_quantity,
            "quantity_step": self.quantity_step,
            "min_notional_quote": self.min_notional_quote,
            "max_top_level_participation": self.max_top_level_participation,
        }
        for name, value in numeric.items():
            if not isfinite(value) or value < 0:
                raise ValueError(f"{name} must be finite and non-negative")
        if self.order_ttl_ms < 0 or self.max_book_age_ms < 0 or self.fill_latency_ms < 0:
            raise ValueError("time parameters must be non-negative")
        if self.max_top_level_participation <= 0:
            raise ValueError("max_top_level_participation must be positive")


@dataclass(slots=True)
class PaperOrder:
    event: ExecutionOrderEvent
    created_time_ms: int
    expires_at_ms: int
    signal: SignalEvent
    remaining_quantity: float
    filled_quantity: float = 0.0
    average_fill_price: float = 0.0
    last_update_ms: int | None = None
    reject_reason: str | None = None
    cancel_reason: str | None = None

    @property
    def order_id(self) -> UUID:
        return self.event.order_id

    @property
    def client_order_id(self) -> str:
        return self.event.client_order_id

    @property
    def status(self) -> OrderStatus:
        return OrderStatus(self.event.status)

    @status.setter
    def status(self, value: OrderStatus) -> None:
        self.event.status = value.value  # type: ignore[misc]

    @property
    def side(self) -> OrderSide:
        return OrderSide(self.event.side)

    @property
    def quantity(self) -> float:
        return float(self.event.quantity)

    @property
    def limit_price(self) -> float | None:
        return float(self.event.limit_price) if self.event.limit_price is not None else None

    @property
    def is_open(self) -> bool:
        return self.status in {
            OrderStatus.CREATED,
            OrderStatus.RISK_APPROVED,
            OrderStatus.SUBMITTED,
            OrderStatus.ACKNOWLEDGED,
            OrderStatus.PARTIALLY_FILLED,
            OrderStatus.CANCEL_PENDING,
        }

    def apply_fill(self, *, price: float, quantity: float, event_time_ms: int) -> None:
        if quantity <= 0:
            return
        notional_before = self.average_fill_price * self.filled_quantity
        notional_after = notional_before + price * quantity
        self.filled_quantity += quantity
        self.remaining_quantity = max(0.0, self.remaining_quantity - quantity)
        self.average_fill_price = notional_after / self.filled_quantity
        self.last_update_ms = event_time_ms
        self.status = OrderStatus.FILLED if self.remaining_quantity <= 1e-12 else OrderStatus.PARTIALLY_FILLED


@dataclass(slots=True)
class PaperPosition:
    symbol: str
    side: TradeSide
    quantity: float
    average_entry_price: float
    strategy_id: str
    signal_id: UUID
    realized_pnl_quote: float = 0.0
    fees_quote: float = 0.0
    mark_price: float | None = None
    last_update_ms: int | None = None

    @property
    def signed_quantity(self) -> float:
        return self.quantity if self.side == TradeSide.LONG else -self.quantity

    @property
    def notional_quote(self) -> float:
        mark = self.mark_price if self.mark_price is not None else self.average_entry_price
        return abs(self.quantity * mark)

    def unrealized_pnl_quote(self, mark_price: float | None = None) -> float:
        mark = mark_price if mark_price is not None else self.mark_price
        if mark is None:
            return 0.0
        if self.side == TradeSide.LONG:
            return (mark - self.average_entry_price) * self.quantity
        return (self.average_entry_price - mark) * self.quantity


@dataclass(frozen=True, slots=True)
class FillResult:
    fill_price: float
    fill_quantity: float
    fee_quote: float
    remaining_quantity: float
    is_complete: bool
    book_update_id: int


@dataclass(frozen=True, slots=True)
class PositionReconciliationReport:
    event_time_ms: int
    open_order_count: int
    position_count: int
    discrepancies: tuple[str, ...] = field(default_factory=tuple)

    @property
    def is_healthy(self) -> bool:
        return not self.discrepancies
