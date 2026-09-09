"""The deterministic core: ``step(state, event) -> (state', outputs)``.

This module is a pure fold. It reads no clock, opens no socket, touches no
disk, and calls no random number generator. Time enters only as
``event_time_ms`` on the events themselves, and as the injected
:class:`~core.ports.Clock` held by :class:`CoreConfig` consumers *outside*
this module.

The shape
---------
::

    state_0 --event_1--> (state_1, intents_1)
             --event_2--> (state_2, intents_2)
             ...

``CoreState`` is frozen. ``step`` returns a new state rather than mutating,
which gives three properties worth the allocation cost:

- **Reproducibility.** Replaying the same events from the same seed state
  yields byte-identical output, every time.
- **Time travel.** A state snapshot can be persisted and resumed, which is how
  live restart-without-flatten becomes possible.
- **Testability.** Every transition is a value comparison, not a sequence of
  mock assertions.

Stage wiring
------------
Phase 2 of the roadmap moves the existing engines (``trading_features``,
``trading_liquidity``, ``trading_sweep``, ``trading_avwap``,
``trading_signals``, ``trading_risk``) behind the :class:`Stage` protocol
below. Those modules are already close to pure -- the sweep state machine and
OFI features in particular -- so the move is mechanical. Until then this
module carries the skeleton, the invariants, and the emission discipline, and
``StageRegistry`` is empty. It is deliberately not faking strategy output:
an engine that emitted plausible-looking intents from stub logic is exactly
how the previous iteration produced 150 documents of evidence for a result
that was never measured.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass, field, replace
from decimal import Decimal
from types import MappingProxyType
from typing import Protocol

from core.models import (
    ZERO,
    CancelIntent,
    Intent,
    OrderIntent,
    RegimeContext,
)
from core.ports import (
    Clock,
    InstrumentRegistry,
    MissingTimestampError,
    NonMonotonicEventError,
)

__all__ = [
    "CoreConfig",
    "CoreState",
    "Stage",
    "StageRegistry",
    "StepResult",
    "StrategyCore",
    "SymbolState",
    "event_order_key",
]


# --------------------------------------------------------------------------- #
# Ordering
# --------------------------------------------------------------------------- #


def event_order_key(event: object) -> tuple[int, int, str]:
    """Total ordering key: ``(event_time_ms, sequence, event_id)``.

    The ``event_id`` tie-break is not decoration. The historical datasets in
    this repo contain events sharing a millisecond -- one sample trade had
    ``entry_time_ms == exit_time_ms``. Without a deterministic tie-break, their
    relative order depends on sort stability and input file order, and the
    backtest stops being reproducible.

    Raises :class:`MissingTimestampError` rather than defaulting to zero.
    """
    time_ms = getattr(event, "event_time_ms", None)
    if not isinstance(time_ms, int) or time_ms <= 0:
        raise MissingTimestampError(
            f"event {getattr(event, 'event_id', '<no id>')} has no usable "
            f"event_time_ms (got {time_ms!r})"
        )
    sequence = getattr(event, "sequence", None)
    if not isinstance(sequence, int):
        sequence = 0
    return (time_ms, sequence, str(getattr(event, "event_id", "")))


# --------------------------------------------------------------------------- #
# Configuration -- parameters only, never state
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class CoreConfig:
    """Static strategy parameters.

    Everything here is a *parameter*. Anything that changes as the market moves
    belongs in :class:`~core.models.RegimeContext`, not here. The audit found
    ``atr_value = 100.0`` living in a frozen config dataclass, which made
    volatility permanently unupdatable by construction.

    Thresholds are expressed as multiples of ATR or spread rather than as
    absolute prices, so a config is portable across symbols. There is no
    ``tick_size`` field -- that comes from
    :class:`~core.models.InstrumentSpec`, sourced from the venue.
    """

    strategy_id: str = "sweep_orderflow_avwap_v2"

    # Signal lifetime. The audit flagged the old 60s TTL as implausible for a
    # microstructure sweep-reversal edge. 5s is a deliberately conservative
    # placeholder; Phase 4.3 sets the real value from measured edge half-life.
    signal_ttl_ms: int = 5_000

    # Staleness gates. Fail closed rather than trading on a stale book.
    max_book_staleness_ms: int = 2_000
    max_signal_age_ms: int = 1_000

    # Stop-distance floors, in regime units. These prevent the degenerate case
    # the audit found: a 3-tick ($0.30) stop on BTC produced a near-zero risk
    # denominator, so position size was set by notional caps rather than by
    # risk-per-trade.
    min_stop_atr_multiple: Decimal = Decimal("0.25")
    min_stop_spread_multiple: Decimal = Decimal("2.0")
    min_stop_ticks: int = 10

    # Emission limits. A core that can emit unboundedly is a core that can
    # rate-limit-ban you.
    max_intents_per_event: int = 4
    max_open_intents_per_symbol: int = 2

    def __post_init__(self) -> None:
        if self.signal_ttl_ms <= 0:
            raise ValueError("signal_ttl_ms must be positive")
        if self.max_intents_per_event <= 0:
            raise ValueError("max_intents_per_event must be positive")
        for name in ("min_stop_atr_multiple", "min_stop_spread_multiple"):
            value = getattr(self, name)
            if not isinstance(value, Decimal):
                raise TypeError(f"{name} must be Decimal, got {type(value).__name__}")
            if value < ZERO:
                raise ValueError(f"{name} must be non-negative")


# --------------------------------------------------------------------------- #
# State
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class SymbolState:
    """Per-symbol slice of core state. Frozen; updated by replacement."""

    symbol: str
    last_event_ms: int = 0
    regime: RegimeContext | None = None
    open_intent_ids: tuple[str, ...] = field(default_factory=tuple)
    events_seen: int = 0

    @property
    def is_tradeable(self) -> bool:
        return self.regime is not None and self.regime.is_tradeable


@dataclass(frozen=True, slots=True)
class CoreState:
    """Complete deterministic state of the strategy at one instant.

    Serialisable by construction, which is what makes restart-without-flatten
    and snapshot-based debugging possible. ``symbols`` is exposed as a read-only
    mapping so a caller cannot mutate state behind the engine's back.
    """

    last_event_ms: int = 0
    events_processed: int = 0
    intents_emitted: int = 0
    halted: bool = False
    halt_reason: str = ""
    _symbols: Mapping[str, SymbolState] = field(default_factory=dict)

    @property
    def symbols(self) -> Mapping[str, SymbolState]:
        return MappingProxyType(dict(self._symbols))

    def symbol(self, symbol: str) -> SymbolState:
        return self._symbols.get(symbol) or SymbolState(symbol=symbol)

    def with_symbol(self, state: SymbolState) -> CoreState:
        updated = dict(self._symbols)
        updated[state.symbol] = state
        return replace(self, _symbols=updated)

    def halt(self, reason: str) -> CoreState:
        """Enter a terminal non-trading state.

        The core cannot un-halt itself. Clearing a halt is an explicit
        operator action performed outside the core, which is the same
        discipline the kill switch follows.
        """
        return replace(self, halted=True, halt_reason=reason)


@dataclass(frozen=True, slots=True)
class StepResult:
    """Output of one transition."""

    state: CoreState
    intents: tuple[Intent, ...] = field(default_factory=tuple)
    diagnostics: tuple[str, ...] = field(default_factory=tuple)

    @property
    def order_intents(self) -> tuple[OrderIntent, ...]:
        return tuple(i for i in self.intents if isinstance(i, OrderIntent))

    @property
    def cancel_intents(self) -> tuple[CancelIntent, ...]:
        return tuple(i for i in self.intents if isinstance(i, CancelIntent))


# --------------------------------------------------------------------------- #
# Stages
# --------------------------------------------------------------------------- #


class Stage(Protocol):
    """One pure pipeline stage.

    Phase 2 wraps the existing engines in this protocol. The signature forces
    the properties the current services lack: state passed in explicitly rather
    than held as instance mutation, and regime supplied per call rather than
    frozen into config at construction.
    """

    name: str

    def apply(
        self,
        *,
        event: object,
        symbol_state: SymbolState,
        regime: RegimeContext | None,
        config: CoreConfig,
        instruments: InstrumentRegistry,
    ) -> tuple[SymbolState, Sequence[Intent], Sequence[str]]: ...


@dataclass(frozen=True, slots=True)
class StageRegistry:
    """Ordered, immutable stage pipeline.

    Empty until Phase 2. Order is significant and mirrors the data dependency
    chain: book -> features -> liquidity -> sweep -> avwap -> signals -> risk.
    """

    stages: tuple[Stage, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        names = [s.name for s in self.stages]
        if len(names) != len(set(names)):
            raise ValueError(f"duplicate stage names: {names}")

    def __iter__(self) -> Iterator[Stage]:
        return iter(self.stages)

    def __len__(self) -> int:
        return len(self.stages)


# --------------------------------------------------------------------------- #
# The core
# --------------------------------------------------------------------------- #


class StrategyCore:
    """Pure event-folding strategy engine.

    Holds only injected ports and immutable configuration. No mutable
    attributes -- all evolving state lives in the :class:`CoreState` threaded
    through :meth:`step`. Two instances constructed identically and fed the
    same events produce identical output, which is precisely what
    ``tests/parity/test_dual_run.py`` asserts across the backtest and live
    wirings.

    ``clock`` is held but never read by :meth:`step`; transitions use
    ``event_time_ms``. It exists for stages that must stamp a decision time in
    live, and the purity test verifies ``core/`` never imports ``time``
    directly.
    """

    __slots__ = ("clock", "config", "instruments", "stages")

    def __init__(
        self,
        *,
        config: CoreConfig,
        clock: Clock,
        instruments: InstrumentRegistry,
        stages: StageRegistry | None = None,
    ) -> None:
        self.config = config
        self.clock = clock
        self.instruments = instruments
        self.stages = stages or StageRegistry()

    # -- the fold ---------------------------------------------------------- #

    def step(self, state: CoreState, event: object) -> StepResult:
        """Advance the state by exactly one event.

        Pure: same ``(state, event)`` always yields the same ``StepResult``.
        """
        time_ms, _, _ = event_order_key(event)

        if time_ms < state.last_event_ms:
            raise NonMonotonicEventError(
                f"event at {time_ms}ms arrived after {state.last_event_ms}ms; "
                "EventStream must deliver total order"
            )

        if state.halted:
            return StepResult(
                state=replace(
                    state,
                    last_event_ms=time_ms,
                    events_processed=state.events_processed + 1,
                ),
                diagnostics=(f"halted: {state.halt_reason}",),
            )

        symbol = getattr(event, "symbol", None)
        if not isinstance(symbol, str) or not symbol:
            # Not every event is symbol-scoped (kill switch, heartbeat).
            return StepResult(
                state=replace(
                    state,
                    last_event_ms=time_ms,
                    events_processed=state.events_processed + 1,
                ),
                diagnostics=("event has no symbol; no stage applied",),
            )

        symbol_state = state.symbol(symbol)
        regime = symbol_state.regime

        intents: list[Intent] = []
        diagnostics: list[str] = []

        for stage in self.stages:
            symbol_state, stage_intents, stage_notes = stage.apply(
                event=event,
                symbol_state=symbol_state,
                regime=regime,
                config=self.config,
                instruments=self.instruments,
            )
            intents.extend(stage_intents)
            diagnostics.extend(stage_notes)
            regime = symbol_state.regime

        symbol_state = replace(
            symbol_state,
            last_event_ms=time_ms,
            events_seen=symbol_state.events_seen + 1,
        )

        admitted, rejected = self._admit(intents, symbol_state)
        diagnostics.extend(rejected)

        next_state = replace(
            state.with_symbol(symbol_state),
            last_event_ms=time_ms,
            events_processed=state.events_processed + 1,
            intents_emitted=state.intents_emitted + len(admitted),
        )
        return StepResult(
            state=next_state,
            intents=tuple(admitted),
            diagnostics=tuple(diagnostics),
        )

    def run(self, state: CoreState, events: Sequence[object]) -> StepResult:
        """Fold a whole sequence. Convenience for tests and backtests."""
        all_intents: list[Intent] = []
        all_diagnostics: list[str] = []
        for event in events:
            result = self.step(state, event)
            state = result.state
            all_intents.extend(result.intents)
            all_diagnostics.extend(result.diagnostics)
        return StepResult(
            state=state,
            intents=tuple(all_intents),
            diagnostics=tuple(all_diagnostics),
        )

    # -- emission discipline ----------------------------------------------- #

    def _admit(
        self, intents: Sequence[Intent], symbol_state: SymbolState
    ) -> tuple[list[Intent], list[str]]:
        """Apply hard emission caps.

        A backstop, not a substitute for risk checks. Its purpose is to make
        runaway emission structurally impossible: the audited baseline fired
        1246 round trips across 68 minutes of data, and no layer objected.
        """
        admitted: list[Intent] = []
        rejected: list[str] = []
        open_count = len(symbol_state.open_intent_ids)

        for intent in intents:
            if len(admitted) >= self.config.max_intents_per_event:
                rejected.append(
                    f"dropped {type(intent).__name__}: max_intents_per_event="
                    f"{self.config.max_intents_per_event} reached"
                )
                continue
            if isinstance(intent, OrderIntent) and not intent.reduce_only:
                if open_count + 1 > self.config.max_open_intents_per_symbol:
                    rejected.append(
                        f"dropped OrderIntent {intent.client_order_id}: "
                        f"max_open_intents_per_symbol="
                        f"{self.config.max_open_intents_per_symbol} reached"
                    )
                    continue
                open_count += 1
            admitted.append(intent)

        return admitted, rejected
