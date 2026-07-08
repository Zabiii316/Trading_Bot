from decimal import Decimal

import pytest

from trading_contracts.events import PriceLevel
from trading_order_book.book import BookIntegrityError, LocalOrderBook, SideBook


def level(price: str, qty: str) -> PriceLevel:
    return PriceLevel(price=Decimal(price), quantity=Decimal(qty))


def test_bid_side_keeps_highest_price_first() -> None:
    bids = SideBook("bid")
    bids.apply_level(Decimal("100"), Decimal("1"))
    bids.apply_level(Decimal("101"), Decimal("2"))
    bids.apply_level(Decimal("99"), Decimal("3"))

    assert bids.best() == level("101", "2")
    assert [x.price for x in bids.top_n(3)] == [Decimal("101"), Decimal("100"), Decimal("99")]


def test_ask_side_keeps_lowest_price_first_and_removes_zero_qty() -> None:
    asks = SideBook("ask")
    asks.apply_level(Decimal("101"), Decimal("1"))
    asks.apply_level(Decimal("100"), Decimal("2"))
    asks.apply_level(Decimal("102"), Decimal("3"))
    asks.apply_level(Decimal("100"), Decimal("0"))

    assert asks.best() == level("101", "1")
    assert [x.price for x in asks.top_n(2)] == [Decimal("101"), Decimal("102")]


def test_local_book_rejects_crossed_state() -> None:
    book = LocalOrderBook("BTCUSDT")
    book.load_snapshot(
        last_update_id=10,
        bids=[level("100", "1")],
        asks=[level("101", "1")],
    )
    with pytest.raises(BookIntegrityError):
        book.apply_delta(update_id=11, bids=[level("102", "1")], asks=[])
