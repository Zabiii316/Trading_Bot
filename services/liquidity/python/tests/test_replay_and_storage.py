import json
from decimal import Decimal

from trading_contracts.enums import LiquidityLevelType, MarketType, Venue
from trading_contracts.events import LiquidityLevelEvent
from trading_liquidity.replay import load_bars_jsonl, replay_bars
from trading_storage.table_map import row_for_event, table_for_event


def test_replay_loads_bars(tmp_path):
    path = tmp_path / "bars.jsonl"
    rows = [
        {
            "symbol": "BTCUSDT",
            "venue": "binance_usdm",
            "market_type": "perpetual_futures",
            "start_time_ms": 0,
            "end_time_ms": 59999,
            "open": 100,
            "high": 101,
            "low": 99,
            "close": 100,
            "volume": 10,
        }
    ]
    path.write_text("\n".join(json.dumps(x) for x in rows))
    bars = list(load_bars_jsonl(path))
    assert len(bars) == 1
    assert bars[0].symbol == "BTCUSDT"


def test_liquidity_event_storage_mapping():
    ev = LiquidityLevelEvent(
        source="test",
        venue=Venue.BINANCE_USDM,
        market_type=MarketType.PERPETUAL_FUTURES,
        symbol="BTCUSDT",
        event_time_ms=1,
        received_time_ms=1,
        level_type=LiquidityLevelType.SWING_HIGH,
        price=Decimal("100"),
        zone_low=Decimal("99.5"),
        zone_high=Decimal("100.5"),
        quality_score=Decimal("0.75"),
        touches=3,
        first_seen_ms=1,
        last_seen_ms=2,
        metadata={"sources": ["test"]},
    )
    assert table_for_event(ev) == "liquidity_levels"
    row = row_for_event(ev)
    assert row["level_type"] == "swing_high"
    assert row["price"] == "100"
    assert row["metadata_json"]
