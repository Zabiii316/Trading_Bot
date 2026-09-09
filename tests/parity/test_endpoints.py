"""Tests for the endpoint configuration.

Each test here corresponds to a specific bug found in the audit. The last one
is a repo-wide grep asserting that ``endpoints.py`` remains the only place a
Binance hostname is written down -- that is what stops the bug recurring.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from adapters.binance.endpoints import (
    BINANCE_URLS,
    BinanceEndpoints,
    BinanceEnvironment,
    EndpointConfigError,
)

REPO_ROOT = Path(__file__).resolve().parents[2]


# --------------------------------------------------------------------------- #
# Environment separation
# --------------------------------------------------------------------------- #


def test_testnet_uses_the_futures_testnet_not_the_spot_one() -> None:
    ep = BinanceEndpoints.for_environment(BinanceEnvironment.TESTNET)
    assert ep.rest_base == "https://testnet.binancefuture.com"
    assert "binance.vision" not in ep.rest_base


def test_testnet_user_stream_is_not_a_mainnet_host() -> None:
    """The user_stream.py:50 bug: mainnet WS host returned regardless of testnet."""
    ep = BinanceEndpoints.for_environment(BinanceEnvironment.TESTNET)
    assert "fstream.binance.com" not in ep.user_stream_ws
    assert ep.user_stream_ws == "wss://stream.binancefuture.com/ws"


def test_testnet_market_data_is_deliberately_mainnet() -> None:
    """Testnet books are synthetic. Real data, simulated fills -- by design."""
    ep = BinanceEndpoints.for_environment(BinanceEnvironment.TESTNET)
    assert ep.uses_live_market_data is True


def test_mainnet_endpoints_are_all_mainnet() -> None:
    ep = BinanceEndpoints.for_environment(BinanceEnvironment.MAINNET)
    assert ep.rest_base == "https://fapi.binance.com"
    assert ep.user_stream_ws == "wss://fstream.binance.com/ws"
    assert ep.is_mainnet


def test_paper_has_no_trading_surface() -> None:
    ep = BinanceEndpoints.for_environment(BinanceEnvironment.PAPER)
    assert ep.rest_base == ""
    assert ep.user_stream_ws == ""
    assert ep.market_data_ws
    assert not ep.orders_are_real


# --------------------------------------------------------------------------- #
# Guards
# --------------------------------------------------------------------------- #


def test_spot_testnet_override_is_rejected_by_name() -> None:
    with pytest.raises(EndpointConfigError, match="SPOT testnet"):
        BinanceEndpoints.for_environment(
            BinanceEnvironment.TESTNET,
            rest_base_override="https://testnet.binance.vision",
        )


def test_mainnet_rest_base_on_testnet_is_rejected() -> None:
    with pytest.raises(EndpointConfigError, match="mainnet host"):
        BinanceEndpoints.for_environment(
            BinanceEnvironment.TESTNET,
            rest_base_override="https://fapi.binance.com",
        )


def test_live_trading_flag_alone_cannot_produce_real_orders() -> None:
    """Double confirmation: the flag is meaningless outside mainnet."""
    with pytest.raises(EndpointConfigError, match="only reach"):
        BinanceEndpoints.for_environment(BinanceEnvironment.TESTNET, enable_live_trading=True)


def test_mainnet_without_the_flag_does_not_submit_real_orders() -> None:
    ep = BinanceEndpoints.for_environment(BinanceEnvironment.MAINNET, enable_live_trading=False)
    assert ep.is_mainnet
    assert not ep.orders_are_real


def test_real_orders_require_both_conditions() -> None:
    ep = BinanceEndpoints.for_environment(BinanceEnvironment.MAINNET, enable_live_trading=True)
    assert ep.orders_are_real


def test_spot_rest_path_is_rejected() -> None:
    """The connectivity script called /api/v3/exchangeInfo on a futures bot."""
    ep = BinanceEndpoints.for_environment(BinanceEnvironment.TESTNET)
    with pytest.raises(EndpointConfigError, match="SPOT path"):
        ep.rest_url("/api/v3/exchangeInfo")
    assert ep.rest_url("/fapi/v1/exchangeInfo").endswith("/fapi/v1/exchangeInfo")


def test_paper_rest_url_raises_rather_than_returning_a_bare_path() -> None:
    ep = BinanceEndpoints.for_environment(BinanceEnvironment.PAPER)
    with pytest.raises(EndpointConfigError, match="no REST trading surface"):
        ep.rest_url("/fapi/v1/order")


# --------------------------------------------------------------------------- #
# Environment resolution
# --------------------------------------------------------------------------- #


def test_default_environment_is_the_safest_one() -> None:
    ep = BinanceEndpoints.from_env({})
    assert ep.environment is BinanceEnvironment.PAPER
    assert not ep.orders_are_real


def test_unknown_environment_is_rejected_with_the_valid_options() -> None:
    with pytest.raises(EndpointConfigError, match="not one of"):
        BinanceEndpoints.from_env({"BINANCE_ENVIRONMENT": "prod"})


def test_env_resolution_reaches_mainnet_only_with_two_variables() -> None:
    ep = BinanceEndpoints.from_env(
        {"BINANCE_ENVIRONMENT": "mainnet", "BINANCE_ENABLE_LIVE_TRADING": "true"}
    )
    assert ep.orders_are_real
    assert "REAL ORDERS" in ep.describe()


def test_every_trading_environment_defines_all_three_surfaces() -> None:
    for env in (BinanceEnvironment.MAINNET, BinanceEnvironment.TESTNET):
        urls = BINANCE_URLS[env]
        assert urls.rest and urls.user_stream_ws and urls.market_data_ws


# --------------------------------------------------------------------------- #
# The structural guarantee
# --------------------------------------------------------------------------- #

_HOSTNAME = re.compile(r"(?:wss?|https?)://[a-z0-9.\-]*binance[a-z0-9.\-]*", re.IGNORECASE)

_ALLOWED = {
    Path("adapters/binance/endpoints.py"),
    Path("tests/parity/test_endpoints.py"),
}

#: Legacy modules under services/ that still hold hardcoded hostnames.
#:
#: This is a quarantine list, not an exemption. Phase 2 migrates each of these
#: into adapters/binance/ and deletes its entry. The test below fails if the
#: list GROWS, and fails if an entry becomes stale -- so it ratchets in one
#: direction only and cannot be quietly widened.
LEGACY_HOSTNAME_QUARANTINE = {
    Path("services/live_execution/python/trading_live_execution/config.py"),
    Path("services/live_execution/python/trading_live_execution/user_stream.py"),
    Path("services/live_execution/python/tests/test_client.py"),
    Path("services/live_execution/python/tests/test_user_stream.py"),
    Path("services/market_data/python/trading_market_data/config.py"),
    Path("services/market_data/python/tests/test_config_and_publisher.py"),
    Path("services/order_book/python/trading_order_book/snapshot.py"),
}


def _modules_with_hostnames() -> dict[Path, list[str]]:
    found: dict[Path, list[str]] = {}
    for path in REPO_ROOT.rglob("*.py"):
        if "__pycache__" in path.parts or ".git" in path.parts:
            continue
        rel = path.relative_to(REPO_ROOT)
        if rel in _ALLOWED:
            continue
        hits = _HOSTNAME.findall(path.read_text(errors="ignore"))
        if hits:
            found[rel] = sorted(set(hits))
    return found


def test_no_new_module_hardcodes_a_binance_hostname() -> None:
    """Three URL bugs had one root cause: literals scattered across modules.

    This is the test that prevents recurrence. New code must route through
    ``BINANCE_URLS``; only the quarantined legacy modules are tolerated.
    """
    offenders = {
        str(rel): hits
        for rel, hits in _modules_with_hostnames().items()
        if rel not in LEGACY_HOSTNAME_QUARANTINE
    }
    assert not offenders, (
        "Binance hostnames must only appear in adapters/binance/endpoints.py:\n"
        + "\n".join(f"  {k}: {v}" for k, v in sorted(offenders.items()))
        + "\n\nIf this is a legacy module being migrated, migrate it -- do not "
        "add it to the quarantine list."
    )


def test_quarantine_list_has_no_stale_entries() -> None:
    """Ratchet: an entry must be removed once its module is migrated.

    Without this, the quarantine list would silently outlive the problem and
    stop meaning anything.
    """
    current = set(_modules_with_hostnames())
    stale = sorted(str(p) for p in LEGACY_HOSTNAME_QUARANTINE - current)
    assert not stale, (
        "these modules no longer hardcode hostnames -- remove them from "
        "LEGACY_HOSTNAME_QUARANTINE:\n  " + "\n  ".join(stale)
    )


def test_quarantine_list_is_shrinking_toward_zero() -> None:
    """Documents remaining migration debt as an executable number."""
    assert len(LEGACY_HOSTNAME_QUARANTINE) <= 7, (
        "hostname quarantine list grew; Phase 2 should be shrinking it"
    )


def test_no_module_references_the_spot_testnet() -> None:
    """No quarantine here. The spot testnet is never acceptable, anywhere.

    Five phase scripts used ``testnet.binance.vision`` on a USD-M futures bot.
    Those scripts are deleted; this keeps them from coming back.
    """
    offenders = [
        str(p.relative_to(REPO_ROOT))
        for p in REPO_ROOT.rglob("*.py")
        if "__pycache__" not in p.parts
        and p.relative_to(REPO_ROOT) not in _ALLOWED
        and "binance.vision" in p.read_text(errors="ignore")
    ]
    assert not offenders, f"spot testnet referenced in: {offenders}"
