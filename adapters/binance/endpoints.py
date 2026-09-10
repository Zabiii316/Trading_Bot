"""Single source of truth for every Binance URL.

Why this module exists
----------------------
The audit found the environment split across three places, two of them wrong:

- ``live_execution/config.py`` -- correct: ``testnet.binancefuture.com``
- ``live_execution/user_stream.py:50`` -- **hardcoded mainnet**
  ``wss://fstream.binance.com/ws``, returned regardless of
  ``config.testnet``. The accompanying comment claimed "testnet routing is
  controlled by the listen-key source", which is not how it works: a testnet
  listen key presented to the mainnet stream host does not authenticate.
- five phase scripts -- ``testnet.binance.vision``, which is the **spot**
  testnet, on a USD-M futures bot, hitting ``/api/v3/*`` instead of
  ``/fapi/v1/*``. Every piece of Phase 23 connectivity, soak-test and
  micro-execution evidence was gathered against the wrong venue.

Three separate bugs, one root cause: URLs were literals scattered across
modules. The fix is not "be more careful" -- it is to make the wrong URL
unreachable. There is exactly one table below, it is keyed by
:class:`BinanceEnvironment`, and ``BINANCE_URLS`` is the only place in the
codebase where a Binance hostname appears as a string literal. CI asserts that
(see ``tests/parity/test_endpoints.py``).

Deliberate asymmetry: market data
---------------------------------
:attr:`BinanceEndpoints.market_data_ws` points at **mainnet** even in the
testnet environment, and this is correct rather than an oversight. Testnet
order books are synthetic and thinly populated; a strategy calibrated against
them is calibrated against nothing. You want real market data with simulated
execution. The property is named ``market_data_ws`` rather than folded into a
generic ``ws_base`` so that the choice is visible at every call site, and
:attr:`uses_live_market_data` reports it explicitly for health output.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from typing import Final

__all__ = [
    "BINANCE_URLS",
    "MAINNET_HOST_MARKERS",
    "BinanceEndpoints",
    "BinanceEnvironment",
    "EndpointConfigError",
]


class EndpointConfigError(ValueError):
    """Endpoint configuration is unsafe or internally inconsistent."""


class BinanceEnvironment(str, Enum):
    """Where orders will actually go.

    ``PAPER`` is included as a first-class environment so that "live data,
    simulated fills" does not have to borrow the testnet configuration and
    thereby acquire a credential path it should not have.
    """

    MAINNET = "mainnet"
    TESTNET = "testnet"
    PAPER = "paper"

    @property
    def submits_real_orders(self) -> bool:
        return self is BinanceEnvironment.MAINNET

    @property
    def requires_credentials(self) -> bool:
        return self in {BinanceEnvironment.MAINNET, BinanceEnvironment.TESTNET}


@dataclass(frozen=True, slots=True)
class _UrlSet:
    rest: str
    user_stream_ws: str
    market_data_ws: str


#: The only place a Binance hostname is written down.
BINANCE_URLS: Final[Mapping[BinanceEnvironment, _UrlSet]] = {
    BinanceEnvironment.MAINNET: _UrlSet(
        rest="https://fapi.binance.com",
        user_stream_ws="wss://fstream.binance.com/ws",
        market_data_ws="wss://fstream.binance.com/stream",
    ),
    BinanceEnvironment.TESTNET: _UrlSet(
        rest="https://testnet.binancefuture.com",
        user_stream_ws="wss://stream.binancefuture.com/ws",
        # Intentional: real book, simulated fills. See module docstring.
        market_data_ws="wss://fstream.binance.com/stream",
    ),
    BinanceEnvironment.PAPER: _UrlSet(
        rest="",  # no REST trading surface at all
        user_stream_ws="",  # no user stream -- fills are simulated locally
        market_data_ws="wss://fstream.binance.com/stream",
    ),
}

#: Substrings that identify a mainnet host. Used by the trading-enabled guard.
MAINNET_HOST_MARKERS: Final[tuple[str, ...]] = ("fapi.binance.com", "fstream.binance.com")

#: The spot testnet. A USD-M futures bot must never reach this host; it serves
#: ``/api/v3/*``, not ``/fapi/v1/*``. Named so the guard can reject it by name
#: rather than by silence.
_SPOT_TESTNET_HOST: Final = "testnet.binance.vision"


@dataclass(frozen=True, slots=True)
class BinanceEndpoints:
    """Resolved, validated endpoint set for one environment.

    Construct with :meth:`for_environment` or :meth:`from_env`. Both run
    :meth:`validate`, so an instance is safe to trust at every call site --
    no module needs to re-derive a URL or re-check a flag.
    """

    environment: BinanceEnvironment
    rest_base: str
    user_stream_ws: str
    market_data_ws: str
    enable_live_trading: bool = False
    rest_base_override: str | None = None

    # -- construction ------------------------------------------------------ #

    @classmethod
    def for_environment(
        cls,
        environment: BinanceEnvironment,
        *,
        enable_live_trading: bool = False,
        rest_base_override: str | None = None,
    ) -> BinanceEndpoints:
        urls = BINANCE_URLS[environment]
        endpoints = cls(
            environment=environment,
            rest_base=(rest_base_override or urls.rest).rstrip("/"),
            user_stream_ws=urls.user_stream_ws,
            market_data_ws=urls.market_data_ws,
            enable_live_trading=enable_live_trading,
            rest_base_override=rest_base_override,
        )
        endpoints.validate()
        return endpoints

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> BinanceEndpoints:
        """Resolve from environment variables, defaulting to the safest option.

        Defaults are deliberately inconvenient: ``PAPER`` and live trading off.
        Reaching mainnet requires setting two independent variables, and the
        double-confirmation guard in :meth:`validate` makes an accidental
        single-variable slip non-fatal.
        """
        source = env if env is not None else os.environ
        raw = (source.get("BINANCE_ENVIRONMENT") or "paper").strip().lower()
        try:
            environment = BinanceEnvironment(raw)
        except ValueError as exc:
            valid = ", ".join(e.value for e in BinanceEnvironment)
            raise EndpointConfigError(
                f"BINANCE_ENVIRONMENT={raw!r} is not one of: {valid}"
            ) from exc

        return cls.for_environment(
            environment,
            enable_live_trading=_bool_from_env(source.get("BINANCE_ENABLE_LIVE_TRADING")),
            rest_base_override=(source.get("BINANCE_REST_BASE_OVERRIDE") or None),
        )

    # -- validation -------------------------------------------------------- #

    def validate(self) -> None:
        """Reject every configuration that caused a bug in the audited code."""
        # 1. The spot testnet is never valid for a USD-M futures bot.
        for url in (self.rest_base, self.user_stream_ws, self.market_data_ws):
            if _SPOT_TESTNET_HOST in url:
                raise EndpointConfigError(
                    f"{_SPOT_TESTNET_HOST} is the Binance SPOT testnet and serves "
                    f"/api/v3/*, not /fapi/v1/*. It cannot be used by a USD-M "
                    f"futures bot. Use {BINANCE_URLS[BinanceEnvironment.TESTNET].rest}."
                )

        # 2. A non-mainnet environment must not carry a mainnet *trading*
        #    surface. Market data is exempt by design (see module docstring).
        if self.environment is not BinanceEnvironment.MAINNET:
            for label, url in (
                ("rest_base", self.rest_base),
                ("user_stream_ws", self.user_stream_ws),
            ):
                if any(marker in url for marker in MAINNET_HOST_MARKERS):
                    raise EndpointConfigError(
                        f"environment={self.environment.value} but {label}={url!r} "
                        f"is a mainnet host. This is the user_stream.py bug: a "
                        f"testnet listen key presented to a mainnet host will not "
                        f"authenticate."
                    )

        # 3. Mainnet must actually be mainnet, unless explicitly overridden.
        if (
            self.environment is BinanceEnvironment.MAINNET
            and self.rest_base_override is None
            and not any(marker in self.rest_base for marker in MAINNET_HOST_MARKERS)
        ):
            raise EndpointConfigError(
                f"environment=mainnet but rest_base={self.rest_base!r} is not a mainnet host"
            )

        # 4. Live trading requires double confirmation. Selecting the mainnet
        #    environment is not on its own sufficient to submit real orders.
        if self.enable_live_trading and not self.environment.submits_real_orders:
            raise EndpointConfigError(
                f"enable_live_trading=True is meaningless for "
                f"environment={self.environment.value}; real orders only reach "
                f"mainnet. Set BINANCE_ENVIRONMENT=mainnet explicitly."
            )

        # 5. Paper has no trading surface, and must not acquire one.
        if self.environment is BinanceEnvironment.PAPER:
            if self.rest_base or self.user_stream_ws:
                raise EndpointConfigError(
                    "paper environment must not define a REST or user-stream "
                    "endpoint; fills are simulated locally"
                )
            if not self.market_data_ws:
                raise EndpointConfigError("paper environment still needs market data")

        # 6. Every environment that trades needs all three surfaces.
        if self.environment.requires_credentials:
            for label, url in (
                ("rest_base", self.rest_base),
                ("user_stream_ws", self.user_stream_ws),
                ("market_data_ws", self.market_data_ws),
            ):
                if not url:
                    raise EndpointConfigError(
                        f"environment={self.environment.value} requires {label}"
                    )

    # -- accessors --------------------------------------------------------- #

    @property
    def is_mainnet(self) -> bool:
        return self.environment is BinanceEnvironment.MAINNET

    @property
    def uses_live_market_data(self) -> bool:
        """True when market data comes from mainnet.

        Surfaced deliberately: an operator reading a health endpoint should see
        that a testnet run is consuming real book data, because it changes how
        the results should be read.
        """
        return any(marker in self.market_data_ws for marker in MAINNET_HOST_MARKERS)

    @property
    def orders_are_real(self) -> bool:
        """The single question that matters. Both conditions required."""
        return self.environment.submits_real_orders and self.enable_live_trading

    def rest_url(self, path: str) -> str:
        """Join a path, rejecting spot paths outright.

        ``/api/v3/*`` on a futures base silently returns 404s that look like
        connectivity problems. The audited connectivity script called
        ``/api/v3/exchangeInfo``; this makes that mistake loud.
        """
        if not self.rest_base:
            raise EndpointConfigError(
                f"environment={self.environment.value} has no REST trading surface"
            )
        if path.startswith("/api/v3"):
            raise EndpointConfigError(
                f"{path} is a Binance SPOT path. USD-M futures uses /fapi/v1/* or /fapi/v2/*."
            )
        if not path.startswith("/"):
            raise EndpointConfigError(f"path must be absolute, got {path!r}")
        return f"{self.rest_base}{path}"

    def describe(self) -> str:
        """One-line summary for startup logs and health output."""
        mode = "REAL ORDERS" if self.orders_are_real else "no real orders"
        data = "mainnet data" if self.uses_live_market_data else "environment data"
        return f"binance[{self.environment.value}] {mode}, {data}, rest={self.rest_base or '-'}"


def _bool_from_env(value: str | None, *, default: bool = False) -> bool:
    if value is None or value == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}
