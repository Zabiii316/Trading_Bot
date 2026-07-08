from __future__ import annotations

from math import exp

from .book_view import BookView, Level


def _safe_ratio(numerator: float, denominator: float) -> float:
    return 0.0 if denominator <= 0.0 else numerator / denominator


def queue_imbalance(book: BookView, levels: int = 1, decay_lambda: float | None = None) -> float | None:
    """Distance-weighted queue imbalance in [-1, 1].

    Positive means more visible bid depth than ask depth. Negative means more visible ask
    depth. This is a displayed-liquidity feature, not proof of executed pressure.
    """

    bids = book.top("bid", levels)
    asks = book.top("ask", levels)
    if not bids or not asks:
        return None

    bid_weighted = 0.0
    ask_weighted = 0.0
    for i, level in enumerate(bids):
        weight = exp(-(decay_lambda or 0.0) * i) if decay_lambda is not None else 1.0
        bid_weighted += weight * level.quantity
    for i, level in enumerate(asks):
        weight = exp(-(decay_lambda or 0.0) * i) if decay_lambda is not None else 1.0
        ask_weighted += weight * level.quantity

    total = bid_weighted + ask_weighted
    if total <= 0.0:
        return 0.0
    value = (bid_weighted - ask_weighted) / total
    return max(-1.0, min(1.0, value))


def best_level_ofi(previous: BookView | None, current: BookView) -> float | None:
    """Cont-style best-level order flow imbalance approximation.

    Positive values indicate bid strengthening and/or ask weakening. Negative values
    indicate bid weakening and/or ask strengthening.
    """

    if previous is None:
        return None
    pb = previous.best_bid
    pa = previous.best_ask
    cb = current.best_bid
    ca = current.best_ask
    if not (pb and pa and cb and ca):
        return None

    # Bid contribution.
    if cb.price > pb.price:
        bid_component = cb.quantity
    elif cb.price < pb.price:
        bid_component = -pb.quantity
    else:
        bid_component = cb.quantity - pb.quantity

    # Ask contribution. Lower ask is sell pressure, higher ask is buy pressure.
    if ca.price < pa.price:
        ask_component = -ca.quantity
    elif ca.price > pa.price:
        ask_component = pa.quantity
    else:
        ask_component = pa.quantity - ca.quantity

    return bid_component + ask_component


def _level_map(levels: tuple[Level, ...]) -> dict[float, float]:
    return {level.price: level.quantity for level in levels}


def depth_delta_ofi(previous: BookView | None, current: BookView, levels: int = 5) -> float | None:
    """Multi-level depth-delta OFI.

    It compares current and previous visible depth at the union of top-N prices. Bid
    additions and ask removals are positive; bid removals and ask additions are negative.
    """

    if previous is None:
        return None
    prev_bids = _level_map(previous.top("bid", levels))
    curr_bids = _level_map(current.top("bid", levels))
    prev_asks = _level_map(previous.top("ask", levels))
    curr_asks = _level_map(current.top("ask", levels))

    bid_prices = set(prev_bids) | set(curr_bids)
    ask_prices = set(prev_asks) | set(curr_asks)
    bid_change = sum(curr_bids.get(p, 0.0) - prev_bids.get(p, 0.0) for p in bid_prices)
    ask_change = sum(curr_asks.get(p, 0.0) - prev_asks.get(p, 0.0) for p in ask_prices)
    return bid_change - ask_change


def depth_depletion(previous: BookView | None, current: BookView, side: str, levels: int = 10) -> float | None:
    if previous is None:
        return None
    prev_depth = previous.depth_qty(side, levels)
    curr_depth = current.depth_qty(side, levels)
    if prev_depth <= 0.0:
        return None
    if curr_depth >= prev_depth:
        return 0.0
    return max(0.0, min(1.0, (prev_depth - curr_depth) / prev_depth))


def depth_replenishment(previous: BookView | None, current: BookView, side: str, levels: int = 10) -> float | None:
    if previous is None:
        return None
    prev_depth = previous.depth_qty(side, levels)
    curr_depth = current.depth_qty(side, levels)
    if prev_depth <= 0.0:
        return None
    if curr_depth <= prev_depth:
        return 0.0
    return max(0.0, (curr_depth - prev_depth) / prev_depth)
