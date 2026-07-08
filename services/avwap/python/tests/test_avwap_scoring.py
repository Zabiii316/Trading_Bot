from __future__ import annotations

from trading_contracts.enums import AvwapConfirmation, SweepOutcome
from trading_avwap.models import AnchorKind, AvwapAnchor, AvwapUpdate
from trading_avwap.scoring import AvwapScorer


def make_anchor():
    anchor = AvwapAnchor.create(
        symbol="BTCUSDT",
        anchor_name="sweep",
        anchor_kind=AnchorKind.SWEEP_EVENT,
        anchor_time_ms=1_000,
        anchor_price=100,
        created_ms=1_000,
        sweep_outcome=SweepOutcome.BULLISH_REJECTION,
    )
    anchor.update(AvwapUpdate("BTCUSDT", 1_000, 1_000, "binance_usdm", "perpetual_futures", 100, 10))
    anchor.update(AvwapUpdate("BTCUSDT", 2_000, 2_000, "binance_usdm", "perpetual_futures", 101, 10))
    return anchor


def test_bullish_confirmation_scores_above_avwap():
    score, confirmation, _, _ = AvwapScorer().score(anchor=make_anchor(), price=101.2, outcome=SweepOutcome.BULLISH_REJECTION, is_reclaim=True)
    assert score > 0
    assert confirmation in {AvwapConfirmation.WEAK_BULLISH, AvwapConfirmation.STRONG_BULLISH}


def test_failure_penalizes_score():
    anchor = make_anchor()
    good, _, _, _ = AvwapScorer().score(anchor=anchor, price=101.2, outcome=SweepOutcome.BULLISH_REJECTION, is_reclaim=True)
    bad, _, _, _ = AvwapScorer().score(anchor=anchor, price=99.0, outcome=SweepOutcome.BULLISH_REJECTION, is_failure=True)
    assert bad < good
