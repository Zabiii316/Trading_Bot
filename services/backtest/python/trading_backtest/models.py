from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from math import isfinite, sqrt
from statistics import mean, pstdev
from uuid import UUID, uuid4

from trading_contracts.enums import OrderSide, TradeSide
from trading_contracts.events import ReconstructedBookEvent, SignalEvent


class ExitReason(str, Enum):
    TARGET_1 = "target_1"
    TARGET_2 = "target_2"
    STOP = "stop"
    EXPIRED = "expired"
    END_OF_REPLAY = "end_of_replay"
    MANUAL = "manual"


class PendingSignalStatus(str, Enum):
    PENDING = "pending"
    EXECUTED = "executed"
    EXPIRED = "expired"
    REJECTED = "rejected"


@dataclass(frozen=True, slots=True)
class BacktestConfig:
    """Execution and accounting assumptions for deterministic replay.

    The defaults are intentionally conservative for taker-style simulated fills.
    All basis-point values are per side unless explicitly documented.
    """

    initial_equity_quote: float = 100_000.0
    risk_fraction_per_trade: float = 0.0025
    max_notional_fraction: float = 1.0
    max_leverage: float = 2.0
    fee_bps: float = 4.0
    slippage_bps: float = 1.5
    latency_ms: int = 250
    reject_stale_signals: bool = True
    close_open_positions_on_end: bool = True
    conservative_intrabar_ordering: bool = True
    min_quantity: float = 0.0
    quantity_step: float = 0.0
    min_notional: float = 0.0

    def validate(self) -> None:
        if self.initial_equity_quote <= 0:
            raise ValueError("initial_equity_quote must be positive")
        if not (0 < self.risk_fraction_per_trade <= 1):
            raise ValueError("risk_fraction_per_trade must be in (0, 1]")
        if self.max_notional_fraction <= 0:
            raise ValueError("max_notional_fraction must be positive")
        if self.max_leverage <= 0:
            raise ValueError("max_leverage must be positive")
        if self.fee_bps < 0 or self.slippage_bps < 0:
            raise ValueError("fee_bps and slippage_bps cannot be negative")
        if self.latency_ms < 0:
            raise ValueError("latency_ms cannot be negative")
        if self.min_quantity < 0 or self.quantity_step < 0 or self.min_notional < 0:
            raise ValueError("quantity constraints cannot be negative")


@dataclass(slots=True)
class PendingSignal:
    signal: SignalEvent
    release_time_ms: int
    status: PendingSignalStatus = PendingSignalStatus.PENDING
    reason: str | None = None


@dataclass(slots=True)
class SimulatedPosition:
    position_id: UUID
    signal: SignalEvent
    side: TradeSide
    quantity: float
    entry_price: float
    entry_time_ms: int
    entry_fee_quote: float
    stop: float
    target_1: float
    target_2: float | None = None
    entry_book_update_id: int | None = None

    @property
    def symbol(self) -> str:
        return self.signal.symbol

    @property
    def notional(self) -> float:
        return abs(self.quantity * self.entry_price)


@dataclass(frozen=True, slots=True)
class BacktestTrade:
    trade_id: UUID
    signal_id: UUID
    symbol: str
    side: TradeSide
    quantity: float
    entry_price: float
    exit_price: float
    entry_time_ms: int
    exit_time_ms: int
    entry_fee_quote: float
    exit_fee_quote: float
    gross_pnl_quote: float
    net_pnl_quote: float
    return_bps: float
    r_multiple: float
    exit_reason: ExitReason
    max_favorable_excursion_bps: float = 0.0
    max_adverse_excursion_bps: float = 0.0

    @property
    def is_winner(self) -> bool:
        return self.net_pnl_quote > 0


@dataclass(slots=True)
class EquityPoint:
    event_time_ms: int
    equity_quote: float
    realized_pnl_quote: float
    open_positions: int


@dataclass(frozen=True, slots=True)
class BacktestSummary:
    initial_equity_quote: float
    final_equity_quote: float
    net_pnl_quote: float
    net_return_pct: float
    trade_count: int
    win_count: int
    loss_count: int
    win_rate: float
    gross_profit_quote: float
    gross_loss_quote: float
    profit_factor: float
    average_trade_pnl_quote: float
    average_win_quote: float
    average_loss_quote: float
    max_drawdown_quote: float
    max_drawdown_pct: float
    sharpe_per_trade: float
    expectancy_quote: float
    total_fees_quote: float
    rejected_signal_count: int
    expired_signal_count: int
    event_count: int


@dataclass(slots=True)
class BacktestReport:
    config: BacktestConfig
    summary: BacktestSummary
    trades: list[BacktestTrade]
    equity_curve: list[EquityPoint]
    event_type_counts: dict[str, int] = field(default_factory=dict)
    rejected_signals: list[tuple[UUID, str]] = field(default_factory=list)
    expired_signals: list[tuple[UUID, str]] = field(default_factory=list)

    def as_dict(self) -> dict[str, object]:
        return {
            "summary": asdict(self.summary),
            "event_type_counts": dict(self.event_type_counts),
            "rejected_signals": [(str(sid), reason) for sid, reason in self.rejected_signals],
            "expired_signals": [(str(sid), reason) for sid, reason in self.expired_signals],
            "trades": [
                {
                    "trade_id": str(t.trade_id),
                    "signal_id": str(t.signal_id),
                    "symbol": t.symbol,
                    "side": t.side.value if hasattr(t.side, "value") else str(t.side),
                    "quantity": t.quantity,
                    "entry_price": t.entry_price,
                    "exit_price": t.exit_price,
                    "entry_time_ms": t.entry_time_ms,
                    "exit_time_ms": t.exit_time_ms,
                    "entry_fee_quote": t.entry_fee_quote,
                    "exit_fee_quote": t.exit_fee_quote,
                    "gross_pnl_quote": t.gross_pnl_quote,
                    "net_pnl_quote": t.net_pnl_quote,
                    "return_bps": t.return_bps,
                    "r_multiple": t.r_multiple,
                    "exit_reason": t.exit_reason.value,
                    "max_favorable_excursion_bps": t.max_favorable_excursion_bps,
                    "max_adverse_excursion_bps": t.max_adverse_excursion_bps,
                }
                for t in self.trades
            ],
            "equity_curve": [asdict(p) for p in self.equity_curve],
        }


def order_side_for_trade_side(side: TradeSide, *, is_entry: bool) -> OrderSide:
    if side == TradeSide.LONG:
        return OrderSide.BUY if is_entry else OrderSide.SELL
    if side == TradeSide.SHORT:
        return OrderSide.SELL if is_entry else OrderSide.BUY
    raise ValueError(f"unsupported trade side: {side}")


def round_quantity(quantity: float, step: float) -> float:
    if step <= 0:
        return quantity
    return (quantity // step) * step


def summarize(
    *,
    config: BacktestConfig,
    trades: list[BacktestTrade],
    equity_curve: list[EquityPoint],
    rejected_signal_count: int,
    expired_signal_count: int,
    event_count: int,
) -> BacktestSummary:
    final_equity = equity_curve[-1].equity_quote if equity_curve else config.initial_equity_quote
    pnl = final_equity - config.initial_equity_quote
    wins = [t for t in trades if t.net_pnl_quote > 0]
    losses = [t for t in trades if t.net_pnl_quote < 0]
    gross_profit = sum(t.net_pnl_quote for t in wins)
    gross_loss = abs(sum(t.net_pnl_quote for t in losses))
    trade_pnls = [t.net_pnl_quote for t in trades]
    trade_returns = [t.return_bps / 10_000.0 for t in trades]
    if gross_loss == 0 and gross_profit > 0:
        profit_factor = float("inf")
    elif gross_loss == 0:
        profit_factor = 0.0
    else:
        profit_factor = gross_profit / gross_loss

    avg = mean(trade_pnls) if trade_pnls else 0.0
    avg_win = mean([t.net_pnl_quote for t in wins]) if wins else 0.0
    avg_loss = mean([t.net_pnl_quote for t in losses]) if losses else 0.0
    sharpe = 0.0
    if len(trade_returns) >= 2:
        std = pstdev(trade_returns)
        if std > 0 and isfinite(std):
            sharpe = mean(trade_returns) / std * sqrt(len(trade_returns))

    max_dd_quote, max_dd_pct = drawdown(equity_curve, config.initial_equity_quote)
    total_fees = sum(t.entry_fee_quote + t.exit_fee_quote for t in trades)
    return BacktestSummary(
        initial_equity_quote=config.initial_equity_quote,
        final_equity_quote=final_equity,
        net_pnl_quote=pnl,
        net_return_pct=(pnl / config.initial_equity_quote) * 100.0,
        trade_count=len(trades),
        win_count=len(wins),
        loss_count=len(losses),
        win_rate=(len(wins) / len(trades)) if trades else 0.0,
        gross_profit_quote=gross_profit,
        gross_loss_quote=gross_loss,
        profit_factor=profit_factor,
        average_trade_pnl_quote=avg,
        average_win_quote=avg_win,
        average_loss_quote=avg_loss,
        max_drawdown_quote=max_dd_quote,
        max_drawdown_pct=max_dd_pct,
        sharpe_per_trade=sharpe,
        expectancy_quote=avg,
        total_fees_quote=total_fees,
        rejected_signal_count=rejected_signal_count,
        expired_signal_count=expired_signal_count,
        event_count=event_count,
    )


def drawdown(equity_curve: list[EquityPoint], initial_equity: float) -> tuple[float, float]:
    peak = initial_equity
    max_dd = 0.0
    max_dd_pct = 0.0
    for point in equity_curve:
        equity = point.equity_quote
        if equity > peak:
            peak = equity
        dd = peak - equity
        if dd > max_dd:
            max_dd = dd
            max_dd_pct = (dd / peak) * 100.0 if peak > 0 else 0.0
    return max_dd, max_dd_pct
