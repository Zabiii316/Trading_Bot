from __future__ import annotations

from trading_avwap.models import AnchorKind, AvwapAnchor, AvwapUpdate


def test_incremental_avwap_and_variance():
    anchor = AvwapAnchor.create(
        symbol="BTCUSDT",
        anchor_name="test",
        anchor_kind=AnchorKind.CUSTOM,
        anchor_time_ms=1_000,
        anchor_price=100.0,
        created_ms=1_000,
    )
    anchor.update(AvwapUpdate("BTCUSDT", 1_000, 1_000, "binance_usdm", "perpetual_futures", 100.0, 2.0))
    anchor.update(AvwapUpdate("BTCUSDT", 2_000, 2_000, "binance_usdm", "perpetual_futures", 110.0, 1.0))
    assert round(anchor.avwap, 8) == round((100 * 2 + 110) / 3, 8)
    assert anchor.sigma is not None
    assert anchor.trade_count == 2


def test_reclaim_and_failure_flags_are_bias_aware():
    anchor = AvwapAnchor.create(
        symbol="BTCUSDT",
        anchor_name="test",
        anchor_kind=AnchorKind.CUSTOM,
        anchor_time_ms=1_000,
        anchor_price=100.0,
        created_ms=1_000,
    )
    anchor.update(AvwapUpdate("BTCUSDT", 1_000, 1_000, "binance_usdm", "perpetual_futures", 100.0, 1.0))
    assert anchor.update_side_and_flags(99.0, bullish_bias=True) == (False, False)
    assert anchor.update_side_and_flags(101.0, bullish_bias=True) == (True, False)
    assert anchor.update_side_and_flags(99.0, bullish_bias=True) == (False, True)
