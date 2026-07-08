from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from uuid import UUID

from trading_contracts.enums import EventType
from trading_contracts.events import EventEnvelope, ReconstructedBookEvent, SignalEvent

from .execution import ExecutionSimulator
from .models import (
    BacktestConfig,
    BacktestReport,
    BacktestTrade,
    EquityPoint,
    ExitReason,
    PendingSignal,
    PendingSignalStatus,
    SimulatedPosition,
    summarize,
)


@dataclass(slots=True)
class BacktestState:
    equity_quote: float
    realized_pnl_quote: float = 0.0
    latest_book: dict[str, ReconstructedBookEvent] = field(default_factory=dict)
    pending_signals: list[PendingSignal] = field(default_factory=list)
    open_positions: dict[UUID, SimulatedPosition] = field(default_factory=dict)
    trades: list[BacktestTrade] = field(default_factory=list)
    equity_curve: list[EquityPoint] = field(default_factory=list)
    event_type_counts: Counter[str] = field(default_factory=Counter)
    rejected_signals: list[tuple[UUID, str]] = field(default_factory=list)
    expired_signals: list[tuple[UUID, str]] = field(default_factory=list)
    last_event_time_ms: int = 0


class EventDrivenBacktestEngine:
    """Deterministic event-driven replay and execution simulator.

    The engine accepts every contract event type so raw trades, depth updates,
    generated features, sweep events, AVWAP events, and signals can be replayed
    through one chronological loop. Trade simulation is intentionally restricted
    to `SignalEvent` + `ReconstructedBookEvent`; all other event types are counted
    and preserved for diagnostics so later processors can be attached without
    changing report semantics.
    """

    __slots__ = ("config", "executor", "state")

    def __init__(self, config: BacktestConfig | None = None) -> None:
        self.config = config or BacktestConfig()
        self.config.validate()
        self.executor = ExecutionSimulator(self.config)
        self.state = BacktestState(equity_quote=self.config.initial_equity_quote)
        self._mark_equity(0)

    def on_event(self, event: EventEnvelope) -> None:
        event_type = str(event.event_type.value if hasattr(event.event_type, "value") else event.event_type)
        self.state.event_type_counts[event_type] += 1
        self.state.last_event_time_ms = max(self.state.last_event_time_ms, event.event_time_ms)
        if isinstance(event, ReconstructedBookEvent):
            self.on_book(event)
        elif isinstance(event, SignalEvent):
            self.on_signal(event)
        else:
            self._mark_equity(event.event_time_ms)

    def on_signal(self, signal: SignalEvent) -> None:
        if self.config.reject_stale_signals and signal.expires_at_ms <= signal.event_time_ms:
            self.state.rejected_signals.append((signal.signal_id, "signal expired before arrival"))
            self._mark_equity(signal.event_time_ms)
            return
        self.state.pending_signals.append(
            PendingSignal(
                signal=signal,
                release_time_ms=signal.event_time_ms + self.config.latency_ms,
            )
        )
        self._mark_equity(signal.event_time_ms)

    def on_book(self, book: ReconstructedBookEvent) -> None:
        self.state.latest_book[book.symbol] = book
        self._release_pending(book)
        self._evaluate_open_positions(book)
        self._mark_equity(book.event_time_ms)

    def finalize(self) -> BacktestReport:
        if self.config.close_open_positions_on_end:
            for position in list(self.state.open_positions.values()):
                book = self.state.latest_book.get(position.symbol)
                if book is not None:
                    self._close_position(position, book, ExitReason.END_OF_REPLAY)
        self._mark_equity(self.state.last_event_time_ms)
        summary = summarize(
            config=self.config,
            trades=self.state.trades,
            equity_curve=self.state.equity_curve,
            rejected_signal_count=len(self.state.rejected_signals),
            expired_signal_count=len(self.state.expired_signals),
            event_count=sum(self.state.event_type_counts.values()),
        )
        return BacktestReport(
            config=self.config,
            summary=summary,
            trades=list(self.state.trades),
            equity_curve=list(self.state.equity_curve),
            event_type_counts=dict(self.state.event_type_counts),
            rejected_signals=list(self.state.rejected_signals),
            expired_signals=list(self.state.expired_signals),
        )

    def _release_pending(self, book: ReconstructedBookEvent) -> None:
        for pending in self.state.pending_signals:
            if pending.status != PendingSignalStatus.PENDING:
                continue
            signal = pending.signal
            if signal.symbol != book.symbol:
                continue
            if book.event_time_ms < pending.release_time_ms:
                continue
            if self.config.reject_stale_signals and book.event_time_ms > signal.expires_at_ms:
                pending.status = PendingSignalStatus.EXPIRED
                pending.reason = "signal expired before simulated execution latency elapsed"
                self.state.expired_signals.append((signal.signal_id, pending.reason))
                continue
            position = self.executor.open_position(signal, book, self.state.equity_quote)
            if position is None:
                pending.status = PendingSignalStatus.REJECTED
                pending.reason = "position sizing or simulated fill rejected"
                self.state.rejected_signals.append((signal.signal_id, pending.reason))
                continue
            pending.status = PendingSignalStatus.EXECUTED
            self.state.open_positions[position.position_id] = position

    def _evaluate_open_positions(self, book: ReconstructedBookEvent) -> None:
        for position in list(self.state.open_positions.values()):
            if position.symbol != book.symbol:
                continue
            exit_decision = self.executor.should_exit(position, book)
            if exit_decision is not None:
                reason, reference_price = exit_decision
                self._close_position(position, book, reason, reference_price)

    def _close_position(
        self,
        position: SimulatedPosition,
        book: ReconstructedBookEvent,
        reason: ExitReason,
        reference_price: float | None = None,
    ) -> None:
        trade = self.executor.close_position(position, book, reason, reference_price)
        self.state.trades.append(trade)
        self.state.realized_pnl_quote += trade.net_pnl_quote
        self.state.equity_quote += trade.net_pnl_quote
        self.state.open_positions.pop(position.position_id, None)

    def _mark_equity(self, event_time_ms: int) -> None:
        if self.state.equity_curve and self.state.equity_curve[-1].event_time_ms == event_time_ms:
            self.state.equity_curve[-1] = EquityPoint(
                event_time_ms=event_time_ms,
                equity_quote=self.state.equity_quote,
                realized_pnl_quote=self.state.realized_pnl_quote,
                open_positions=len(self.state.open_positions),
            )
            return
        self.state.equity_curve.append(
            EquityPoint(
                event_time_ms=event_time_ms,
                equity_quote=self.state.equity_quote,
                realized_pnl_quote=self.state.realized_pnl_quote,
                open_positions=len(self.state.open_positions),
            )
        )
