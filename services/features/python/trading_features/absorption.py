from __future__ import annotations

from .rolling import RollingTradeWindow


def absorption_ratio(
    *,
    trade_window: RollingTradeWindow,
    previous_mid_price: float | None,
    current_mid_price: float | None,
    epsilon_price: float = 1e-9,
) -> float | None:
    """Aggressive volume per unit of price movement.

    Large values indicate that meaningful aggressive volume produced little price
    progress, which can be interpreted as potential absorption. This value is not capped
    because it is instrument and price-scale dependent; downstream scoring normalizes it
    by rolling distributions.
    """

    if previous_mid_price is None or current_mid_price is None:
        return None
    volume = trade_window.total_volume
    if volume <= 0.0:
        return 0.0
    price_move = abs(current_mid_price - previous_mid_price)
    return volume / max(price_move, epsilon_price)
