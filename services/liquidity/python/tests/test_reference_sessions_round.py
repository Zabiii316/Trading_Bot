from trading_contracts.enums import LiquidityLevelType, MarketType, Venue
from trading_liquidity.models import Bar
from trading_liquidity.reference import ReferenceLevelEngine
from trading_liquidity.round_numbers import RoundNumberConfig, RoundNumberDetector
from trading_liquidity.sessions import SessionLevelEngine, SessionSpec


def mkbar(ms: int, high: float, low: float, close: float = 100.0) -> Bar:
    return Bar(
        symbol="BTCUSDT",
        venue=Venue.BINANCE_USDM,
        market_type=MarketType.PERPETUAL_FUTURES,
        start_time_ms=ms,
        end_time_ms=ms + 59_999,
        open=close,
        high=high,
        low=low,
        close=close,
        volume=100,
    )


def test_previous_day_levels_emit_on_day_rollover():
    engine = ReferenceLevelEngine()
    day1 = 1_704_067_200_000  # 2024-01-01 UTC
    day2 = day1 + 86_400_000
    assert engine.update(mkbar(day1, 110, 90)) == []
    out = engine.update(mkbar(day2, 105, 95))
    types = {x.level_type for x in out}
    assert LiquidityLevelType.PREVIOUS_DAY_HIGH in types
    assert LiquidityLevelType.PREVIOUS_DAY_LOW in types
    prices = {x.price for x in out}
    assert {110, 90}.issubset(prices)


def test_session_levels_emit_on_rollover():
    engine = SessionLevelEngine([SessionSpec("test", 0, 1)])
    base = 1_704_067_200_000
    assert engine.update(mkbar(base, 110, 90)) == []
    out = engine.update(mkbar(base + 86_400_000, 108, 92))
    assert len(out) == 2
    assert {x.level_type for x in out} == {LiquidityLevelType.SESSION_HIGH, LiquidityLevelType.SESSION_LOW}


def test_round_number_detector_deduplicates_nearby_levels():
    detector = RoundNumberDetector(RoundNumberConfig(step=100, levels_each_side=1, emit_distance_steps=1.0))
    out1 = detector.update(mkbar(0, 62130, 62050, close=62120))
    out2 = detector.update(mkbar(60_000, 62140, 62080, close=62130))
    assert any(x.price == 62100 for x in out1)
    assert out2 == []
