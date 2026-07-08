from __future__ import annotations

from dataclasses import asdict
from typing import Any

from .engine import PaperExecutionEngine


def execution_snapshot(engine: PaperExecutionEngine) -> dict[str, Any]:
    open_orders = [order for order in engine.orders.values() if order.is_open]
    filled_orders = [order for order in engine.orders.values() if str(order.status) == "OrderStatus.FILLED" or getattr(order.status, "value", order.status) == "filled"]
    positions = list(engine.positions.values())
    return {
        "orders_total": len(engine.orders),
        "orders_open": len(open_orders),
        "orders_filled": len(filled_orders),
        "positions_total": len(positions),
        "open_notional_quote": sum(position.notional_quote for position in positions),
        "unrealized_pnl_quote": sum(position.unrealized_pnl_quote() for position in positions),
        "fees_quote": sum(position.fees_quote for position in positions),
    }
