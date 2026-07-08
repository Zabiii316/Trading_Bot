from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from trading_contracts.enums import OrderSide, OrderType, TimeInForce, TradeSide
from trading_live_execution.config import BinanceLiveExecutionConfig
from trading_live_execution.mapping import (
    binance_order_type,
    closing_side_for_position,
    decimal_to_exchange,
    make_client_order_id,
    side_for_signal,
    to_binance_order_params,
)
from trading_live_execution.models import BinanceOrderRequest
from trading_live_execution.signing import canonical_query, sign_query, signed_query


def test_hmac_signature_matches_known_sha256() -> None:
    query = "symbol=BTCUSDT&side=BUY&type=MARKET&timestamp=1700000000000"
    signature = sign_query(query, "secret")
    assert signature == "c5bee7ef23d0f08ff08fe04022f745e9ff389ec6ea2ad8203e0a096b238dcf36"


def test_signed_query_preserves_parameter_order() -> None:
    params = [("symbol", "BTCUSDT"), ("timestamp", 1700000000000)]
    assert canonical_query(params) == "symbol=BTCUSDT&timestamp=1700000000000"
    assert signed_query(params, "secret").startswith("symbol=BTCUSDT&timestamp=1700000000000&signature=")


def test_mapping_marketable_limit_to_binance_limit_ioc() -> None:
    request = BinanceOrderRequest(
        symbol="btcusdt",
        side=OrderSide.BUY,
        order_type=OrderType.MARKETABLE_LIMIT,
        time_in_force=TimeInForce.IOC,
        quantity=Decimal("0.010000"),
        limit_price=Decimal("62000.5000"),
        reduce_only=True,
        client_order_id="tb14-test",
    )
    config = BinanceLiveExecutionConfig(api_key="k", api_secret="s")
    params = dict(to_binance_order_params(request, timestamp_ms=123, config=config))
    assert params["symbol"] == "BTCUSDT"
    assert params["side"] == "BUY"
    assert params["type"] == "LIMIT"
    assert params["timeInForce"] == "IOC"
    assert params["price"] == "62000.5"
    assert params["quantity"] == "0.01"
    assert params["reduceOnly"] is True


def test_side_helpers_and_client_order_id_length() -> None:
    assert side_for_signal(TradeSide.LONG) == OrderSide.BUY
    assert side_for_signal(TradeSide.SHORT) == OrderSide.SELL
    assert closing_side_for_position(Decimal("1.2")) == OrderSide.SELL
    assert closing_side_for_position(Decimal("-1.2")) == OrderSide.BUY
    assert binance_order_type(OrderType.MARKETABLE_LIMIT) == "LIMIT"
    client_id = make_client_order_id("tb14", UUID("00000000-0000-0000-0000-000000000001"), 7)
    assert len(client_id) <= 36
    assert client_id.startswith("tb14-")


def test_decimal_to_exchange_avoids_scientific_notation() -> None:
    assert decimal_to_exchange(Decimal("0.010000")) == "0.01"
    assert decimal_to_exchange(Decimal("62000.5000")) == "62000.5"
