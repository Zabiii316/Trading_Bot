from decimal import Decimal
from uuid import uuid4

from trading_contracts.enums import EventType, LiquidityLevelType, MarketType, SweepState, Venue
from trading_contracts.events import LiquidityLevelEvent, LiquiditySweepEvent
from trading_storage.table_map import row_for_event, table_for_event
from trading_sweep.replay import replay_file


def test_liquidity_sweep_storage_mapping():
    event = LiquiditySweepEvent(
        event_type=EventType.LIQUIDITY_SWEEP,
        source="test",
        venue=Venue.BINANCE_USDM,
        market_type=MarketType.PERPETUAL_FUTURES,
        symbol="BTCUSDT",
        event_time_ms=1,
        received_time_ms=1,
        sweep_id=uuid4(),
        level_id=uuid4(),
        state=SweepState.LEVEL_ARMED,
        level_price=Decimal("100"),
        liquidity_score=Decimal("0.8"),
    )
    assert table_for_event(event) == "liquidity_sweeps"
    row = row_for_event(event)
    assert row["state"] == "level_armed"
    assert row["level_price"] == "100"


def test_replay_file_ignores_unknown_events(tmp_path):
    level = LiquidityLevelEvent(
        event_type=EventType.LIQUIDITY_LEVEL,
        source="test",
        venue=Venue.BINANCE_USDM,
        market_type=MarketType.PERPETUAL_FUTURES,
        symbol="BTCUSDT",
        event_time_ms=1_000,
        received_time_ms=1_000,
        level_id=uuid4(),
        level_type=LiquidityLevelType.EQUAL_HIGHS,
        price=Decimal("100"),
        zone_low=Decimal("99.9"),
        zone_high=Decimal("100.1"),
        quality_score=Decimal("0.8"),
        touches=2,
        first_seen_ms=1,
        last_seen_ms=1_000,
    )
    path = tmp_path / "events.jsonl"
    path.write_text(level.model_dump_json() + "\n" + '{"event_type":"ignored"}' + "\n", encoding="utf-8")
    out = replay_file(path)
    assert len(out) == 1
    assert out[0].state == SweepState.LEVEL_ARMED
