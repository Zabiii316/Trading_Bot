from decimal import Decimal
from uuid import uuid4

from trading_backtest.engine import EventDrivenBacktestEngine
from trading_backtest.models import BacktestConfig, ExitReason
from trading_contracts.enums import EventType, MarketType, SweepOutcome, TradeSide, Venue
from trading_contracts.events import PriceLevel, ReconstructedBookEvent, SignalEvent


def book(t=1_000, bid="100.00", ask="100.01"):
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


def signal(t=1_001, side=TradeSide.LONG, stop="99.50", target="100.75", expires=61_001):
    return SignalEvent(
        event_type=EventType.SIGNAL,
        source="test",
        venue=Venue.BINANCE_USDM,
        market_type=MarketType.PERPETUAL_FUTURES,
        symbol="BTCUSDT",
        event_time_ms=t,
        received_time_ms=t,
        signal_id=uuid4(),
        strategy_id="sweep_orderflow_avwap_v1",
        side=side,
        outcome=SweepOutcome.BULLISH_REJECTION if side == TradeSide.LONG else SweepOutcome.BEARISH_REJECTION,
        entry_candidate=Decimal("100.01"),
        stop=Decimal(stop),
        target_1=Decimal(target),
        target_2=Decimal("101.00") if side == TradeSide.LONG else Decimal("99.00"),
        liquidity_score=Decimal("0.8"),
        order_flow_score=Decimal("0.8"),
        avwap_score=Decimal("0.8"),
        regime_score=Decimal("0.7"),
        execution_score=Decimal("0.9"),
        final_score=Decimal("0.8"),
        expected_net_return_bps=Decimal("20"),
        expires_at_ms=expires,
        feature_snapshot_id=uuid4(),
        rationale=["test"],
    )


def test_long_signal_executes_after_latency_and_hits_target():
    engine = EventDrivenBacktestEngine(BacktestConfig(latency_ms=100, fee_bps=0, slippage_bps=0))
    engine.on_event(book(1_000))
    sig = signal(1_001)
    engine.on_event(sig)
    engine.on_event(book(1_050, "100.10", "100.11"))
    assert len(engine.state.open_positions) == 0
    engine.on_event(book(1_101, "100.10", "100.11"))
    assert len(engine.state.open_positions) == 1
    engine.on_event(book(1_200, "100.80", "100.81"))
    report = engine.finalize()
    assert report.summary.trade_count == 1
    trade = report.trades[0]
    assert trade.exit_reason == ExitReason.TARGET_1
    assert trade.net_pnl_quote > 0


def test_stop_loss_closes_position_with_loss_after_costs():
    engine = EventDrivenBacktestEngine(BacktestConfig(latency_ms=0, fee_bps=4, slippage_bps=1.5))
    engine.on_event(book(1_000))
    engine.on_event(signal(1_001))
    engine.on_event(book(1_002, "100.00", "100.01"))
    engine.on_event(book(1_003, "99.40", "99.41"))
    report = engine.finalize()
    assert report.summary.trade_count == 1
    assert report.trades[0].exit_reason == ExitReason.STOP
    assert report.trades[0].net_pnl_quote < 0
    assert report.summary.total_fees_quote > 0


def test_expired_signal_is_not_executed():
    engine = EventDrivenBacktestEngine(BacktestConfig(latency_ms=500))
    engine.on_event(book(1_000))
    engine.on_event(signal(1_001, expires=1_100))
    engine.on_event(book(1_600))
    report = engine.finalize()
    assert report.summary.trade_count == 0
    assert report.summary.expired_signal_count == 1


def test_short_signal_target():
    engine = EventDrivenBacktestEngine(BacktestConfig(latency_ms=0, fee_bps=0, slippage_bps=0))
    engine.on_event(book(1_000, "100.00", "100.01"))
    engine.on_event(signal(1_001, side=TradeSide.SHORT, stop="100.50", target="99.25"))
    engine.on_event(book(1_002, "100.00", "100.01"))
    engine.on_event(book(1_003, "99.20", "99.21"))
    report = engine.finalize()
    assert report.summary.trade_count == 1
    assert report.trades[0].side == TradeSide.SHORT
    assert report.trades[0].net_pnl_quote > 0
