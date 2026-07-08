from __future__ import annotations

from math import floor

from trading_contracts.enums import OrderSide, TradeSide
from trading_contracts.events import ReconstructedBookEvent


def round_down_to_step(value: float, step: float) -> float:
    if step <= 0:
        return value
    return floor(value / step) * step


def side_for_entry(trade_side: TradeSide) -> OrderSide:
    if trade_side == TradeSide.LONG:
        return OrderSide.BUY
    if trade_side == TradeSide.SHORT:
        return OrderSide.SELL
    raise ValueError(f"unsupported trade side: {trade_side}")


def executable_price_for_side(book: ReconstructedBookEvent, side: OrderSide) -> float:
    if side == OrderSide.BUY:
        return float(book.best_ask.price)
    if side == OrderSide.SELL:
        return float(book.best_bid.price)
    raise ValueError(f"unsupported side: {side}")


def executable_quantity_for_side(book: ReconstructedBookEvent, side: OrderSide) -> float:
    if side == OrderSide.BUY:
        return float(book.best_ask.quantity)
    if side == OrderSide.SELL:
        return float(book.best_bid.quantity)
    raise ValueError(f"unsupported side: {side}")


def marketable_limit_price(book: ReconstructedBookEvent, side: OrderSide, buffer_bps: float) -> float:
    reference = executable_price_for_side(book, side)
    buffer = buffer_bps / 10_000.0
    if side == OrderSide.BUY:
        return reference * (1.0 + buffer)
    return reference * (1.0 - buffer)


def apply_slippage(price: float, side: OrderSide, slippage_bps: float) -> float:
    slip = slippage_bps / 10_000.0
    if side == OrderSide.BUY:
        return price * (1.0 + slip)
    return price * (1.0 - slip)


def fee_quote(price: float, quantity: float, fee_bps: float) -> float:
    return abs(price * quantity) * (fee_bps / 10_000.0)
