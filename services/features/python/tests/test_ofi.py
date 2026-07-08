from trading_features.book_view import BookView
from trading_features.ofi import (
    best_level_ofi,
    depth_delta_ofi,
    depth_depletion,
    depth_replenishment,
    queue_imbalance,
)


def book(bid_px=100.0, bid_qty=10.0, ask_px=100.1, ask_qty=8.0, update_id=1):
    return BookView.from_levels(
        symbol="BTCUSDT",
        venue="binance_usdm",
        market_type="perpetual_futures",
        event_time_ms=1000 + update_id,
        received_time_ms=1000 + update_id,
        last_update_id=update_id,
        bids=[(bid_px, bid_qty), (bid_px - 0.1, 5.0), (bid_px - 0.2, 3.0)],
        asks=[(ask_px, ask_qty), (ask_px + 0.1, 4.0), (ask_px + 0.2, 2.0)],
    )


def test_queue_imbalance() -> None:
    b = book(bid_qty=12, ask_qty=6)
    assert queue_imbalance(b, 1) == (12 - 6) / (12 + 6)


def test_best_level_ofi_same_price_size_changes() -> None:
    prev = book(bid_qty=10, ask_qty=8)
    curr = book(bid_qty=12, ask_qty=5, update_id=2)
    # bid +2, ask removal +3 => +5
    assert best_level_ofi(prev, curr) == 5.0


def test_best_level_ofi_price_move() -> None:
    prev = book(bid_px=100.0, bid_qty=10, ask_px=100.1, ask_qty=8)
    curr = book(bid_px=100.1, bid_qty=7, ask_px=100.2, ask_qty=9, update_id=2)
    assert best_level_ofi(prev, curr) == 15.0


def test_depth_delta_ofi_depletion_and_replenishment() -> None:
    prev = book(bid_qty=10, ask_qty=8)
    curr = BookView.from_levels(
        symbol="BTCUSDT",
        venue="binance_usdm",
        market_type="perpetual_futures",
        event_time_ms=1002,
        received_time_ms=1002,
        last_update_id=2,
        bids=[(100.0, 5.0), (99.9, 2.5), (99.8, 1.5)],
        asks=[(100.1, 12.0), (100.2, 8.0), (100.3, 4.0)],
    )
    assert depth_delta_ofi(prev, curr, 3) < 0
    assert round(depth_depletion(prev, curr, "bid", 3), 6) == round((18 - 9) / 18, 6)
    assert round(depth_replenishment(prev, curr, "ask", 3), 6) == round((24 - 14) / 14, 6)
