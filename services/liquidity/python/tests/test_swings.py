from trading_contracts.enums import MarketType, Venue
from trading_liquidity.models import Bar, PivotKind
from trading_liquidity.swings import SwingDetector, SwingDetectorConfig


def bar(i: int, high: float, low: float) -> Bar:
    return Bar(
        symbol="BTCUSDT",
        venue=Venue.BINANCE_USDM,
        market_type=MarketType.PERPETUAL_FUTURES,
        start_time_ms=i * 60_000,
        end_time_ms=(i + 1) * 60_000 - 1,
        open=(high + low) / 2,
        high=high,
        low=low,
        close=(high + low) / 2,
        volume=100,
    )


def test_swing_high_confirmed_after_right_bars():
    detector = SwingDetector(SwingDetectorConfig(left_strength=2, right_strength=2))
    highs = [10, 11, 15, 12, 11]
    lows = [8, 8, 9, 8, 8]
    pivots = []
    for i, (h, l) in enumerate(zip(highs, lows)):
        pivots.extend(detector.update(bar(i, h, l)))
    assert len(pivots) == 1
    assert pivots[0].kind == PivotKind.HIGH
    assert pivots[0].price == 15
    assert pivots[0].time_ms == 3 * 60_000 - 1
    assert pivots[0].confirmed_time_ms == 5 * 60_000 - 1


def test_swing_low_confirmed_after_right_bars():
    detector = SwingDetector(SwingDetectorConfig(left_strength=2, right_strength=2))
    lows = [10, 9, 5, 8, 9]
    highs = [12, 12, 11, 12, 12]
    pivots = []
    for i, (h, l) in enumerate(zip(highs, lows)):
        pivots.extend(detector.update(bar(i, h, l)))
    assert len(pivots) == 1
    assert pivots[0].kind == PivotKind.LOW
    assert pivots[0].price == 5
