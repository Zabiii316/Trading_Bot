from decimal import Decimal
from uuid import UUID

import pytest
from pydantic import ValidationError
from trading_contracts.events import (
    DepthUpdateEvent,
    OrderFlowFeatureEvent,
    PriceLevel,
    RawAggTradeEvent,
    ReconstructedBookEvent,
    SignalEvent,
)


def base_payload(event_type: str) -> dict:
    return {
        "event_type": event_type,
        "source": "unit_test",
        "venue": "binance_usdm",
        "market_type": "perpetual_futures",
        "symbol": "btcusdt",
        "event_time_ms": 1_783_086_819_245,
        "received_time_ms": 1_783_086_819_250,
    }


def test_raw_agg_trade_validates_and_normalizes_symbol():
    event = RawAggTradeEvent.model_validate(
        {
            **base_payload("raw.agg_trade"),
            "agg_trade_id": 10,
            "price": "62175.80",
            "quantity": "0.001",
            "first_trade_id": 10,
            "last_trade_id": 12,
            "trade_time_ms": 1_783_086_819_245,
            "is_buyer_maker": True,
            "aggressor_side": "sell",
        }
    )
    assert event.symbol == "BTCUSDT"
    assert event.price == Decimal("62175.80")


def test_raw_agg_trade_rejects_bad_aggressor_side():
    with pytest.raises(ValidationError):
        RawAggTradeEvent.model_validate(
            {
                **base_payload("raw.agg_trade"),
                "agg_trade_id": 10,
                "price": "62175.80",
                "quantity": "0.001",
                "first_trade_id": 10,
                "last_trade_id": 12,
                "trade_time_ms": 1_783_086_819_245,
                "is_buyer_maker": True,
                "aggressor_side": "buy",
            }
        )


def test_depth_update_rejects_invalid_sequence():
    with pytest.raises(ValidationError):
        DepthUpdateEvent.model_validate(
            {
                **base_payload("raw.depth_update"),
                "first_update_id": 200,
                "final_update_id": 100,
                "bids": [{"price": "100", "quantity": "1"}],
                "asks": [{"price": "101", "quantity": "1"}],
            }
        )


def test_reconstructed_book_spread_must_match():
    event = ReconstructedBookEvent.model_validate(
        {
            **base_payload("book.reconstructed"),
            "last_update_id": 999,
            "best_bid": {"price": "100", "quantity": "2"},
            "best_ask": {"price": "100.5", "quantity": "2"},
            "spread": "0.5",
            "spread_bps": "50",
            "bid_depth_notional_10": "10000",
            "ask_depth_notional_10": "12000",
            "is_sequence_healthy": True,
        }
    )
    assert event.best_bid == PriceLevel(price=Decimal("100"), quantity=Decimal("2"))


def test_order_flow_delta_math():
    event = OrderFlowFeatureEvent.model_validate(
        {
            **base_payload("features.order_flow"),
            "window_ms": 1000,
            "trade_count": 10,
            "buy_volume": "7",
            "sell_volume": "3",
            "delta": "4",
            "normalized_delta": "0.4",
            "cumulative_volume_delta": "124",
        }
    )
    assert event.delta == Decimal("4")


def test_long_signal_requires_stop_below_entry():
    payload = {
        **base_payload("signal.generated"),
        "strategy_id": "sweep_orderflow_avwap_v1",
        "side": "long",
        "outcome": "bullish_rejection",
        "entry_candidate": "100",
        "stop": "99",
        "target_1": "102",
        "liquidity_score": "0.8",
        "order_flow_score": "0.7",
        "avwap_score": "0.7",
        "regime_score": "0.6",
        "execution_score": "0.8",
        "final_score": "0.74",
        "expected_net_return_bps": "10",
        "expires_at_ms": 1_783_086_879_245,
        "feature_snapshot_id": "00000000-0000-4000-8000-000000000001",
    }
    signal = SignalEvent.model_validate(payload)
    assert isinstance(signal.feature_snapshot_id, UUID)

    payload["stop"] = "101"
    with pytest.raises(ValidationError):
        SignalEvent.model_validate(payload)
