"""Immutable value types for the deterministic core.

Every type in this module is frozen and hashable. Nothing here performs I/O,
reads a clock, or imports anything outside the standard library and
``trading_contracts.enums``. Adapters and the core both depend on this module,
so it must stay dependency-free -- see ``tests/parity/test_core_purity.py``,
which enforces that mechanically.

Design note on money types
--------------------------
Prices, quantities and notionals are ``Decimal``. Never ``float``. The audit
found ``floor(0.3 / 0.1) * 0.1 == 0.2`` in the live sizing path, a 33% quantity
error caused by IEEE-754 representation. ``Decimal`` with explicit quantisation
is the only correct tool here. Scores and statistics may remain ``float``.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from decimal import ROUND_DOWN, ROUND_UP, Decimal, InvalidOperation
from enum import Enum
from typing import Final
from uuid import UUID

from trading_contracts.enums import (
    OrderSide,
    OrderType,
    TimeInForce,
    TradeSide,
    Venue,
)

__all__ = [
    "ZERO",
    "CancelIntent",
    "InstrumentSpec",
    "InstrumentViolation",
    "Intent",
    "OrderIntent",
    "PriceKind",
    "PricePoint",
    "RegimeContext",
    "quantize_down",
    "quantize_up",
]

ZERO: Final = Decimal(0)


class InstrumentViolation(ValueError):
    """An intent violates a venue filter and must never reach the exchange.

    Raised at construction time rather than returned as a status, because an
    unsnapped price or a sub-minimum quantity is a programming error, not a
    market condition. Binance answers these with ``-1111`` (precision) or
    ``-1013`` (filter), and retrying is pointless.
    """


# --------------------------------------------------------------------------- #
# Decimal helpers
# --------------------------------------------------------------------------- #


def quantize_down(value: Decimal, step: Decimal) -> Decimal:
    """Largest multiple of ``step`` that is <= ``value``.

    Replaces the ``floor(value / step) * step`` float idiom that produced
    ``0.3 -> 0.2``. Exact for any step representable as a Decimal.
    """
    if step <= ZERO:
        raise ValueError(f"step must be positive, got {step}")
    return (value / step).to_integral_value(rounding=ROUND_DOWN) * step


def quantize_up(value: Decimal, step: Decimal) -> Decimal:
    """Smallest multiple of ``step`` that is >= ``value``."""
    if step <= ZERO:
        raise ValueError(f"step must be positive, got {step}")
    return (value / step).to_integral_value(rounding=ROUND_UP) * step


# --------------------------------------------------------------------------- #
# Instruments
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class InstrumentSpec:
    """Venue-authoritative trading rules for one symbol.

    Populated from ``GET /fapi/v1/exchangeInfo`` -- never hardcoded. The audit
    found ``tick_size = 0.10`` written as a literal in two config dataclasses;
    correct for BTCUSDT and 10x wrong for ETHUSDT.

    ``source_hash`` is the sha256 of the exchangeInfo snapshot this spec came
    from. It is recorded in backtest manifests so a result stays reproducible
    after the venue changes its filters.
    """

    symbol: str
    tick_size: Decimal
    step_size: Decimal
    min_qty: Decimal
    min_notional: Decimal
    price_precision: int
    quantity_precision: int
    source_hash: str
    venue: Venue = Venue.BINANCE_USDM
    max_qty: Decimal | None = None
    max_market_qty: Decimal | None = None

    def __post_init__(self) -> None:
        if not self.symbol or self.symbol != self.symbol.upper():
            raise ValueError(f"symbol must be upper-case and non-empty: {self.symbol!r}")
        for name in ("tick_size", "step_size", "min_qty", "min_notional"):
            value = getattr(self, name)
            if not isinstance(value, Decimal):
                raise TypeError(f"{name} must be Decimal, got {type(value).__name__}")
            if value < ZERO:
                raise ValueError(f"{name} must be non-negative, got {value}")
        if self.tick_size <= ZERO or self.step_size <= ZERO:
            raise ValueError("tick_size and step_size must be strictly positive")

    # -- snapping ---------------------------------------------------------- #

    def snap_price(self, price: Decimal, *, side: OrderSide) -> Decimal:
        """Snap to ``tick_size``, rounding to the conservative side.

        A BUY limit rounds down and a SELL limit rounds up, so snapping never
        makes an order more aggressive than intended.
        """
        if side is OrderSide.BUY:
            return quantize_down(price, self.tick_size)
        return quantize_up(price, self.tick_size)

    def snap_quantity(self, quantity: Decimal) -> Decimal:
        """Snap down to ``step_size``. Never rounds up -- that would exceed the
        risk budget the sizer authorised."""
        return quantize_down(quantity, self.step_size)

    # -- validation -------------------------------------------------------- #

    def is_price_snapped(self, price: Decimal) -> bool:
        return price % self.tick_size == ZERO

    def is_quantity_snapped(self, quantity: Decimal) -> bool:
        return quantity % self.step_size == ZERO

    def validate_order(self, *, quantity: Decimal, price: Decimal | None) -> None:
        """Raise ``InstrumentViolation`` if the venue would reject this order."""
        if quantity <= ZERO:
            raise InstrumentViolation(f"{self.symbol}: quantity must be positive, got {quantity}")
        if not self.is_quantity_snapped(quantity):
            raise InstrumentViolation(
                f"{self.symbol}: quantity {quantity} is not a multiple of "
                f"step_size {self.step_size}"
            )
        if quantity < self.min_qty:
            raise InstrumentViolation(
                f"{self.symbol}: quantity {quantity} below min_qty {self.min_qty}"
            )
        if self.max_qty is not None and quantity > self.max_qty:
            raise InstrumentViolation(
                f"{self.symbol}: quantity {quantity} above max_qty {self.max_qty}"
            )
        if price is not None:
            if price <= ZERO:
                raise InstrumentViolation(f"{self.symbol}: price must be positive, got {price}")
            if not self.is_price_snapped(price):
                raise InstrumentViolation(
                    f"{self.symbol}: price {price} is not a multiple of tick_size {self.tick_size}"
                )
            notional = price * quantity
            if notional < self.min_notional:
                raise InstrumentViolation(
                    f"{self.symbol}: notional {notional} below min_notional {self.min_notional}"
                )


# --------------------------------------------------------------------------- #
# Intents -- the parity seam
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class OrderIntent:
    """A fully-specified, exchange-ready statement of intent to trade.

    This is *the* parity seam. The core emits ``OrderIntent`` and stops; it
    never calls an exchange. The backtest ``FillSimulator`` and the live
    ``BinanceConnector`` consume byte-identical instances, and
    ``tests/parity/test_dual_run.py`` asserts exact equality of the intent
    sequence produced by both paths.

    That property only holds because *no computation happens downstream*. By
    the time an intent exists, quantity is snapped to ``step_size``, price is
    snapped to ``tick_size``, and every venue filter has been checked. An
    adapter that recomputes any of these reintroduces the divergence this
    design exists to prevent.

    Construct via :meth:`create`, which performs snapping and validation
    against an :class:`InstrumentSpec`. The bare constructor validates but does
    not snap, so it will reject an unsnapped price rather than silently fixing
    it.
    """

    intent_id: UUID
    symbol: str
    side: OrderSide
    order_type: OrderType
    quantity: Decimal
    time_in_force: TimeInForce
    reduce_only: bool
    client_order_id: str
    decided_at_ms: int
    expires_at_ms: int
    limit_price: Decimal | None = None
    signal_id: UUID | None = None
    risk_snapshot_id: UUID | None = None
    instrument_hash: str = ""
    venue: Venue = Venue.BINANCE_USDM
    trade_side: TradeSide = TradeSide.FLAT
    tags: tuple[str, ...] = field(default_factory=tuple)

    # -- invariants -------------------------------------------------------- #

    def __post_init__(self) -> None:
        if not isinstance(self.quantity, Decimal):
            raise TypeError(f"quantity must be Decimal, got {type(self.quantity).__name__}")
        if self.quantity <= ZERO:
            raise ValueError(f"quantity must be positive, got {self.quantity}")
        if self.limit_price is not None and not isinstance(self.limit_price, Decimal):
            raise TypeError("limit_price must be Decimal or None")
        if self.limit_price is not None and self.limit_price <= ZERO:
            raise ValueError(f"limit_price must be positive, got {self.limit_price}")

        if self.requires_price and self.limit_price is None:
            raise ValueError(f"{self.order_type.value} requires a limit_price")
        if self.order_type is OrderType.MARKET and self.limit_price is not None:
            raise ValueError("MARKET order must not carry a limit_price")
        if self.order_type is OrderType.MARKET and self.time_in_force is not TimeInForce.GTC:
            # Binance ignores TIF on MARKET; carrying a non-default value hides
            # a modelling mistake behind venue-specific leniency.
            raise ValueError("MARKET order must use TimeInForce.GTC")

        if self.decided_at_ms <= 0:
            raise ValueError("decided_at_ms must be a positive epoch millisecond")
        if self.expires_at_ms <= self.decided_at_ms:
            raise ValueError(
                f"expires_at_ms {self.expires_at_ms} must be after "
                f"decided_at_ms {self.decided_at_ms}"
            )
        if not self.client_order_id:
            raise ValueError("client_order_id is mandatory -- it is the recovery key")
        if len(self.client_order_id) > 36:
            raise ValueError(
                f"client_order_id exceeds Binance's 36 chars: {self.client_order_id!r}"
            )
        if self.symbol != self.symbol.upper():
            raise ValueError(f"symbol must be upper-case: {self.symbol!r}")

    @property
    def requires_price(self) -> bool:
        return self.order_type in {OrderType.LIMIT, OrderType.MARKETABLE_LIMIT}

    @property
    def notional(self) -> Decimal | None:
        """Quote-currency notional, or ``None`` for a market order with no
        reference price. Never estimate a price to fill this in."""
        if self.limit_price is None:
            return None
        return self.limit_price * self.quantity

    def is_expired_at(self, now_ms: int) -> bool:
        """TTL check. Takes the time explicitly -- the intent never reads a clock."""
        return now_ms >= self.expires_at_ms

    def ttl_ms(self) -> int:
        return self.expires_at_ms - self.decided_at_ms

    # -- construction ------------------------------------------------------ #

    @classmethod
    def create(
        cls,
        *,
        intent_id: UUID,
        spec: InstrumentSpec,
        side: OrderSide,
        order_type: OrderType,
        quantity: Decimal,
        time_in_force: TimeInForce,
        client_order_id: str,
        decided_at_ms: int,
        ttl_ms: int,
        limit_price: Decimal | None = None,
        reduce_only: bool = False,
        signal_id: UUID | None = None,
        risk_snapshot_id: UUID | None = None,
        trade_side: TradeSide = TradeSide.FLAT,
        tags: tuple[str, ...] = (),
    ) -> OrderIntent:
        """Snap to venue filters, validate, and freeze.

        This is the only sanctioned way to build an intent. It guarantees the
        downstream no-computation property: an adapter receiving this object
        can serialise it directly.
        """
        if ttl_ms <= 0:
            raise ValueError(f"ttl_ms must be positive, got {ttl_ms}")

        try:
            snapped_qty = spec.snap_quantity(quantity)
            snapped_price = (
                spec.snap_price(limit_price, side=side) if limit_price is not None else None
            )
        except (InvalidOperation, ArithmeticError) as exc:  # pragma: no cover - defensive
            raise InstrumentViolation(f"{spec.symbol}: snapping failed: {exc}") from exc

        spec.validate_order(quantity=snapped_qty, price=snapped_price)

        return cls(
            intent_id=intent_id,
            symbol=spec.symbol,
            side=side,
            order_type=order_type,
            quantity=snapped_qty,
            time_in_force=time_in_force,
            reduce_only=reduce_only,
            client_order_id=client_order_id,
            decided_at_ms=decided_at_ms,
            expires_at_ms=decided_at_ms + ttl_ms,
            limit_price=snapped_price,
            signal_id=signal_id,
            risk_snapshot_id=risk_snapshot_id,
            instrument_hash=spec.source_hash,
            venue=spec.venue,
            trade_side=trade_side,
            tags=tags,
        )

    def as_parity_key(self) -> tuple[object, ...]:
        """The fields that must match exactly across backtest and live.

        Excludes ``intent_id`` and ``client_order_id``, which embed a sequence
        counter and are legitimately environment-specific. Everything that
        determines market impact is included.
        """
        return (
            self.symbol,
            self.side.value,
            self.order_type.value,
            self.quantity,
            self.limit_price,
            self.time_in_force.value,
            self.reduce_only,
            self.decided_at_ms,
            self.expires_at_ms,
            self.trade_side.value,
        )


@dataclass(frozen=True, slots=True)
class CancelIntent:
    """Intent to cancel a working order, addressed by ``client_order_id``.

    Deliberately not by venue order id: the client id is deterministic and
    survives a process restart, which is what makes it usable as the recovery
    key when an order is in ``SUBMIT_UNKNOWN``.
    """

    intent_id: UUID
    symbol: str
    client_order_id: str
    decided_at_ms: int
    reason: str = ""
    venue: Venue = Venue.BINANCE_USDM

    def __post_init__(self) -> None:
        if not self.client_order_id:
            raise ValueError("client_order_id is mandatory")
        if self.decided_at_ms <= 0:
            raise ValueError("decided_at_ms must be a positive epoch millisecond")
        if self.symbol != self.symbol.upper():
            raise ValueError(f"symbol must be upper-case: {self.symbol!r}")

    def as_parity_key(self) -> tuple[object, ...]:
        return (self.symbol, self.client_order_id, self.decided_at_ms)


Intent = OrderIntent | CancelIntent


# --------------------------------------------------------------------------- #
# Regime -- live state, deliberately separate from config
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class RegimeContext:
    """Per-symbol market state, recomputed on every event.

    This type exists because the audit found ``SweepEngineConfig.atr_value =
    100.0`` sitting in a ``frozen=True`` dataclass -- volatility modelled as
    immutable configuration, while a correct ``RollingAtr`` existed elsewhere
    and was never wired in. Config holds *parameters*; ``RegimeContext`` holds
    *state*. Conflating them is what froze the strategy to one regime.

    Thresholds should be expressed as multiples of these values rather than as
    absolute prices, so they transfer across symbols and volatility regimes.
    """

    symbol: str
    as_of_ms: int
    atr: Decimal
    spread: Decimal
    realized_vol: Decimal = ZERO
    spread_pctile: float = 0.5
    book_healthy: bool = False
    ms_since_book_sync: int = 0

    def __post_init__(self) -> None:
        for name in ("atr", "spread", "realized_vol"):
            value = getattr(self, name)
            if not isinstance(value, Decimal):
                raise TypeError(f"{name} must be Decimal, got {type(value).__name__}")
            if value < ZERO:
                raise ValueError(f"{name} must be non-negative, got {value}")

    @property
    def is_tradeable(self) -> bool:
        """Fail closed: an unhealthy or unpriced book is not tradeable."""
        return self.book_healthy and self.atr > ZERO and self.spread > ZERO

    def with_book_health(self, *, healthy: bool, ms_since_sync: int) -> RegimeContext:
        return replace(self, book_healthy=healthy, ms_since_book_sync=ms_since_sync)


# --------------------------------------------------------------------------- #
# Price series typing -- the fix for the harness defect
# --------------------------------------------------------------------------- #


class PriceKind(str, Enum):
    """What a price number actually *is*.

    The audit's root cause: a backtest ``extract_price()`` that returned the
    first matching key from a list containing both ``price`` and ``avwap``,
    over a dataset that was half trade prints and half anchored-VWAP events.
    The resulting series was a square wave; the strategy lost 1246 of 1246
    trades at exactly the round-trip cost.

    ``AVWAP`` is enumerated here specifically so that any attempt to use it as
    a fill price is a loud, named error. Fill prices come from a reconstructed
    book's best bid/ask -- never from a derived feature, and never from a trade
    print, which tells you what somebody else got.
    """

    TRADE = "trade"
    MID = "mid"
    BID = "bid"
    ASK = "ask"
    MARK = "mark"
    AVWAP = "avwap"

    @property
    def is_executable(self) -> bool:
        return self in {PriceKind.BID, PriceKind.ASK}


@dataclass(frozen=True, slots=True)
class PricePoint:
    time_ms: int
    price: Decimal
    kind: PriceKind
    symbol: str

    def __post_init__(self) -> None:
        if not isinstance(self.price, Decimal):
            raise TypeError(f"price must be Decimal, got {type(self.price).__name__}")
        if self.price <= ZERO:
            raise ValueError(f"price must be positive, got {self.price}")
        if self.time_ms <= 0:
            raise ValueError("time_ms must be a positive epoch millisecond")
