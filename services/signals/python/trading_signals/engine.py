from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from trading_contracts.enums import AvwapConfirmation, SweepOutcome, SweepState
from trading_contracts.events import (
    AnchoredVwapEvent,
    LiquiditySweepEvent,
    OrderFlowFeatureEvent,
    ReconstructedBookEvent,
    SignalEvent,
)

from .models import ExecutionSnapshot, RegimeSnapshot, SignalCandidate
from .scoring import RuleBasedSignalScorer, SignalScoringConfig


BULLISH_CONFIRMATIONS = {AvwapConfirmation.STRONG_BULLISH.value, AvwapConfirmation.WEAK_BULLISH.value}
BEARISH_CONFIRMATIONS = {AvwapConfirmation.STRONG_BEARISH.value, AvwapConfirmation.WEAK_BEARISH.value}
BULLISH_OUTCOMES = {SweepOutcome.BULLISH_REJECTION.value, SweepOutcome.BULLISH_ACCEPTANCE.value}
BEARISH_OUTCOMES = {SweepOutcome.BEARISH_REJECTION.value, SweepOutcome.BEARISH_ACCEPTANCE.value}
FINAL_SWEEP_STATES = {
    SweepState.ORDER_FLOW_CONFIRMED.value,
    SweepState.SIGNAL_READY.value,
}


@dataclass(frozen=True, slots=True)
class SignalEngineConfig:
    scoring: SignalScoringConfig = SignalScoringConfig()
    require_avwap_confirmation: bool = True
    require_order_flow_confirmation: bool = True
    allow_duplicate_signals: bool = False
    stale_book_ms: int = 2_000
    stale_flow_ms: int = 5_000
    stale_avwap_ms: int = 5_000


class SignalScorerEngine:
    """Event-driven signal scorer that emits trade-ready SignalEvent objects.

    The engine stores only the latest book/flow/AVWAP state per symbol/sweep and
    produces at most one signal per sweep by default. This keeps the hot path
    deterministic, bounded, and replay-safe.
    """

    __slots__ = (
        "config",
        "scorer",
        "latest_book",
        "latest_flow",
        "latest_avwap_by_sweep",
        "latest_sweep",
        "regimes",
        "emitted_sweeps",
        "last_rejections",
    )

    def __init__(self, config: SignalEngineConfig | None = None) -> None:
        self.config = config or SignalEngineConfig()
        self.scorer = RuleBasedSignalScorer(self.config.scoring)
        self.latest_book: dict[str, ReconstructedBookEvent] = {}
        self.latest_flow: dict[str, OrderFlowFeatureEvent] = {}
        self.latest_avwap_by_sweep: dict[UUID, AnchoredVwapEvent] = {}
        self.latest_sweep: dict[UUID, LiquiditySweepEvent] = {}
        self.regimes: dict[str, RegimeSnapshot] = {}
        self.emitted_sweeps: set[UUID] = set()
        self.last_rejections: dict[UUID, list[str]] = {}

    def update_regime(self, regime: RegimeSnapshot) -> None:
        self.regimes[regime.normalized_symbol()] = regime

    def on_book(self, book: ReconstructedBookEvent) -> list[SignalEvent]:
        self.latest_book[book.symbol] = book
        return self._attempt_for_symbol(book.symbol, book.event_time_ms)

    def on_order_flow(self, feature: OrderFlowFeatureEvent) -> list[SignalEvent]:
        self.latest_flow[feature.symbol] = feature
        return self._attempt_for_symbol(feature.symbol, feature.event_time_ms)

    def on_avwap(self, event: AnchoredVwapEvent) -> list[SignalEvent]:
        if event.sweep_id is not None:
            self.latest_avwap_by_sweep[event.sweep_id] = event
            sweep = self.latest_sweep.get(event.sweep_id)
            if sweep is not None:
                return self._attempt(sweep, event.event_time_ms)
        return []

    def on_sweep(self, sweep: LiquiditySweepEvent) -> list[SignalEvent]:
        self.latest_sweep[sweep.sweep_id] = sweep
        return self._attempt(sweep, sweep.event_time_ms)

    def _attempt_for_symbol(self, symbol: str, now_ms: int) -> list[SignalEvent]:
        output: list[SignalEvent] = []
        for sweep in list(self.latest_sweep.values()):
            if sweep.symbol == symbol:
                output.extend(self._attempt(sweep, now_ms))
        return output

    def _attempt(self, sweep: LiquiditySweepEvent, now_ms: int) -> list[SignalEvent]:
        if not self.config.allow_duplicate_signals and sweep.sweep_id in self.emitted_sweeps:
            self.last_rejections[sweep.sweep_id] = ["duplicate sweep signal suppressed"]
            return []
        if not self._is_final_sweep(sweep):
            self.last_rejections[sweep.sweep_id] = ["waiting for final sweep state"]
            return []
        if self.config.require_order_flow_confirmation and sweep.order_flow_score is None:
            self.last_rejections[sweep.sweep_id] = ["waiting for order-flow-confirmed sweep"]
            return []

        avwap = self.latest_avwap_by_sweep.get(sweep.sweep_id)
        if self.config.require_avwap_confirmation:
            if avwap is None:
                self.last_rejections[sweep.sweep_id] = ["waiting for AVWAP confirmation"]
                return []
            if not self._avwap_matches_outcome(sweep, avwap):
                self.last_rejections[sweep.sweep_id] = ["AVWAP confirmation direction does not match sweep outcome"]
                return []
            if avwap.is_failure:
                self.last_rejections[sweep.sweep_id] = ["AVWAP failure event"]
                return []
            if now_ms - avwap.event_time_ms > self.config.stale_avwap_ms:
                self.last_rejections[sweep.sweep_id] = ["AVWAP confirmation is stale"]
                return []

        book = self.latest_book.get(sweep.symbol)
        if book is not None and now_ms - book.event_time_ms > self.config.stale_book_ms:
            self.last_rejections[sweep.sweep_id] = ["execution book is stale"]
            return []
        flow = self.latest_flow.get(sweep.symbol)
        if flow is not None and now_ms - flow.event_time_ms > self.config.stale_flow_ms:
            self.last_rejections[sweep.sweep_id] = ["order-flow feature is stale"]
            return []

        regime = self.regimes.get(sweep.symbol, RegimeSnapshot(symbol=sweep.symbol, score=self.config.scoring.default_regime_score))
        candidate = SignalCandidate(
            sweep=sweep,
            order_flow=flow,
            avwap=avwap,
            execution=ExecutionSnapshot.from_book(book) if book is not None else None,
            regime=regime,
        )
        breakdown = self.scorer.score(candidate)
        if breakdown.is_rejected:
            self.last_rejections[sweep.sweep_id] = breakdown.rejection_reasons
            return []
        signal = self.scorer.build_signal(candidate, breakdown)
        self.emitted_sweeps.add(sweep.sweep_id)
        self.last_rejections.pop(sweep.sweep_id, None)
        return [signal]

    @staticmethod
    def _is_final_sweep(sweep: LiquiditySweepEvent) -> bool:
        state = sweep.state.value if hasattr(sweep.state, "value") else str(sweep.state)
        outcome = sweep.outcome.value if hasattr(sweep.outcome, "value") else str(sweep.outcome)
        return state in FINAL_SWEEP_STATES and outcome not in {SweepOutcome.NO_TRADE.value, SweepOutcome.UNRESOLVED.value}

    @staticmethod
    def _avwap_matches_outcome(sweep: LiquiditySweepEvent, avwap: AnchoredVwapEvent) -> bool:
        outcome = sweep.outcome.value if hasattr(sweep.outcome, "value") else str(sweep.outcome)
        confirmation = avwap.confirmation.value if hasattr(avwap.confirmation, "value") else str(avwap.confirmation)
        if outcome in BULLISH_OUTCOMES:
            return confirmation in BULLISH_CONFIRMATIONS
        if outcome in BEARISH_OUTCOMES:
            return confirmation in BEARISH_CONFIRMATIONS
        return False
