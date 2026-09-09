"""The complete boundary between deterministic logic and the outside world.

Four ports. Nothing else in ``core/`` may touch time, network, disk, or
randomness -- ``tests/parity/test_core_purity.py`` enforces this with an AST
check that fails the build.

Why ``Protocol`` and not ``ABC``
--------------------------------
These are structural, not nominal. An adapter satisfies ``ExecutionPort`` by
having the right methods; it does not inherit from it. That matters for three
reasons:

1. Adapters stay importable without pulling in ``core``, which keeps the
   dependency arrow pointing one way (``adapters -> core.models``, never
   ``core -> adapters``).
2. Test doubles are plain classes. No base-class ceremony, no ``super()``
   calls, no risk of a half-implemented ABC passing ``isinstance``.
3. ``mypy --strict`` verifies conformance at every call site rather than only
   where a subclass is declared.

``@runtime_checkable`` is applied so ``isinstance`` works for wiring
assertions, but note it only checks method *presence*, not signatures. Static
checking is the real guarantee; treat a passing ``isinstance`` as a smoke test.
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from typing import Protocol, runtime_checkable

from core.models import CancelIntent, InstrumentSpec, OrderIntent

__all__ = [
    "Clock",
    "EventStream",
    "ExecutionPort",
    "InstrumentRegistry",
    "MissingTimestampError",
    "NonMonotonicEventError",
    "UnknownInstrumentError",
]


class MissingTimestampError(ValueError):
    """An event carries no usable ``event_time_ms``.

    Raised, never defaulted. The audit found ``extract_time()`` returning ``0``
    for unrecognised rows and then sorting, which silently moved untimestamped
    events to the front of the series.
    """


class NonMonotonicEventError(ValueError):
    """Events arrived out of order on a stream that promises total ordering."""


class UnknownInstrumentError(KeyError):
    """No venue-authoritative spec for this symbol.

    Fail closed. Trading a symbol whose filters you have not fetched is how you
    discover ``-1111 Precision is over the maximum`` with real money on the
    line.
    """


@runtime_checkable
class Clock(Protocol):
    """The only source of time available to the core.

    Implementations:

    - ``adapters.replay.SimulatedClock`` -- returns the timestamp of the event
      currently being processed. Backtests therefore have no wall-clock
      dependency at all and are bit-reproducible.
    - ``adapters.binance.VenueClock`` -- system time plus a periodically
      resynchronised offset against ``GET /fapi/v1/time``. Without the offset,
      signed requests fail with ``-1021`` once the host drifts past
      ``recvWindow``.

    ``now_ms`` must be monotonic non-decreasing within a single run. A clock
    that can go backwards makes TTL logic unsound.
    """

    def now_ms(self) -> int:
        """Current time in epoch milliseconds."""
        ...


@runtime_checkable
class EventStream(Protocol):
    """An ordered, replayable sequence of market and execution events.

    Contract, binding on every implementation:

    1. Yields in strict total order by ``(event_time_ms, sequence, event_id)``.
       The tie-break on ``event_id`` is what makes equal-millisecond events
       order identically on every run -- without it, backtests are not
       reproducible.
    2. Raises :class:`MissingTimestampError` for any event without a
       timestamp. Never substitutes a default.
    3. Raises :class:`NonMonotonicEventError` rather than silently reordering.
    4. Never blocks indefinitely in a backtest; may block in live.

    In live, execution results (acks, fills, cancels) arrive on this same
    stream. That is what lets the core be a synchronous fold in both
    environments -- see :class:`ExecutionPort`.
    """

    def __iter__(self) -> Iterator[object]: ...


@runtime_checkable
class ExecutionPort(Protocol):
    """Where intents go. Fire-and-forget, by design.

    Both methods return ``None``. This is the single most load-bearing
    decision in the architecture, so it is worth being explicit about why.

    If ``submit()`` returned a fill, it would have to be ``async`` in live
    (network round-trip) and synchronous in backtest (immediate simulation).
    The core would then need two control flows, and parity would be gone
    before the first strategy rule was written. Instead, submissions go *out*
    through this port and their consequences come *back* as events on the
    :class:`EventStream`. The core stays a pure synchronous fold in every
    environment.

    Implementations must therefore:

    - Never raise for market conditions. A rejection is an event, not an
      exception. Only raise for programming errors (a malformed intent that
      somehow escaped ``OrderIntent.create``).
    - Never mutate the intent, and never recompute quantity or price. The
      intent is already snapped and validated; recomputation reintroduces
      divergence.
    - Be idempotent on ``client_order_id``. Submitting the same intent twice
      must not produce two positions. This is what makes recovery from
      ``SUBMIT_UNKNOWN`` safe.
    """

    def submit(self, intent: OrderIntent) -> None:
        """Accept an order intent for transmission."""
        ...

    def cancel(self, intent: CancelIntent) -> None:
        """Accept a cancellation intent for transmission."""
        ...


@runtime_checkable
class InstrumentRegistry(Protocol):
    """Venue-authoritative trading rules, keyed by symbol.

    Populated from ``GET /fapi/v1/exchangeInfo`` in live, and from a
    content-hashed snapshot fixture in backtest. The hash is recorded in the
    dataset manifest so a historical result remains reproducible after the
    venue changes a filter.
    """

    def spec(self, symbol: str) -> InstrumentSpec:
        """Return the spec for ``symbol``.

        Raises :class:`UnknownInstrumentError` if absent. Must not invent a
        default.
        """
        ...

    def symbols(self) -> Sequence[str]:
        """All symbols this registry knows about."""
        ...

    @property
    def source_hash(self) -> str:
        """sha256 of the snapshot backing this registry."""
        ...
