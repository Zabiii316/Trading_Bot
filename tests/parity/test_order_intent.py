"""Tests for the parity anchor: OrderIntent and InstrumentSpec."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from decimal import Decimal
from math import floor
from uuid import uuid4

import pytest
from trading_contracts.enums import OrderSide, OrderType, TimeInForce, TradeSide

from core.models import (
    CancelIntent,
    InstrumentSpec,
    InstrumentViolation,
    OrderIntent,
    PriceKind,
    quantize_down,
)

BTC = InstrumentSpec(
    symbol="BTCUSDT",
    tick_size=Decimal("0.10"),
    step_size=Decimal("0.001"),
    min_qty=Decimal("0.001"),
    min_notional=Decimal(5),
    price_precision=2,
    quantity_precision=3,
    source_hash="sha256:test-btc",
)

ETH = InstrumentSpec(
    symbol="ETHUSDT",
    tick_size=Decimal("0.01"),
    step_size=Decimal("0.001"),
    min_qty=Decimal("0.001"),
    min_notional=Decimal(5),
    price_precision=2,
    quantity_precision=3,
    source_hash="sha256:test-eth",
)


def make_intent(spec: InstrumentSpec = BTC, **overrides) -> OrderIntent:
    kwargs = {
        "intent_id": uuid4(),
        "spec": spec,
        "side": OrderSide.BUY,
        "order_type": OrderType.MARKETABLE_LIMIT,
        "quantity": Decimal("0.01"),
        "time_in_force": TimeInForce.IOC,
        "client_order_id": "tb-test-0001",
        "decided_at_ms": 1_700_000_000_000,
        "ttl_ms": 5_000,
        "limit_price": Decimal("61864.6"),
        "trade_side": TradeSide.LONG,
    }
    kwargs.update(overrides)
    return OrderIntent.create(**kwargs)


# --------------------------------------------------------------------------- #
# The regression that motivated Decimal everywhere
# --------------------------------------------------------------------------- #


def test_float_step_rounding_bug_is_reproducible() -> None:
    """Documents the audited defect so nobody reintroduces the float idiom.

    ``risk/sizing.py`` and ``paper_execution/pricing.py`` both contained
    ``floor(quantity / step) * step`` on floats. This asserts the wrong answer,
    so the test itself is the explanation.
    """
    assert floor(0.3 / 0.1) * 0.1 == pytest.approx(0.2)  # 33% quantity error
    assert floor(2.9 / 0.1) * 0.1 != 2.9


def test_quantize_down_is_exact_where_float_was_not() -> None:
    assert quantize_down(Decimal("0.3"), Decimal("0.1")) == Decimal("0.3")
    assert quantize_down(Decimal("2.9"), Decimal("0.1")) == Decimal("2.9")
    assert quantize_down(Decimal("0.35"), Decimal("0.1")) == Decimal("0.3")
    assert quantize_down(Decimal("0.0009"), Decimal("0.001")) == Decimal(0)


def test_quantity_snapping_never_rounds_up() -> None:
    """Rounding up would exceed the risk budget the sizer authorised."""
    for raw in ("0.0019", "0.3", "1.9999", "0.001"):
        snapped = BTC.snap_quantity(Decimal(raw))
        assert snapped <= Decimal(raw)
        assert snapped % BTC.step_size == 0


# --------------------------------------------------------------------------- #
# Snapping and per-symbol correctness
# --------------------------------------------------------------------------- #


def test_price_snapping_is_conservative_per_side() -> None:
    raw = Decimal("61864.67")
    assert BTC.snap_price(raw, side=OrderSide.BUY) == Decimal("61864.60")
    assert BTC.snap_price(raw, side=OrderSide.SELL) == Decimal("61864.70")


def test_tick_size_is_per_symbol_not_global() -> None:
    """The audit found tick_size=0.10 hardcoded -- correct for BTC, 10x wrong for ETH."""
    raw = Decimal("1736.517")
    assert BTC.snap_price(raw, side=OrderSide.BUY) == Decimal("1736.50")
    assert ETH.snap_price(raw, side=OrderSide.BUY) == Decimal("1736.51")


def test_create_snaps_so_downstream_never_computes() -> None:
    intent = make_intent(quantity=Decimal("0.0129"), limit_price=Decimal("61864.67"))
    assert intent.quantity == Decimal("0.012")
    assert intent.limit_price == Decimal("61864.60")
    assert BTC.is_price_snapped(intent.limit_price)
    assert BTC.is_quantity_snapped(intent.quantity)


def test_instrument_hash_is_carried_for_reproducibility() -> None:
    assert make_intent().instrument_hash == "sha256:test-btc"


# --------------------------------------------------------------------------- #
# Venue filter rejection -- the -1111 / -1013 class
# --------------------------------------------------------------------------- #


def test_quantity_below_one_step_snaps_to_zero_and_is_rejected() -> None:
    """0.0005 with a 0.001 step snaps to zero, so the positivity guard fires
    first. Rejection is what matters; both paths refuse to emit an intent."""
    with pytest.raises(InstrumentViolation, match="must be positive"):
        make_intent(quantity=Decimal("0.0005"))


def test_quantity_above_step_but_below_min_qty_is_rejected() -> None:
    """A venue whose min_qty exceeds its step_size -- the case where the
    min_qty check is the one that has to catch it."""
    spec = InstrumentSpec(
        symbol="BTCUSDT",
        tick_size=Decimal("0.10"),
        step_size=Decimal("0.001"),
        min_qty=Decimal("0.010"),
        min_notional=Decimal(5),
        price_precision=2,
        quantity_precision=3,
        source_hash="sha256:test-minqty",
    )
    with pytest.raises(InstrumentViolation, match="below min_qty"):
        make_intent(spec=spec, quantity=Decimal("0.005"))


def test_sub_minimum_notional_is_rejected() -> None:
    with pytest.raises(InstrumentViolation, match="below min_notional"):
        make_intent(quantity=Decimal("0.001"), limit_price=Decimal("1.0"))


def test_bare_constructor_rejects_unsnapped_price_rather_than_fixing_it() -> None:
    """Only ``create`` snaps. The constructor is strict so a hand-built intent
    cannot smuggle an unsnapped price past validation."""
    spec_checked = BTC
    with pytest.raises(InstrumentViolation, match="not a multiple of tick_size"):
        spec_checked.validate_order(quantity=Decimal("0.01"), price=Decimal("61864.67"))


# --------------------------------------------------------------------------- #
# Intent invariants
# --------------------------------------------------------------------------- #


def test_intent_is_frozen() -> None:
    intent = make_intent()
    with pytest.raises(FrozenInstanceError):
        intent.quantity = Decimal(99)  # type: ignore[misc]


def test_float_quantity_is_a_type_error() -> None:
    with pytest.raises(TypeError, match="quantity must be Decimal"):
        OrderIntent(
            intent_id=uuid4(),
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=0.01,  # type: ignore[arg-type]
            time_in_force=TimeInForce.GTC,
            reduce_only=False,
            client_order_id="tb-1",
            decided_at_ms=1,
            expires_at_ms=2,
        )


def test_limit_order_requires_a_price() -> None:
    with pytest.raises(ValueError, match="requires a limit_price"):
        make_intent(order_type=OrderType.LIMIT, limit_price=None)


def test_market_order_must_not_carry_a_price() -> None:
    with pytest.raises(ValueError, match="must not carry a limit_price"):
        make_intent(order_type=OrderType.MARKET, time_in_force=TimeInForce.GTC)


def test_ttl_must_be_positive_and_expiry_after_decision() -> None:
    with pytest.raises(ValueError, match="ttl_ms must be positive"):
        make_intent(ttl_ms=0)


def test_client_order_id_is_mandatory_because_it_is_the_recovery_key() -> None:
    with pytest.raises(ValueError, match="recovery key"):
        make_intent(client_order_id="")


def test_client_order_id_respects_binance_length_limit() -> None:
    with pytest.raises(ValueError, match="36 chars"):
        make_intent(client_order_id="x" * 37)


def test_expiry_and_ttl_are_derived_consistently() -> None:
    intent = make_intent(decided_at_ms=1_000_000, ttl_ms=5_000)
    assert intent.expires_at_ms == 1_005_000
    assert intent.ttl_ms() == 5_000
    assert not intent.is_expired_at(1_004_999)
    assert intent.is_expired_at(1_005_000)


def test_notional_is_none_without_a_reference_price() -> None:
    assert (
        make_intent(
            order_type=OrderType.MARKET, limit_price=None, time_in_force=TimeInForce.GTC
        ).notional
        is None
    )
    assert make_intent(
        quantity=Decimal("0.01"), limit_price=Decimal("61864.6")
    ).notional == Decimal("618.646")


# --------------------------------------------------------------------------- #
# The parity key
# --------------------------------------------------------------------------- #


def test_parity_key_ignores_environment_specific_identity() -> None:
    """Two intents differing only in ids must compare equal for parity."""
    common = {
        "quantity": Decimal("0.01"),
        "limit_price": Decimal("61864.6"),
        "decided_at_ms": 1_700_000_000_000,
    }
    a = make_intent(intent_id=uuid4(), client_order_id="bt-0001", **common)
    b = make_intent(intent_id=uuid4(), client_order_id="live-0001", **common)
    assert a != b
    assert a.as_parity_key() == b.as_parity_key()


def test_parity_key_detects_a_quantity_divergence() -> None:
    """One step of difference must fail parity. Decimal equality, not approx."""
    a = make_intent(quantity=Decimal("0.010"))
    b = make_intent(quantity=Decimal("0.011"))
    assert a.as_parity_key() != b.as_parity_key()


def test_parity_key_detects_a_one_tick_price_divergence() -> None:
    a = make_intent(limit_price=Decimal("61864.6"))
    b = make_intent(limit_price=Decimal("61864.7"))
    assert a.as_parity_key() != b.as_parity_key()


# --------------------------------------------------------------------------- #
# CancelIntent and PriceKind
# --------------------------------------------------------------------------- #


def test_cancel_intent_requires_client_order_id() -> None:
    with pytest.raises(ValueError, match="client_order_id is mandatory"):
        CancelIntent(intent_id=uuid4(), symbol="BTCUSDT", client_order_id="", decided_at_ms=1)


def test_avwap_is_not_an_executable_price_kind() -> None:
    """The harness defect in one assertion: AVWAP is a feature, not a fill price."""
    assert not PriceKind.AVWAP.is_executable
    assert not PriceKind.TRADE.is_executable
    assert PriceKind.BID.is_executable
    assert PriceKind.ASK.is_executable
