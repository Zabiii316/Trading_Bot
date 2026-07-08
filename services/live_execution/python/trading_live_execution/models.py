from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from uuid import UUID

from trading_contracts.enums import OrderSide, OrderStatus, OrderType, TimeInForce
from trading_contracts.events import ExecutionFillEvent, ExecutionOrderEvent


class BinanceOrderStatus(str, Enum):
    NEW = "NEW"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCELED = "CANCELED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
    EXPIRED_IN_MATCH = "EXPIRED_IN_MATCH"


class BinanceExecutionType(str, Enum):
    NEW = "NEW"
    CANCELED = "CANCELED"
    CALCULATED = "CALCULATED"
    EXPIRED = "EXPIRED"
    TRADE = "TRADE"
    AMENDMENT = "AMENDMENT"


@dataclass(frozen=True, slots=True)
class BinanceOrderRequest:
    symbol: str
    side: OrderSide
    order_type: OrderType
    quantity: Decimal
    client_order_id: str
    time_in_force: TimeInForce | None = None
    limit_price: Decimal | None = None
    stop_price: Decimal | None = None
    reduce_only: bool = False
    position_side: str | None = None
    working_type: str | None = None


@dataclass(frozen=True, slots=True)
class BinanceOrderAck:
    symbol: str
    venue_order_id: str
    client_order_id: str
    status: BinanceOrderStatus
    raw: dict


@dataclass(slots=True)
class LiveOrderState:
    event: ExecutionOrderEvent
    created_time_ms: int
    last_update_ms: int
    filled_quantity: Decimal = Decimal("0")
    average_fill_price: Decimal = Decimal("0")
    cumulative_fee: Decimal = Decimal("0")
    raw_updates: list[dict] = field(default_factory=list)

    @property
    def order_id(self) -> UUID:
        return self.event.order_id

    @property
    def client_order_id(self) -> str:
        return self.event.client_order_id

    @property
    def is_open(self) -> bool:
        return self.event.status in {
            OrderStatus.SUBMITTED,
            OrderStatus.ACKNOWLEDGED,
            OrderStatus.PARTIALLY_FILLED,
            OrderStatus.CANCEL_PENDING,
        }


@dataclass(frozen=True, slots=True)
class ExchangeOrderSnapshot:
    symbol: str
    venue_order_id: str
    client_order_id: str
    status: BinanceOrderStatus
    side: str
    order_type: str
    original_quantity: Decimal
    executed_quantity: Decimal
    average_price: Decimal
    reduce_only: bool
    update_time_ms: int
    raw: dict


@dataclass(frozen=True, slots=True)
class ExchangePositionSnapshot:
    symbol: str
    position_amount: Decimal
    entry_price: Decimal
    mark_price: Decimal
    unrealized_pnl: Decimal
    leverage: Decimal | None = None
    isolated: bool | None = None
    raw: dict | None = None


@dataclass(frozen=True, slots=True)
class LiveReconciliationReport:
    event_time_ms: int
    local_open_order_count: int
    exchange_open_order_count: int
    local_position_symbols: tuple[str, ...]
    exchange_position_symbols: tuple[str, ...]
    discrepancies: tuple[str, ...] = ()

    @property
    def is_healthy(self) -> bool:
        return not self.discrepancies


@dataclass(frozen=True, slots=True)
class OrderUpdateResult:
    order_event: ExecutionOrderEvent | None = None
    fill_event: ExecutionFillEvent | None = None
    discrepancy: str | None = None
