from decimal import Decimal
from uuid import uuid4

from trading_contracts.enums import AvwapConfirmation, EventType, MarketType, SweepOutcome, SweepState, TradeSide, Venue
from trading_contracts.events import AnchoredVwapEvent, LiquiditySweepEvent, PriceLevel, ReconstructedBookEvent, SignalEvent
from trading_signals.replay import replay_file
from trading_storage.table_map import row_for_event, table_for_event


def test_signal_storage_mapping():
    signal = SignalEvent(
        event_type=EventType.SIGNAL,
        source="test",
        venue=Venue.BINANCE_USDM,
        market_type=MarketType.PERPETUAL_FUTURES,
        symbol="BTCUSDT",
        event_time_ms=1,
        received_time_ms=1,
        strategy_id="sweep_orderflow_avwap_v1",
        sweep_id=uuid4(),
        side=TradeSide.LONG,
        outcome=SweepOutcome.BULLISH_REJECTION,
        entry_candidate=Decimal("100"),
        stop=Decimal("99"),
        target_1=Decimal("101.25"),
        target_2=Decimal("102"),
        liquidity_score=Decimal("0.8"),
        order_flow_score=Decimal("0.8"),
        avwap_score=Decimal("0.8"),
        regime_score=Decimal("0.65"),
        execution_score=Decimal("0.9"),
        final_score=Decimal("0.795"),
        expected_net_return_bps=Decimal("30"),
        expires_at_ms=60_000,
        feature_snapshot_id=uuid4(),
        rationale=["test"],
    )
    assert table_for_event(signal) == "signals"
    row = row_for_event(signal)
    assert row["strategy_id"] == "sweep_orderflow_avwap_v1"
    assert row["side"] == "long"
    assert row["entry_candidate"] == "100"


def test_signal_replay_file(tmp_path):
    sid = uuid4()
    book = ReconstructedBookEvent(
        event_type=EventType.RECONSTRUCTED_BOOK,
        source="test",
        venue=Venue.BINANCE_USDM,
        market_type=MarketType.PERPETUAL_FUTURES,
        symbol="BTCUSDT",
        event_time_ms=1000,
        received_time_ms=1000,
        last_update_id=1,
        best_bid=PriceLevel(price=Decimal("100"), quantity=Decimal("100")),
        best_ask=PriceLevel(price=Decimal("100.01"), quantity=Decimal("100")),
        spread=Decimal("0.01"),
        spread_bps=Decimal("1"),
        bid_depth_notional_10=Decimal("100000"),
        ask_depth_notional_10=Decimal("100000"),
        is_sequence_healthy=True,
    )
    sweep = LiquiditySweepEvent(
        event_type=EventType.LIQUIDITY_SWEEP,
        source="test",
        venue=Venue.BINANCE_USDM,
        market_type=MarketType.PERPETUAL_FUTURES,
        symbol="BTCUSDT",
        event_time_ms=1001,
        received_time_ms=1001,
        sweep_id=sid,
        level_id=uuid4(),
        state=SweepState.ORDER_FLOW_CONFIRMED,
        outcome=SweepOutcome.BULLISH_REJECTION,
        level_price=Decimal("100"),
        sweep_extreme_price=Decimal("99.5"),
        liquidity_score=Decimal("0.85"),
        order_flow_score=Decimal("0.82"),
    )
    avwap = AnchoredVwapEvent(
        event_type=EventType.ANCHORED_VWAP,
        source="test",
        venue=Venue.BINANCE_USDM,
        market_type=MarketType.PERPETUAL_FUTURES,
        symbol="BTCUSDT",
        event_time_ms=1002,
        received_time_ms=1002,
        anchor_name="sweep",
        anchor_type="sweep_event",
        anchor_time_ms=999,
        anchor_price=Decimal("99.5"),
        avwap=Decimal("99.9"),
        slope=Decimal("0.1"),
        distance_from_price_bps=Decimal("5"),
        confirmation=AvwapConfirmation.STRONG_BULLISH,
        confirmation_score=Decimal("0.84"),
        is_reclaim=True,
        sweep_id=sid,
    )
    path = tmp_path / "events.jsonl"
    path.write_text(book.model_dump_json() + "\n" + sweep.model_dump_json() + "\n" + avwap.model_dump_json() + "\n", encoding="utf-8")
    out = replay_file(path)
    assert len(out) == 1
    assert out[0].sweep_id == sid
