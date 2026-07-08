from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from trading_contracts.enums import OrderSide, OrderStatus, OrderType, TimeInForce, TradeSide

from .config import BinanceLiveExecutionConfig
from .models import BinanceOrderRequest, BinanceOrderStatus, ExchangeOrderSnapshot, ExchangePositionSnapshot


def decimal_to_exchange(value: Decimal) -> str:
    # Avoid scientific notation while preserving exchange-compatible precision.
    normalized = format(value.normalize(), "f")
    if "." in normalized:
        normalized = normalized.rstrip("0").rstrip(".")
    return normalized or "0"


def binance_side(side: OrderSide) -> str:
    return "BUY" if side == OrderSide.BUY else "SELL"


def binance_order_type(order_type: OrderType) -> str:
    if order_type == OrderType.MARKETABLE_LIMIT:
        return "LIMIT"
    return {
        OrderType.MARKET: "MARKET",
        OrderType.LIMIT: "LIMIT",
        OrderType.STOP_MARKET: "STOP_MARKET",
        OrderType.TAKE_PROFIT_MARKET: "TAKE_PROFIT_MARKET",
    }[order_type]


def binance_tif(time_in_force: TimeInForce | None) -> str | None:
    if time_in_force is None:
        return None
    return {
        TimeInForce.GTC: "GTC",
        TimeInForce.IOC: "IOC",
        TimeInForce.FOK: "FOK",
        TimeInForce.GTX: "GTX",
    }[time_in_force]


def order_status_from_binance(status: str) -> OrderStatus:
    try:
        parsed = BinanceOrderStatus(status)
    except ValueError:
        return OrderStatus.RECONCILIATION_REQUIRED
    return {
        BinanceOrderStatus.NEW: OrderStatus.ACKNOWLEDGED,
        BinanceOrderStatus.PARTIALLY_FILLED: OrderStatus.PARTIALLY_FILLED,
        BinanceOrderStatus.FILLED: OrderStatus.FILLED,
        BinanceOrderStatus.CANCELED: OrderStatus.CANCELLED,
        BinanceOrderStatus.REJECTED: OrderStatus.REJECTED,
        BinanceOrderStatus.EXPIRED: OrderStatus.EXPIRED,
        BinanceOrderStatus.EXPIRED_IN_MATCH: OrderStatus.EXPIRED,
    }[parsed]


def side_for_signal(signal_side: TradeSide) -> OrderSide:
    if signal_side == TradeSide.LONG:
        return OrderSide.BUY
    if signal_side == TradeSide.SHORT:
        return OrderSide.SELL
    raise ValueError("flat signal cannot be converted to entry side")


def closing_side_for_position(position_amount: Decimal) -> OrderSide:
    if position_amount > 0:
        return OrderSide.SELL
    if position_amount < 0:
        return OrderSide.BUY
    raise ValueError("zero position cannot be closed")


def to_binance_order_params(
    request: BinanceOrderRequest,
    *,
    timestamp_ms: int,
    config: BinanceLiveExecutionConfig,
) -> list[tuple[str, str | int | bool]]:
    params: list[tuple[str, str | int | bool]] = [
        ("symbol", request.symbol.upper()),
        ("side", binance_side(request.side)),
        ("type", binance_order_type(request.order_type)),
        ("quantity", decimal_to_exchange(request.quantity)),
        ("newClientOrderId", request.client_order_id),
        ("timestamp", timestamp_ms),
        ("recvWindow", config.recv_window_ms),
    ]
    tif = binance_tif(request.time_in_force)
    if tif is not None and binance_order_type(request.order_type) == "LIMIT":
        params.append(("timeInForce", tif))
    if request.limit_price is not None and binance_order_type(request.order_type) == "LIMIT":
        params.append(("price", decimal_to_exchange(request.limit_price)))
    if request.stop_price is not None:
        params.append(("stopPrice", decimal_to_exchange(request.stop_price)))
    if request.reduce_only:
        params.append(("reduceOnly", True))
    if request.position_side and not config.one_way_mode:
        params.append(("positionSide", request.position_side))
    if request.working_type:
        params.append(("workingType", request.working_type))
    return params


def parse_exchange_order(raw: dict) -> ExchangeOrderSnapshot:
    return ExchangeOrderSnapshot(
        symbol=str(raw.get("symbol") or raw.get("s") or "").upper(),
        venue_order_id=str(raw.get("orderId") or raw.get("i") or ""),
        client_order_id=str(raw.get("clientOrderId") or raw.get("origClientOrderId") or raw.get("c") or ""),
        status=BinanceOrderStatus(str(raw.get("status") or raw.get("X") or "NEW")),
        side=str(raw.get("side") or raw.get("S") or ""),
        order_type=str(raw.get("type") or raw.get("o") or ""),
        original_quantity=Decimal(str(raw.get("origQty") or raw.get("q") or "0")),
        executed_quantity=Decimal(str(raw.get("executedQty") or raw.get("z") or "0")),
        average_price=Decimal(str(raw.get("avgPrice") or raw.get("ap") or "0")),
        reduce_only=bool(raw.get("reduceOnly") if "reduceOnly" in raw else raw.get("R", False)),
        update_time_ms=int(raw.get("updateTime") or raw.get("T") or 0),
        raw=raw,
    )


def parse_position(raw: dict) -> ExchangePositionSnapshot:
    return ExchangePositionSnapshot(
        symbol=str(raw.get("symbol") or "").upper(),
        position_amount=Decimal(str(raw.get("positionAmt") or "0")),
        entry_price=Decimal(str(raw.get("entryPrice") or "0")),
        mark_price=Decimal(str(raw.get("markPrice") or "0")),
        unrealized_pnl=Decimal(str(raw.get("unRealizedProfit") or raw.get("unrealizedPnl") or "0")),
        leverage=Decimal(str(raw["leverage"])) if raw.get("leverage") is not None else None,
        isolated=bool(raw.get("isolated")) if raw.get("isolated") is not None else None,
        raw=raw,
    )


def make_client_order_id(prefix: str, signal_id: UUID, sequence: int, *, max_len: int = 36) -> str:
    raw = f"{prefix}-{signal_id.hex[:20]}-{sequence:04d}"
    return raw[:max_len]
