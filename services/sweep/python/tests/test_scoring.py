from decimal import Decimal

from trading_contracts.enums import EventType, MarketType, SweepOutcome, Venue
from trading_contracts.events import OrderFlowFeatureEvent
from trading_sweep.models import SweepDirection
from trading_sweep.scoring import SweepScorer


def feature(delta_positive: bool) -> OrderFlowFeatureEvent:
    buy, sell = (Decimal("8"), Decimal("2")) if delta_positive else (Decimal("2"), Decimal("8"))
    delta = buy - sell
    return OrderFlowFeatureEvent(
        event_type=EventType.ORDER_FLOW_FEATURE,
        source="test",
        venue=Venue.BINANCE_USDM,
        market_type=MarketType.PERPETUAL_FUTURES,
        symbol="BTCUSDT",
        event_time_ms=1,
        received_time_ms=1,
        window_ms=1000,
        trade_count=1,
        buy_volume=buy,
        sell_volume=sell,
        delta=delta,
        normalized_delta=delta / (buy + sell),
        cumulative_volume_delta=delta,
        ofi_l1=Decimal("10") if delta_positive else Decimal("-10"),
        ofi_l5=Decimal("10") if delta_positive else Decimal("-10"),
        absorption_ratio=Decimal("8"),
        depth_depletion_bid=Decimal("0.6"),
        depth_depletion_ask=Decimal("0.6"),
        depth_replenishment_bid=Decimal("2"),
        depth_replenishment_ask=Decimal("2"),
    )


def test_consumption_prefers_aligned_flow():
    scorer = SweepScorer()
    assert scorer.consumption_score(feature(True), SweepDirection.UPSIDE) > scorer.consumption_score(feature(False), SweepDirection.UPSIDE)
    assert scorer.consumption_score(feature(False), SweepDirection.DOWNSIDE) > scorer.consumption_score(feature(True), SweepDirection.DOWNSIDE)


def test_resolution_prefers_outcome_bias():
    scorer = SweepScorer()
    assert scorer.resolution_score(feature(True), SweepOutcome.BULLISH_REJECTION) > scorer.resolution_score(feature(False), SweepOutcome.BULLISH_REJECTION)
    assert scorer.resolution_score(feature(False), SweepOutcome.BEARISH_REJECTION) > scorer.resolution_score(feature(True), SweepOutcome.BEARISH_REJECTION)
