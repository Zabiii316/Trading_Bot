from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

from trading_contracts.enums import OrderSide, TradeSide
from trading_contracts.events import ReconstructedBookEvent, SignalEvent

from .models import BacktestConfig, BacktestTrade, ExitReason, SimulatedPosition, order_side_for_trade_side, round_quantity


@dataclass(frozen=True, slots=True)
class FillEstimate:
    side: OrderSide
    price: float
    quantity: float
    fee_quote: float
    notional_quote: float
    book_update_id: int | None


class ExecutionSimulator:
    """Deterministic taker-fill simulator based on reconstructed best bid/ask.

    This is not a market-impact model. It is intentionally conservative for V1:
    entries and exits use the executable side of the reconstructed book plus a
    fixed slippage assumption. Later phases can replace this with queue-aware and
    depth-walking fill models without changing the replay engine contract.
    """

    __slots__ = ("config",)

    def __init__(self, config: BacktestConfig) -> None:
        config.validate()
        self.config = config

    def open_position(self, signal: SignalEvent, book: ReconstructedBookEvent, equity_quote: float) -> SimulatedPosition | None:
        side = TradeSide(signal.side)
        if side not in {TradeSide.LONG, TradeSide.SHORT}:
            return None
        entry_order_side = order_side_for_trade_side(side, is_entry=True)
        raw_entry_price = self._entry_reference_price(side, book)
        entry_price = self.apply_slippage(raw_entry_price, entry_order_side)
        stop = float(signal.stop)
        risk_per_unit = abs(entry_price - stop)
        if risk_per_unit <= 0:
            return None

        risk_budget_quote = equity_quote * self.config.risk_fraction_per_trade
        quantity = risk_budget_quote / risk_per_unit
        max_notional = equity_quote * self.config.max_notional_fraction * self.config.max_leverage
        quantity = min(quantity, max_notional / entry_price)
        quantity = round_quantity(quantity, self.config.quantity_step)
        if quantity <= 0 or quantity < self.config.min_quantity:
            return None
        if quantity * entry_price < self.config.min_notional:
            return None

        fee = self.fee(entry_price, quantity)
        return SimulatedPosition(
            position_id=uuid4(),
            signal=signal,
            side=side,
            quantity=quantity,
            entry_price=entry_price,
            entry_time_ms=book.event_time_ms,
            entry_fee_quote=fee,
            stop=stop,
            target_1=float(signal.target_1),
            target_2=float(signal.target_2) if signal.target_2 is not None else None,
            entry_book_update_id=book.last_update_id,
        )

    def should_exit(self, position: SimulatedPosition, book: ReconstructedBookEvent) -> tuple[ExitReason, float] | None:
        best_bid = float(book.best_bid.price)
        best_ask = float(book.best_ask.price)
        if position.side == TradeSide.LONG:
            stop_hit = best_bid <= position.stop
            target_hit = best_bid >= position.target_1
            if stop_hit and target_hit and self.config.conservative_intrabar_ordering:
                return ExitReason.STOP, position.stop
            if stop_hit:
                return ExitReason.STOP, position.stop
            if target_hit:
                return ExitReason.TARGET_1, position.target_1
        elif position.side == TradeSide.SHORT:
            stop_hit = best_ask >= position.stop
            target_hit = best_ask <= position.target_1
            if stop_hit and target_hit and self.config.conservative_intrabar_ordering:
                return ExitReason.STOP, position.stop
            if stop_hit:
                return ExitReason.STOP, position.stop
            if target_hit:
                return ExitReason.TARGET_1, position.target_1
        return None

    def close_position(
        self,
        position: SimulatedPosition,
        book: ReconstructedBookEvent,
        reason: ExitReason,
        reference_price: float | None = None,
    ) -> BacktestTrade:
        exit_side = order_side_for_trade_side(position.side, is_entry=False)
        reference = reference_price if reference_price is not None else self._exit_reference_price(position.side, book)
        exit_price = self.apply_slippage(reference, exit_side)
        exit_fee = self.fee(exit_price, position.quantity)
        if position.side == TradeSide.LONG:
            gross = (exit_price - position.entry_price) * position.quantity
            risk_per_unit = abs(position.entry_price - position.stop)
        else:
            gross = (position.entry_price - exit_price) * position.quantity
            risk_per_unit = abs(position.stop - position.entry_price)
        net = gross - position.entry_fee_quote - exit_fee
        notional = position.entry_price * position.quantity
        return_bps = (net / notional) * 10_000.0 if notional > 0 else 0.0
        r_multiple = net / max(risk_per_unit * position.quantity, 1e-12)
        return BacktestTrade(
            trade_id=uuid4(),
            signal_id=position.signal.signal_id,
            symbol=position.symbol,
            side=position.side,
            quantity=position.quantity,
            entry_price=position.entry_price,
            exit_price=exit_price,
            entry_time_ms=position.entry_time_ms,
            exit_time_ms=book.event_time_ms,
            entry_fee_quote=position.entry_fee_quote,
            exit_fee_quote=exit_fee,
            gross_pnl_quote=gross,
            net_pnl_quote=net,
            return_bps=return_bps,
            r_multiple=r_multiple,
            exit_reason=reason,
        )

    def fee(self, price: float, quantity: float) -> float:
        return abs(price * quantity) * (self.config.fee_bps / 10_000.0)

    def apply_slippage(self, price: float, side: OrderSide) -> float:
        slip = self.config.slippage_bps / 10_000.0
        if side == OrderSide.BUY:
            return price * (1.0 + slip)
        if side == OrderSide.SELL:
            return price * (1.0 - slip)
        raise ValueError(f"unsupported order side: {side}")

    @staticmethod
    def _entry_reference_price(side: TradeSide, book: ReconstructedBookEvent) -> float:
        return float(book.best_ask.price) if side == TradeSide.LONG else float(book.best_bid.price)

    @staticmethod
    def _exit_reference_price(side: TradeSide, book: ReconstructedBookEvent) -> float:
        return float(book.best_bid.price) if side == TradeSide.LONG else float(book.best_ask.price)
