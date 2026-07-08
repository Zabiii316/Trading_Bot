from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class BinanceLiveExecutionConfig:
    """Configuration for the USD-M Futures live execution adapter.

    The adapter is safe by default: testnet is enabled, live trading is disabled,
    and API credentials must be supplied from the environment or secret manager.
    """

    api_key: str = ""
    api_secret: str = ""
    testnet: bool = True
    enable_live_trading: bool = False
    recv_window_ms: int = 5_000
    request_timeout_s: float = 5.0
    max_retries: int = 2
    retry_backoff_s: float = 0.25
    one_way_mode: bool = True
    default_time_in_force: str = "IOC"
    client_order_prefix: str = "tb14"
    max_client_order_id_len: int = 36
    fail_closed_on_reconciliation_error: bool = True
    max_open_orders_per_symbol: int = 10
    base_url_override: str | None = None

    @property
    def base_url(self) -> str:
        if self.base_url_override:
            return self.base_url_override.rstrip("/")
        return "https://testnet.binancefuture.com" if self.testnet else "https://fapi.binance.com"

    def validate(self) -> None:
        if not self.api_key:
            raise ValueError("api_key is required")
        if not self.api_secret:
            raise ValueError("api_secret is required")
        if self.recv_window_ms <= 0 or self.recv_window_ms > 60_000:
            raise ValueError("recv_window_ms must be in 1..60000")
        if self.request_timeout_s <= 0:
            raise ValueError("request_timeout_s must be positive")
        if self.max_retries < 0:
            raise ValueError("max_retries cannot be negative")
        if self.retry_backoff_s < 0:
            raise ValueError("retry_backoff_s cannot be negative")
        if not self.testnet and not self.enable_live_trading:
            # Live base URL can still be used for read-only reconciliation if desired, but order submission
            # will be blocked by the adapter unless enable_live_trading is true.
            return


def bool_from_env(value: str | None, *, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def config_from_env() -> BinanceLiveExecutionConfig:
    return BinanceLiveExecutionConfig(
        api_key=os.getenv("BINANCE_API_KEY", ""),
        api_secret=os.getenv("BINANCE_API_SECRET", ""),
        testnet=bool_from_env(os.getenv("BINANCE_TESTNET"), default=True),
        enable_live_trading=bool_from_env(os.getenv("BINANCE_ENABLE_LIVE_TRADING"), default=False),
        recv_window_ms=int(os.getenv("BINANCE_RECV_WINDOW_MS", "5000")),
        request_timeout_s=float(os.getenv("BINANCE_REQUEST_TIMEOUT_S", "5.0")),
        max_retries=int(os.getenv("BINANCE_MAX_RETRIES", "2")),
        retry_backoff_s=float(os.getenv("BINANCE_RETRY_BACKOFF_S", "0.25")),
        one_way_mode=bool_from_env(os.getenv("BINANCE_ONE_WAY_MODE"), default=True),
        default_time_in_force=os.getenv("BINANCE_DEFAULT_TIF", "IOC"),
        client_order_prefix=os.getenv("BINANCE_CLIENT_ORDER_PREFIX", "tb14"),
        base_url_override=os.getenv("BINANCE_BASE_URL") or None,
    )
