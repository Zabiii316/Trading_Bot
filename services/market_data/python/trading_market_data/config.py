from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Iterable


class BinanceMarket(str, Enum):
    SPOT = "spot"
    USDM_FUTURES = "usdm_futures"


@dataclass(frozen=True)
class RecorderConfig:
    """Runtime configuration for the Binance market-data recorder.

    The recorder uses public market-data streams only. API keys are intentionally not
    required in Phase 2.
    """

    symbols: tuple[str, ...] = ("BTCUSDT", "ETHUSDT")
    market: BinanceMarket = BinanceMarket.USDM_FUTURES
    streams: tuple[str, ...] = ("aggTrade", "trade", "depth@100ms", "bookTicker")
    publisher: str = "jsonl"  # jsonl | stdout | memory | redpanda
    jsonl_path: str = "data/raw/binance_market_data.jsonl"
    kafka_bootstrap_servers: str = "localhost:9092"
    kafka_client_id: str = "market-data-recorder"
    reconnect_initial_delay_s: float = 1.0
    reconnect_max_delay_s: float = 30.0
    reconnect_jitter_s: float = 0.25
    websocket_read_timeout_s: float = 30.0
    max_queue_size: int = 100_000
    enable_raw_payload: bool = True
    include_stream_name: bool = True
    source: str = "binance_market_data_recorder"

    def __post_init__(self) -> None:
        normalized = tuple(symbol.upper().strip() for symbol in self.symbols)
        object.__setattr__(self, "symbols", normalized)
        if not normalized:
            raise ValueError("At least one symbol must be configured")
        if self.reconnect_initial_delay_s <= 0:
            raise ValueError("reconnect_initial_delay_s must be positive")
        if self.reconnect_max_delay_s < self.reconnect_initial_delay_s:
            raise ValueError("reconnect_max_delay_s must be >= reconnect_initial_delay_s")
        if self.max_queue_size <= 0:
            raise ValueError("max_queue_size must be positive")

    @property
    def ws_base_url(self) -> str:
        if self.market == BinanceMarket.SPOT:
            return "wss://stream.binance.com:9443/stream"
        if self.market == BinanceMarket.USDM_FUTURES:
            return "wss://fstream.binance.com/stream"
        raise ValueError(f"Unsupported Binance market: {self.market}")

    @property
    def venue_value(self) -> str:
        if self.market == BinanceMarket.SPOT:
            return "binance_spot"
        if self.market == BinanceMarket.USDM_FUTURES:
            return "binance_usdm"
        raise ValueError(f"Unsupported Binance market: {self.market}")

    @property
    def market_type_value(self) -> str:
        if self.market == BinanceMarket.SPOT:
            return "spot"
        if self.market == BinanceMarket.USDM_FUTURES:
            return "perpetual_futures"
        raise ValueError(f"Unsupported Binance market: {self.market}")

    def stream_names(self) -> list[str]:
        """Return Binance stream names such as btcusdt@aggTrade."""
        return [f"{symbol.lower()}@{stream}" for symbol in self.symbols for stream in self.streams]

    def combined_stream_url(self) -> str:
        streams = "/".join(self.stream_names())
        return f"{self.ws_base_url}?streams={streams}"

    @classmethod
    def from_env(cls, env: dict[str, str] | None = None) -> "RecorderConfig":
        import os

        source = env if env is not None else os.environ

        def parse_symbols(value: str | None) -> tuple[str, ...]:
            if not value:
                return cls.symbols
            return tuple(part.strip().upper() for part in value.split(",") if part.strip())

        def parse_streams(value: str | None) -> tuple[str, ...]:
            if not value:
                return cls.streams
            return tuple(part.strip() for part in value.split(",") if part.strip())

        market_raw = source.get("BINANCE_MARKET", BinanceMarket.USDM_FUTURES.value)
        return cls(
            symbols=parse_symbols(source.get("SYMBOLS")),
            market=BinanceMarket(market_raw),
            streams=parse_streams(source.get("STREAMS")),
            publisher=source.get("PUBLISHER", "jsonl"),
            jsonl_path=source.get("JSONL_PATH", "data/raw/binance_market_data.jsonl"),
            kafka_bootstrap_servers=source.get("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092"),
            kafka_client_id=source.get("KAFKA_CLIENT_ID", "market-data-recorder"),
            reconnect_initial_delay_s=float(source.get("RECONNECT_INITIAL_DELAY_S", "1.0")),
            reconnect_max_delay_s=float(source.get("RECONNECT_MAX_DELAY_S", "30.0")),
            reconnect_jitter_s=float(source.get("RECONNECT_JITTER_S", "0.25")),
            websocket_read_timeout_s=float(source.get("WEBSOCKET_READ_TIMEOUT_S", "30.0")),
            max_queue_size=int(source.get("MAX_QUEUE_SIZE", "100000")),
            enable_raw_payload=source.get("ENABLE_RAW_PAYLOAD", "true").lower() in {"1", "true", "yes"},
        )
