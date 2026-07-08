from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from trading_contracts.enums import (
    EventType,
    KillSwitchLevel,
    MarketType,
    OrderSide,
    OrderStatus,
    OrderType,
    RiskDecisionStatus,
    TimeInForce,
    TradeSide,
    Venue,
)
from trading_contracts.events import (
    ExecutionFillEvent,
    ExecutionOrderEvent,
    KillSwitchEvent,
    RiskDecisionEvent,
    SignalEvent,
)

from .client import BinanceFuturesRestClient
from .config import BinanceLiveExecutionConfig
from .mapping import (
    closing_side_for_position,
    decimal_to_exchange,
    make_client_order_id,
    order_status_from_binance,
    side_for_signal,
    to_binance_order_params,
)
from .models import BinanceExecutionType, BinanceOrderRequest, LiveOrderState, OrderUpdateResult


class BinanceLiveExecutionAdapter:
    """Production-facing Binance execution adapter.

    The adapter intentionally has a narrow hot path: approved risk decisions are
    transformed to signed Binance order requests, acknowledgements mutate local
    order state, and exchange/user-stream updates are mapped back to the shared
    execution contracts used by the paper engine.
    """

    __slots__ = (
        "config",
        "client",
        "orders",
        "orders_by_client_id",
        "_sequence",
        "kill_switch_level",
        "kill_switch_reason",
    )

    def __init__(self, config: BinanceLiveExecutionConfig, client: BinanceFuturesRestClient) -> None:
        self.config = config
        self.client = client
        self.orders: dict[UUID, LiveOrderState] = {}
        self.orders_by_client_id: dict[str, UUID] = {}
        self._sequence = 0
        self.kill_switch_level = KillSwitchLevel.NONE
        self.kill_switch_reason = "none"

    def set_kill_switch(self, event: KillSwitchEvent) -> None:
        self.kill_switch_level = KillSwitchLevel(event.level) if event.is_active else KillSwitchLevel.NONE
        self.kill_switch_reason = event.reason if event.is_active else "none"

    async def submit_entry(
        self,
        *,
        signal: SignalEvent,
        risk_decision: RiskDecisionEvent,
        event_time_ms: int,
    ) -> tuple[ExecutionOrderEvent | None, tuple[str, ...]]:
        reasons = self._pre_submit_rejections(signal, risk_decision)
        if reasons:
            return None, reasons
        self._sequence += 1
        side = side_for_signal(TradeSide(signal.side))
        quantity = risk_decision.approved_quantity
        client_order_id = make_client_order_id(
            self.config.client_order_prefix,
            signal.signal_id,
            self._sequence,
            max_len=self.config.max_client_order_id_len,
        )
        order_event = ExecutionOrderEvent(
            source="binance_live_execution",
            venue=Venue.BINANCE_USDM,
            market_type=MarketType.PERPETUAL_FUTURES,
            symbol=signal.symbol,
            event_time_ms=event_time_ms,
            received_time_ms=event_time_ms,
            signal_id=signal.signal_id,
            risk_snapshot_id=risk_decision.risk_snapshot_id,
            side=side,
            order_type=OrderType.MARKETABLE_LIMIT,
            time_in_force=TimeInForce.IOC,
            status=OrderStatus.SUBMITTED,
            quantity=quantity,
            limit_price=signal.entry_candidate,
            reduce_only=False,
            client_order_id=client_order_id,
        )
        request = BinanceOrderRequest(
            symbol=signal.symbol,
            side=side,
            order_type=OrderType.MARKETABLE_LIMIT,
            time_in_force=TimeInForce.IOC,
            quantity=quantity,
            limit_price=signal.entry_candidate,
            reduce_only=False,
            client_order_id=client_order_id,
        )
        if not self.config.enable_live_trading:
            return None, ["live trading disabled"]

        ack = await self.client.place_order(
            to_binance_order_params(request, timestamp_ms=self.client.timestamp_ms(), config=self.config)
        )
        order_event.status = order_status_from_binance(ack.status.value)  # type: ignore[misc]
        order_event.venue_order_id = ack.venue_order_id  # type: ignore[misc]
        state = LiveOrderState(
            event=order_event,
            created_time_ms=event_time_ms,
            last_update_ms=event_time_ms,
            raw_updates=[ack.raw],
        )
        self.orders[order_event.order_id] = state
        self.orders_by_client_id[client_order_id] = order_event.order_id
        return order_event, ()

    async def submit_reduce_only_close(
        self,
        *,
        symbol: str,
        position_amount: Decimal,
        signal_id: UUID,
        risk_snapshot_id: UUID,
        event_time_ms: int,
        limit_price: Decimal | None = None,
    ) -> ExecutionOrderEvent:
        if position_amount == 0:
            raise ValueError("cannot close zero position")
        self._sequence += 1
        side = closing_side_for_position(position_amount)
        quantity = abs(position_amount)
        order_type = OrderType.MARKETABLE_LIMIT if limit_price is not None else OrderType.MARKET
        tif = TimeInForce.IOC if limit_price is not None else TimeInForce.GTC
        client_order_id = make_client_order_id(
            f"{self.config.client_order_prefix}ro",
            signal_id,
            self._sequence,
            max_len=self.config.max_client_order_id_len,
        )
        order_event = ExecutionOrderEvent(
            source="binance_live_execution",
            venue=Venue.BINANCE_USDM,
            market_type=MarketType.PERPETUAL_FUTURES,
            symbol=symbol,
            event_time_ms=event_time_ms,
            received_time_ms=event_time_ms,
            signal_id=signal_id,
            risk_snapshot_id=risk_snapshot_id,
            side=side,
            order_type=order_type,
            time_in_force=tif,
            status=OrderStatus.SUBMITTED,
            quantity=quantity,
            limit_price=limit_price,
            reduce_only=True,
            client_order_id=client_order_id,
        )
        request = BinanceOrderRequest(
            symbol=symbol,
            side=side,
            order_type=order_type,
            time_in_force=TimeInForce.IOC if order_type == OrderType.MARKETABLE_LIMIT else None,
            quantity=quantity,
            limit_price=limit_price,
            reduce_only=True,
            client_order_id=client_order_id,
        )
        ack = await self.client.place_order(
            to_binance_order_params(request, timestamp_ms=self.client.timestamp_ms(), config=self.config)
        )
        order_event.status = order_status_from_binance(ack.status.value)  # type: ignore[misc]
        order_event.venue_order_id = ack.venue_order_id  # type: ignore[misc]
        state = LiveOrderState(order_event, event_time_ms, event_time_ms, raw_updates=[ack.raw])
        self.orders[order_event.order_id] = state
        self.orders_by_client_id[client_order_id] = order_event.order_id
        return order_event

    async def cancel_order(self, *, order_id: UUID, event_time_ms: int) -> ExecutionOrderEvent | None:
        state = self.orders.get(order_id)
        if state is None or not state.is_open:
            return None
        state.event.status = OrderStatus.CANCEL_PENDING  # type: ignore[misc]
        snapshot = await self.client.cancel_order(
            symbol=state.event.symbol,
            orig_client_order_id=state.event.client_order_id,
        )
        state.event.status = order_status_from_binance(snapshot.status.value)  # type: ignore[misc]
        state.event.event_time_ms = event_time_ms  # type: ignore[misc]
        state.event.received_time_ms = event_time_ms  # type: ignore[misc]
        state.event.venue_order_id = snapshot.venue_order_id  # type: ignore[misc]
        state.last_update_ms = event_time_ms
        state.raw_updates.append(snapshot.raw)
        return state.event

    async def sync_order_status(self, *, order_id: UUID, event_time_ms: int) -> ExecutionOrderEvent | None:
        state = self.orders.get(order_id)
        if state is None:
            return None
        snapshot = await self.client.query_order(
            symbol=state.event.symbol,
            orig_client_order_id=state.event.client_order_id,
        )
        state.event.status = order_status_from_binance(snapshot.status.value)  # type: ignore[misc]
        state.event.event_time_ms = event_time_ms  # type: ignore[misc]
        state.event.received_time_ms = event_time_ms  # type: ignore[misc]
        state.event.venue_order_id = snapshot.venue_order_id  # type: ignore[misc]
        state.filled_quantity = snapshot.executed_quantity
        state.average_fill_price = snapshot.average_price
        state.last_update_ms = event_time_ms
        state.raw_updates.append(snapshot.raw)
        return state.event

    def on_order_trade_update(self, payload: dict) -> OrderUpdateResult:
        if payload.get("e") != "ORDER_TRADE_UPDATE":
            return OrderUpdateResult(discrepancy="unsupported_user_stream_event")
        order = payload.get("o", {})
        client_order_id = str(order.get("c") or "")
        order_id = self.orders_by_client_id.get(client_order_id)
        if order_id is None:
            return OrderUpdateResult(discrepancy=f"unknown_client_order_id:{client_order_id}")
        state = self.orders[order_id]
        status = order_status_from_binance(str(order.get("X", "NEW")))
        event_time_ms = int(payload.get("T") or payload.get("E") or state.last_update_ms)
        state.event.status = status  # type: ignore[misc]
        state.event.event_time_ms = event_time_ms  # type: ignore[misc]
        state.event.received_time_ms = event_time_ms  # type: ignore[misc]
        state.event.venue_order_id = str(order.get("i") or state.event.venue_order_id or "")  # type: ignore[misc]
        state.last_update_ms = event_time_ms
        state.raw_updates.append(payload)
        last_qty = Decimal(str(order.get("l") or "0"))
        fill_event: ExecutionFillEvent | None = None
        if str(order.get("x")) == BinanceExecutionType.TRADE.value and last_qty > 0:
            last_price = Decimal(str(order.get("L") or order.get("ap") or "0"))
            fee_amount = Decimal(str(order.get("n") or "0"))
            fill_event = ExecutionFillEvent(
                source="binance_live_execution",
                venue=Venue.BINANCE_USDM,
                market_type=state.event.market_type,
                symbol=state.event.symbol,
                event_time_ms=event_time_ms,
                received_time_ms=event_time_ms,
                order_id=state.order_id,
                client_order_id=client_order_id,
                venue_order_id=state.event.venue_order_id,
                side=state.event.side,
                fill_price=last_price,
                fill_quantity=last_qty,
                fee_asset=str(order.get("N") or "USDT"),
                fee_amount=fee_amount,
                is_maker=bool(order.get("m")) if order.get("m") is not None else None,
                liquidity_tag="maker" if bool(order.get("m")) else "taker",
            )
            state.filled_quantity = Decimal(str(order.get("z") or state.filled_quantity))
            state.average_fill_price = Decimal(str(order.get("ap") or state.average_fill_price))
            state.cumulative_fee += fee_amount
        return OrderUpdateResult(order_event=state.event, fill_event=fill_event)

    async def cancel_all_open(self, *, event_time_ms: int, symbol: str | None = None) -> list[ExecutionOrderEvent]:
        events: list[ExecutionOrderEvent] = []
        for state in list(self.orders.values()):
            if not state.is_open:
                continue
            if symbol is not None and state.event.symbol != symbol.upper():
                continue
            event = await self.cancel_order(order_id=state.order_id, event_time_ms=event_time_ms)
            if event is not None:
                events.append(event)
        return events

    def _pre_submit_rejections(self, signal: SignalEvent, risk_decision: RiskDecisionEvent) -> tuple[str, ...]:
        reasons: list[str] = []
        if self.kill_switch_level in {KillSwitchLevel.HARD_TRADING_HALT, KillSwitchLevel.EMERGENCY_FLATTEN}:
            reasons.append(f"kill_switch_active:{self.kill_switch_level.value}:{self.kill_switch_reason}")
        if risk_decision.status not in {RiskDecisionStatus.APPROVED, RiskDecisionStatus.REDUCED_SIZE}:
            reasons.append("risk_not_approved")
        if risk_decision.signal_id != signal.signal_id:
            reasons.append("risk_signal_mismatch")
        if risk_decision.approved_quantity <= 0:
            reasons.append("invalid_approved_quantity")
        if signal.signal_id in {
            state.event.signal_id for state in self.orders.values() if state.event.status != OrderStatus.REJECTED
        }:
            reasons.append("duplicate_signal")
        if not self.config.testnet and not self.config.enable_live_trading:
            reasons.append("live_trading_disabled")
        return tuple(reasons)
