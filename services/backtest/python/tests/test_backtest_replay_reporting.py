from decimal import Decimal
from uuid import uuid4

import pytest

from trading_backtest.models import BacktestConfig
from trading_backtest.replay import replay_backtest_file
from trading_backtest.reporting import format_summary
from trading_contracts.enums import AggressorSide, EventType, MarketType, SweepOutcome, TradeSide, Venue
from trading_contracts.events import PriceLevel, RawAggTradeEvent, ReconstructedBookEvent, SignalEvent


def book(t, bid, ask):
    return ReconstructedBookEvent(
        event_type=EventType.RECONSTRUCTED_BOOK,
        source="test",
        venue=Venue.BINANCE_USDM,
        market_type=MarketType.PERPETUAL_FUTURES,
        symbol="BTCUSDT",
        event_time_ms=t,
        received_time_ms=t,
        last_update_id=t,
        best_bid=PriceLevel(price=Decimal(bid), quantity=Decimal("100")),
        best_ask=PriceLevel(price=Decimal(ask), quantity=Decimal("100")),
        spread=Decimal(str(Decimal(ask) - Decimal(bid))),
        spread_bps=Decimal("1"),
        bid_depth_notional_10=Decimal("1000000"),
        ask_depth_notional_10=Decimal("1000000"),
        is_sequence_healthy=True,
    )


def agg_trade(t):
    return RawAggTradeEvent(
        event_type=EventType.RAW_AGG_TRADE,
        source="test",
        venue=Venue.BINANCE_USDM,
        market_type=MarketType.PERPETUAL_FUTURES,
        symbol="BTCUSDT",
        event_time_ms=t,
        received_time_ms=t,
        agg_trade_id=t,
        price=Decimal("100"),
        quantity=Decimal("1"),
        first_trade_id=t,
        last_trade_id=t,
        trade_time_ms=t,
        is_buyer_maker=False,
        aggressor_side=AggressorSide.BUY,
    )


def signal(t):
    return SignalEvent(
        event_type=EventType.SIGNAL,
        source="test",
        venue=Venue.BINANCE_USDM,
        market_type=MarketType.PERPETUAL_FUTURES,
        symbol="BTCUSDT",
        event_time_ms=t,
        received_time_ms=t,
        signal_id=uuid4(),
        strategy_id="test",
        side=TradeSide.LONG,
        outcome=SweepOutcome.BULLISH_REJECTION,
        entry_candidate=Decimal("100.01"),
        stop=Decimal("99.50"),
        target_1=Decimal("100.75"),
        target_2=Decimal("101.00"),
        liquidity_score=Decimal("0.8"),
        order_flow_score=Decimal("0.8"),
        avwap_score=Decimal("0.8"),
        regime_score=Decimal("0.7"),
        execution_score=Decimal("0.9"),
        final_score=Decimal("0.8"),
        expected_net_return_bps=Decimal("20"),
        expires_at_ms=t + 60_000,
        feature_snapshot_id=uuid4(),
        rationale=["test"],
    )


def test_replay_file_counts_all_events_and_reports_trade(tmp_path):
    path = tmp_path / "events.jsonl"
    events = [agg_trade(999), book(1000, "100.00", "100.01"), signal(1001), book(1002, "100.00", "100.01"), book(1003, "100.80", "100.81")]
    path.write_text("\n".join(e.model_dump_json() for e in events) + "\n", encoding="utf-8")
    report = replay_backtest_file(path, BacktestConfig(latency_ms=0, fee_bps=0, slippage_bps=0))
    assert report.summary.event_count == 5
    assert report.event_type_counts["raw.agg_trade"] == 1
    assert report.summary.trade_count == 1
    assert "Backtest Summary" in format_summary(report)


def test_replay_rejects_non_monotonic_events(tmp_path):
    path = tmp_path / "events.jsonl"
    events = [book(1000, "100", "100.01"), agg_trade(999)]
    path.write_text("\n".join(e.model_dump_json() for e in events) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="sorted"):
        replay_backtest_file(path)


def test_report_as_dict_is_json_serializable(tmp_path):
    path = tmp_path / "events.jsonl"
    events = [book(1000, "100", "100.01"), signal(1001), book(1002, "100", "100.01"), book(1003, "100.8", "100.81")]
    path.write_text("\n".join(e.model_dump_json() for e in events) + "\n", encoding="utf-8")
    report = replay_backtest_file(path, BacktestConfig(latency_ms=0, fee_bps=0, slippage_bps=0))
    payload = report.as_dict()
    assert payload["summary"]["trade_count"] == 1
    assert payload["trades"][0]["exit_reason"] == "target_1"
