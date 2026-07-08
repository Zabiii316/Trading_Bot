from trading_contracts.enums import LiquidityLevelType, MarketType, Venue
from trading_liquidity.clustering import LiquidityClusterBook
from trading_liquidity.engine import LiquidityLevelEngine, LiquidityLevelEngineConfig
from trading_liquidity.models import Bar, CandidateLevel
from trading_liquidity.scoring import LiquidityQualityScorer
from trading_liquidity.tolerance import ToleranceModel, ZoneToleranceConfig


def test_cluster_absorbs_nearby_candidates():
    tol = ToleranceModel(ZoneToleranceConfig(min_ticks=4, tick_size=0.1, atr_fraction=0, volatility_fraction=0))
    book = LiquidityClusterBook(tol)
    c1 = CandidateLevel("BTCUSDT", Venue.BINANCE_USDM, MarketType.PERPETUAL_FUTURES, LiquidityLevelType.SWING_HIGH, 100.0, 1, "a")
    c2 = CandidateLevel("BTCUSDT", Venue.BINANCE_USDM, MarketType.PERPETUAL_FUTURES, LiquidityLevelType.SWING_HIGH, 100.2, 2, "b")
    cl1 = book.add(c1)
    cl2 = book.add(c2)
    assert cl1 is cl2
    assert cl2.touches == 2


def test_quality_score_increases_with_touches():
    tol = ToleranceModel(ZoneToleranceConfig(min_ticks=4, tick_size=0.1, atr_fraction=0, volatility_fraction=0))
    book = LiquidityClusterBook(tol)
    scorer = LiquidityQualityScorer()
    c1 = CandidateLevel("BTCUSDT", Venue.BINANCE_USDM, MarketType.PERPETUAL_FUTURES, LiquidityLevelType.SWING_LOW, 100.0, 1, "a", volume=10)
    c2 = CandidateLevel("BTCUSDT", Venue.BINANCE_USDM, MarketType.PERPETUAL_FUTURES, LiquidityLevelType.SWING_LOW, 100.1, 2, "b", volume=100)
    cl = book.add(c1)
    s1 = scorer.score(cl, 2)
    cl = book.add(c2)
    s2 = scorer.score(cl, 3)
    assert s2 > s1


def mkbar(i: int, high: float, low: float, close: float) -> Bar:
    return Bar(
        symbol="BTCUSDT",
        venue=Venue.BINANCE_USDM,
        market_type=MarketType.PERPETUAL_FUTURES,
        start_time_ms=i * 60_000,
        end_time_ms=(i + 1) * 60_000 - 1,
        open=close,
        high=high,
        low=low,
        close=close,
        volume=100 + i,
    )


def test_liquidity_engine_emits_contract_valid_levels():
    engine = LiquidityLevelEngine(LiquidityLevelEngineConfig(min_emit_score=0.0))
    bars = [
        mkbar(0, 100, 90, 95),
        mkbar(1, 101, 91, 96),
        mkbar(2, 110, 93, 105),
        mkbar(3, 102, 92, 96),
        mkbar(4, 101, 91, 95),
        mkbar(5, 103, 89, 92),
        mkbar(6, 104, 90, 93),
    ]
    events = []
    for b in bars:
        events.extend(engine.update(b))
    assert events
    assert all(e.price >= e.zone_low and e.price <= e.zone_high for e in events)
    assert any(e.level_type in {LiquidityLevelType.SWING_HIGH, LiquidityLevelType.ROUND_NUMBER} for e in events)
