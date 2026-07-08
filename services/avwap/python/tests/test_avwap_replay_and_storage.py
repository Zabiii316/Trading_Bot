from __future__ import annotations

import json
from decimal import Decimal
from uuid import uuid4

from trading_contracts.enums import AvwapConfirmation, EventType, MarketType, SweepOutcome, Venue
from trading_contracts.events import AnchoredVwapEvent
from trading_avwap.replay import replay_jsonl
from trading_storage.table_map import row_for_event, table_for_event


def base_event_payload(event_type: str, t: int = 1_000) -> dict:
    return {
        "event_type": event_type,
        "source": "test",
        "venue": "binance_usdm",
        "market_type": "perpetual_futures",
        "symbol": "BTCUSDT",
        "event_time_ms": t,
        "received_time_ms": t,
    }


def test_storage_mapping_for_avwap_event():
    event = AnchoredVwapEvent(
        event_type=EventType.ANCHORED_VWAP,
        source="test",
        venue=Venue.BINANCE_USDM,
        market_type=MarketType.PERPETUAL_FUTURES,
        symbol="BTCUSDT",
        event_time_ms=1_000,
        received_time_ms=1_000,
        anchor_name="sweep:test",
        anchor_type="sweep_event",
        anchor_time_ms=900,
        anchor_price=Decimal("100"),
        avwap=Decimal("100.5"),
        slope=Decimal("0.1"),
        upper_band_1=Decimal("101"),
        lower_band_1=Decimal("100"),
        band_z_score=Decimal("0.5"),
        distance_from_price_bps=Decimal("5"),
        confirmation=AvwapConfirmation.WEAK_BULLISH,
        confirmation_score=Decimal("0.65"),
        is_reclaim=True,
        sweep_id=uuid4(),
    )
    assert table_for_event(event) == "anchored_vwaps"
    row = row_for_event(event)
    assert row["anchor_type"] == "sweep_event"
    assert row["is_reclaim"] == 1
    assert row["confirmation_score"] == "0.65"


def test_jsonl_replay_emits_avwap(tmp_path):
    sid = str(uuid4())
    lines = [
        {
            **base_event_payload("liquidity.sweep", 1_000),
            "sweep_id": sid,
            "level_id": str(uuid4()),
            "state": "consumption_confirmed",
            "outcome": SweepOutcome.BULLISH_REJECTION.value,
            "level_price": "100",
            "sweep_extreme_price": "99.5",
            "liquidity_score": "0.8",
            "order_flow_score": "0.7",
        },
        {
            **base_event_payload("raw.agg_trade", 1_010),
            "agg_trade_id": 1,
            "price": "100",
            "quantity": "1",
            "first_trade_id": 1,
            "last_trade_id": 1,
            "trade_time_ms": 1_010,
            "is_buyer_maker": False,
            "aggressor_side": "buy",
        },
        {
            **base_event_payload("raw.agg_trade", 1_020),
            "agg_trade_id": 2,
            "price": "101",
            "quantity": "1",
            "first_trade_id": 2,
            "last_trade_id": 2,
            "trade_time_ms": 1_020,
            "is_buyer_maker": False,
            "aggressor_side": "buy",
        },
    ]
    path = tmp_path / "events.jsonl"
    path.write_text("\n".join(json.dumps(x) for x in lines), encoding="utf-8")
    out = replay_jsonl(path)
    assert out
    assert out[-1].event_type == EventType.ANCHORED_VWAP
