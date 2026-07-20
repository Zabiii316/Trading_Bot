import hashlib
import hmac
import json
import os
import time
import urllib.parse
import urllib.request
import urllib.error

base_url = os.getenv(
    "BINANCE_TESTNET_BASE_URL",
    "https://testnet.binance.vision",
).rstrip("/")

api_key = os.getenv("BINANCE_TESTNET_API_KEY", "")
api_secret = os.getenv("BINANCE_TESTNET_API_SECRET", "")

symbol = os.getenv("TRADING_SYMBOLS", "BTCUSDT").split(",")[0].strip()
notional = os.getenv("MICRO_TRADE_NOTIONAL_USDT", "5")

if not api_key or not api_secret:
    raise SystemExit("Missing Binance testnet credentials")

# Get Binance Testnet server time.
with urllib.request.urlopen(
    base_url + "/api/v3/time",
    timeout=15,
) as response:
    server_time = json.loads(
        response.read().decode()
    )["serverTime"]

params = {
    "symbol": symbol,
    "side": "BUY",
    "type": "MARKET",
    "quoteOrderQty": notional,
    "recvWindow": "5000",
    "timestamp": str(server_time),
}

query = urllib.parse.urlencode(params)

signature = hmac.new(
    api_secret.encode(),
    query.encode(),
    hashlib.sha256,
).hexdigest()

url = (
    base_url
    + "/api/v3/order/test?"
    + query
    + "&signature="
    + signature
)

request = urllib.request.Request(
    url,
    method="POST",
    headers={
        "X-MBX-APIKEY": api_key,
        "Accept": "application/json",
    },
)

try:
    with urllib.request.urlopen(
        request,
        timeout=15,
    ) as response:
        body = response.read().decode()

        print("trade_permission_check_passed=True")
        print("test_order_endpoint=/api/v3/order/test")
        print("real_testnet_order_submitted=False")
        print("production_order_submitted=False")
        print("response_status=", response.status)
        print("response=", body or "{}")

except urllib.error.HTTPError as exc:
    body = exc.read().decode()

    try:
        error = json.loads(body)
    except Exception:
        error = {"raw": body}

    print("trade_permission_check_passed=False")
    print("real_testnet_order_submitted=False")
    print("error_code=", error.get("code"))
    print("error_message=", error.get("msg"))
