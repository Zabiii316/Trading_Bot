from __future__ import annotations

from decimal import Decimal
from uuid import UUID, uuid4

from trading_contracts.enums import (
    EventType,
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
    ReconstructedBookEvent,
    RiskDecisionEvent,
    SignalEvent,
)

from .models import (
    CancelReason,
    FillResult,
    OrderRejectReason,
    PaperExecutionConfig,
    PaperOrder,
    PaperPosition,
    PositionReconciliationReport,
)
from .pricing import (
    apply_slippage,
    executable_price_for_side,
    executable_quantity_for_side,
    fee_quote,
    marketable_limit_price,
    round_down_to_step,
    side_for_entry,
)


class PaperExecutionEngine:
    """Deterministic paper execution adapter.

    The engine has no network or database I/O on the hot path. It consumes
    approved RiskDecisionEvent objects with the matching SignalEvent, creates
    ExecutionOrderEvent objects, updates simulated orders from reconstructed
    books, emits ExecutionFillEvent objects and maintains a paper position
    ledger. The same event contracts are intended for later live execution.
    """

    __slots__ = (
        "config",
        "orders",
        "orders_by_client_id",
        "open_order_ids_by_symbol",
        "positions",
        "seen_signal_ids",
        "last_book_by_symbol",
        "_sequence",
    )

    def __init__(self, config: PaperExecutionConfig | None = None) -> None:
        self.config = config or PaperExecutionConfig()
        self.config.validate()
        self.orders: dict[UUID, PaperOrder] = {}
        self.orders_by_client_id: dict[str, UUID] = {}
        self.open_order_ids_by_symbol: dict[str, set[UUID]] = {}
        self.positions: dict[str, PaperPosition] = {}
        self.seen_signal_ids: set[UUID] = set()
        self.last_book_by_symbol: dict[str, ReconstructedBookEvent] = {}
        self._sequence = 0

    def submit(
        self,
        *,
        signal: SignalEvent,
        risk_decision: RiskDecisionEvent,
        book: ReconstructedBookEvent,
        event_time_ms: int | None = None,
    ) -> tuple[ExecutionOrderEvent | None, tuple[str, ...]]:
        """Create a paper order from an approved risk decision.

        Returns a contract event and rejection reasons. Rejections are returned
        as reasons instead of raising so replay loops can continue fail-closed.
        """
        now = event_time_ms if event_time_ms is not None else max(book.event_time_ms, risk_decision.event_time_ms)
        reasons = list(self._pre_submit_rejections(signal, risk_decision, book, now))
        if reasons:
            return None, tuple(reasons)

        side = side_for_entry(TradeSide(signal.side))
        quantity = round_down_to_step(float(risk_decision.approved_quantity), self.config.quantity_step)
        if quantity <= 0 or quantity < self.config.min_quantity:
            return None, (OrderRejectReason.INVALID_QUANTITY.value,)
        limit_price = marketable_limit_price(book, side, self.config.marketable_limit_buffer_bps)
        if quantity * limit_price < self.config.min_notional_quote:
            return None, (OrderRejectReason.INVALID_QUANTITY.value,)

        client_order_id = self._client_order_id(signal.signal_id)
        order_event = ExecutionOrderEvent(
            source="paper_execution",
            venue=Venue.PAPER,
            market_type=signal.market_type,
            symbol=signal.symbol,
            event_time_ms=now,
            received_time_ms=now,
            signal_id=signal.signal_id,
            risk_snapshot_id=risk_decision.risk_snapshot_id,
            side=side,
            order_type=OrderType.MARKETABLE_LIMIT,
            time_in_force=TimeInForce.IOC,
            status=OrderStatus.ACKNOWLEDGED,
            quantity=Decimal(str(quantity)),
            limit_price=Decimal(str(limit_price)),
            reduce_only=False,
            client_order_id=client_order_id,
        )
        order = PaperOrder(
            event=order_event,
            created_time_ms=now,
            expires_at_ms=min(signal.expires_at_ms, now + self.config.order_ttl_ms),
            signal=signal,
            remaining_quantity=quantity,
            last_update_ms=now,
        )
        self.orders[order.order_id] = order
        self.orders_by_client_id[client_order_id] = order.order_id
        self.open_order_ids_by_symbol.setdefault(signal.symbol.upper(), set()).add(order.order_id)
        self.seen_signal_ids.add(signal.signal_id)
        return order_event, ()

    def on_book(self, book: ReconstructedBookEvent) -> list[ExecutionFillEvent | ExecutionOrderEvent]:
        """Update open orders and positions from the latest reconstructed book."""
        self.last_book_by_symbol[book.symbol] = book
        events: list[ExecutionFillEvent | ExecutionOrderEvent] = []
        if self.config.fail_closed_on_unhealthy_book and not book.is_sequence_healthy:
            for order in list(self._open_orders_for_symbol(book.symbol)):
                cancel = self.cancel_order(order.order_id, CancelReason.STALE_BOOK, book.event_time_ms)
                if cancel is not None:
                    events.append(cancel)
            return events

        for order in list(self._open_orders_for_symbol(book.symbol)):
            if book.event_time_ms < order.created_time_ms + self.config.fill_latency_ms:
                continue
            if book.event_time_ms > order.expires_at_ms:
                cancel = self.cancel_order(order.order_id, CancelReason.EXPIRED, book.event_time_ms)
                if cancel is not None:
                    events.append(cancel)
                continue
            fill = self._try_fill_order(order, book)
            if fill is None:
                continue
            order.apply_fill(price=fill.fill_price, quantity=fill.fill_quantity, event_time_ms=book.event_time_ms)
            fill_event = self._fill_event_for(order, fill, book.event_time_ms)
            events.append(fill_event)
            self._apply_fill_to_position(order, fill, book.event_time_ms)
            if order.status in {OrderStatus.FILLED, OrderStatus.PARTIALLY_FILLED}:
                # Mutated order emits a lifecycle update after fill.
                order.event.event_time_ms = book.event_time_ms  # type: ignore[misc]
                order.event.received_time_ms = book.event_time_ms  # type: ignore[misc]
                events.append(order.event)
            if order.status == OrderStatus.FILLED:
                self._remove_open_order(order)
        return events

    def cancel_order(
        self,
        order_id: UUID,
        reason: CancelReason,
        event_time_ms: int,
    ) -> ExecutionOrderEvent | None:
        order = self.orders.get(order_id)
        if order is None or not order.is_open:
            return None
        order.status = OrderStatus.CANCELLED
        order.cancel_reason = reason.value
        order.last_update_ms = event_time_ms
        order.event.event_time_ms = event_time_ms  # type: ignore[misc]
        order.event.received_time_ms = event_time_ms  # type: ignore[misc]
        self._remove_open_order(order)
        return order.event

    def cancel_all(self, *, reason: CancelReason, event_time_ms: int, symbol: str | None = None) -> list[ExecutionOrderEvent]:
        events: list[ExecutionOrderEvent] = []
        for order in list(self.orders.values()):
            if symbol is not None and order.event.symbol != symbol.upper():
                continue
            cancel = self.cancel_order(order.order_id, reason, event_time_ms)
            if cancel is not None:
                events.append(cancel)
        return events

    def reconcile(self, *, event_time_ms: int) -> PositionReconciliationReport:
        discrepancies: list[str] = []
        if len(self.orders_by_client_id) != len(set(self.orders_by_client_id.keys())):
            discrepancies.append("duplicate_client_order_id")
        for order in self.orders.values():
            if order.remaining_quantity < -1e-9:
                discrepancies.append(f"negative_remaining_quantity:{order.client_order_id}")
            if order.filled_quantity - order.quantity > 1e-9:
                discrepancies.append(f"overfilled_order:{order.client_order_id}")
            if order.status == OrderStatus.FILLED and order.remaining_quantity > 1e-9:
                discrepancies.append(f"filled_order_has_remaining_quantity:{order.client_order_id}")
        for key, position in self.positions.items():
            if position.quantity <= 0:
                discrepancies.append(f"non_positive_position:{key}")
            if position.mark_price is not None and position.mark_price <= 0:
                discrepancies.append(f"invalid_mark_price:{key}")
        return PositionReconciliationReport(
            event_time_ms=event_time_ms,
            open_order_count=sum(1 for order in self.orders.values() if order.is_open),
            position_count=len(self.positions),
            discrepancies=tuple(discrepancies),
        )

    def mark_positions(self, book: ReconstructedBookEvent) -> None:
        key_long = self._position_key(book.symbol, TradeSide.LONG)
        key_short = self._position_key(book.symbol, TradeSide.SHORT)
        mark = (float(book.best_bid.price) + float(book.best_ask.price)) / 2.0
        if key_long in self.positions:
            self.positions[key_long].mark_price = mark
            self.positions[key_long].last_update_ms = book.event_time_ms
        if key_short in self.positions:
            self.positions[key_short].mark_price = mark
            self.positions[key_short].last_update_ms = book.event_time_ms

    def _pre_submit_rejections(
        self,
        signal: SignalEvent,
        risk_decision: RiskDecisionEvent,
        book: ReconstructedBookEvent,
        now: int,
    ) -> tuple[str, ...]:
        reasons: list[str] = []
        if risk_decision.status not in {RiskDecisionStatus.APPROVED, RiskDecisionStatus.REDUCED_SIZE}:
            reasons.append(OrderRejectReason.RISK_NOT_APPROVED.value)
        if risk_decision.signal_id != signal.signal_id:
            reasons.append("signal_risk_mismatch")
        if signal.signal_id in self.seen_signal_ids:
            reasons.append(OrderRejectReason.DUPLICATE_SIGNAL.value)
        if self.config.fail_closed_on_unhealthy_book and not book.is_sequence_healthy:
            reasons.append(OrderRejectReason.BOOK_UNHEALTHY.value)
        if now - book.event_time_ms > self.config.max_book_age_ms:
            reasons.append(OrderRejectReason.STALE_BOOK.value)
        if float(book.best_bid.price) <= 0 or float(book.best_ask.price) <= 0 or float(book.best_bid.price) > float(book.best_ask.price):
            reasons.append(OrderRejectReason.NO_EXECUTABLE_BOOK.value)
        if risk_decision.approved_quantity <= 0:
            reasons.append(OrderRejectReason.INVALID_QUANTITY.value)
        return tuple(reasons)

    def _try_fill_order(self, order: PaperOrder, book: ReconstructedBookEvent) -> FillResult | None:
        side = order.side
        reference = executable_price_for_side(book, side)
        limit = order.limit_price
        if limit is None:
            return None
        if side == OrderSide.BUY and limit + 1e-12 < reference:
            return None
        if side == OrderSide.SELL and limit - 1e-12 > reference:
            return None
        available = executable_quantity_for_side(book, side) * self.config.max_top_level_participation
        fill_quantity = min(order.remaining_quantity, available)
        if fill_quantity <= 0:
            return None
        if not self.config.allow_partial_fills and fill_quantity + 1e-12 < order.remaining_quantity:
            return None
        fill_price = apply_slippage(reference, side, self.config.slippage_bps)
        # Do not allow marketable-limit fill price beyond the limit.
        if side == OrderSide.BUY:
            fill_price = min(fill_price, limit)
        else:
            fill_price = max(fill_price, limit)
        fee = fee_quote(fill_price, fill_quantity, self.config.fee_bps)
        return FillResult(
            fill_price=fill_price,
            fill_quantity=fill_quantity,
            fee_quote=fee,
            remaining_quantity=max(0.0, order.remaining_quantity - fill_quantity),
            is_complete=fill_quantity + 1e-12 >= order.remaining_quantity,
            book_update_id=book.last_update_id,
        )

    def _fill_event_for(self, order: PaperOrder, fill: FillResult, event_time_ms: int) -> ExecutionFillEvent:
        return ExecutionFillEvent(
            source="paper_execution",
            venue=Venue.PAPER,
            market_type=order.event.market_type,
            symbol=order.event.symbol,
            event_time_ms=event_time_ms,
            received_time_ms=event_time_ms,
            order_id=order.order_id,
            client_order_id=order.client_order_id,
            venue_order_id=order.event.venue_order_id,
            side=order.side,
            fill_price=Decimal(str(fill.fill_price)),
            fill_quantity=Decimal(str(fill.fill_quantity)),
            fee_asset="USDT",
            fee_amount=Decimal(str(fill.fee_quote)),
            is_maker=False,
            liquidity_tag="paper_taker",
        )

    def _apply_fill_to_position(self, order: PaperOrder, fill: FillResult, event_time_ms: int) -> None:
        trade_side = TradeSide.LONG if order.side == OrderSide.BUY else TradeSide.SHORT
        key = self._position_key(order.event.symbol, trade_side)
        position = self.positions.get(key)
        if position is None:
            self.positions[key] = PaperPosition(
                symbol=order.event.symbol,
                side=trade_side,
                quantity=fill.fill_quantity,
                average_entry_price=fill.fill_price,
                strategy_id=order.signal.strategy_id,
                signal_id=order.signal.signal_id,
                fees_quote=fill.fee_quote,
                mark_price=fill.fill_price,
                last_update_ms=event_time_ms,
            )
            return
        total_qty = position.quantity + fill.fill_quantity
        position.average_entry_price = (
            position.average_entry_price * position.quantity + fill.fill_price * fill.fill_quantity
        ) / total_qty
        position.quantity = total_qty
        position.fees_quote += fill.fee_quote
        position.mark_price = fill.fill_price
        position.last_update_ms = event_time_ms

    def _open_orders_for_symbol(self, symbol: str) -> list[PaperOrder]:
        symbol = symbol.upper()
        ids = self.open_order_ids_by_symbol.get(symbol)
        if not ids:
            return []
        stale: list[UUID] = []
        orders: list[PaperOrder] = []
        for order_id in tuple(ids):
            order = self.orders.get(order_id)
            if order is None or not order.is_open:
                stale.append(order_id)
                continue
            orders.append(order)
        for order_id in stale:
            ids.discard(order_id)
        return orders

    def _remove_open_order(self, order: PaperOrder) -> None:
        ids = self.open_order_ids_by_symbol.get(order.event.symbol.upper())
        if ids is not None:
            ids.discard(order.order_id)
            if not ids:
                self.open_order_ids_by_symbol.pop(order.event.symbol.upper(), None)

    def _client_order_id(self, signal_id: UUID) -> str:
        self._sequence += 1
        return f"PAPER-{str(signal_id)[:8]}-{self._sequence:08d}"

    @staticmethod
    def _position_key(symbol: str, side: TradeSide) -> str:
        return f"{symbol.upper()}:{side.value}"
