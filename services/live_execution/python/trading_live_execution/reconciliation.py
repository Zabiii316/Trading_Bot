from __future__ import annotations

from decimal import Decimal

from .client import BinanceFuturesRestClient
from .engine import BinanceLiveExecutionAdapter
from .models import LiveReconciliationReport


class BinanceReconciler:
    """Compares internal live order state with Binance exchange snapshots."""

    def __init__(self, adapter: BinanceLiveExecutionAdapter, client: BinanceFuturesRestClient) -> None:
        self.adapter = adapter
        self.client = client

    async def reconcile(self, *, event_time_ms: int, symbol: str | None = None) -> LiveReconciliationReport:
        local_open = [
            state
            for state in self.adapter.orders.values()
            if state.is_open and (symbol is None or state.event.symbol == symbol.upper())
        ]
        exchange_open = await self.client.open_orders(symbol=symbol)
        exchange_by_client = {order.client_order_id: order for order in exchange_open}
        local_by_client = {state.client_order_id: state for state in local_open}

        discrepancies: list[str] = []
        for client_id, state in local_by_client.items():
            if client_id not in exchange_by_client:
                discrepancies.append(f"local_open_missing_on_exchange:{client_id}")
            else:
                exch = exchange_by_client[client_id]
                if exch.executed_quantity > state.event.quantity:
                    discrepancies.append(f"exchange_overfilled_local_quantity:{client_id}")
                if exch.reduce_only != bool(state.event.reduce_only):
                    discrepancies.append(f"reduce_only_mismatch:{client_id}")
        for client_id in exchange_by_client:
            if client_id not in local_by_client:
                discrepancies.append(f"exchange_open_missing_locally:{client_id}")

        exchange_positions = await self.client.position_risk(symbol=symbol)
        exchange_symbols = tuple(sorted(p.symbol for p in exchange_positions if p.position_amount != Decimal("0")))
        local_symbols = tuple(sorted({state.event.symbol for state in local_open}))
        return LiveReconciliationReport(
            event_time_ms=event_time_ms,
            local_open_order_count=len(local_open),
            exchange_open_order_count=len(exchange_open),
            local_position_symbols=local_symbols,
            exchange_position_symbols=exchange_symbols,
            discrepancies=tuple(discrepancies),
        )
