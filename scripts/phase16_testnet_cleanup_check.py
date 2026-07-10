from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
import urllib.parse
import urllib.request
from pathlib import Path


BASE_URL = "https://testnet.binancefuture.com"
SYMBOL = "BTCUSDT"
OUTPUT_PATH = Path("data/processed/phase16_testnet_cleanup_report.json")


def signed_request(method: str, path: str, params: dict[str, str]) -> object:
    api_key = os.getenv("BINANCE_API_KEY")
    api_secret = os.getenv("BINANCE_API_SECRET")

    if not api_key or not api_secret:
        raise RuntimeError("BINANCE_API_KEY and BINANCE_API_SECRET are required.")

    params = dict(params)
    params["timestamp"] = str(int(time.time() * 1000))
    params["recvWindow"] = "5000"

    query = urllib.parse.urlencode(params)
    signature = hmac.new(
        api_secret.encode("utf-8"),
        query.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    url = f"{BASE_URL}{path}?{query}&signature={signature}"

    req = urllib.request.Request(
        url,
        headers={"X-MBX-APIKEY": api_key},
        method=method,
    )

    with urllib.request.urlopen(req, timeout=20) as response:
        raw = response.read().decode("utf-8")
        return json.loads(raw) if raw else {}


def main() -> None:
    print("Phase 16.7 — Testnet Cleanup & Open Order Safety Check")
    print(f"Base URL: {BASE_URL}")
    print(f"Symbol: {SYMBOL}")

    open_orders_before = signed_request(
        "GET",
        "/fapi/v1/openOrders",
        {"symbol": SYMBOL},
    )

    open_count_before = len(open_orders_before) if isinstance(open_orders_before, list) else 0

    cancel_result = None
    if open_count_before > 0:
        print(f"Open orders before cleanup: {open_count_before}")
        print("Cancelling all open testnet orders...")
        cancel_result = signed_request(
            "DELETE",
            "/fapi/v1/allOpenOrders",
            {"symbol": SYMBOL},
        )
    else:
        print("No open orders found before cleanup.")

    time.sleep(2)

    open_orders_after = signed_request(
        "GET",
        "/fapi/v1/openOrders",
        {"symbol": SYMBOL},
    )

    position_result = signed_request(
        "GET",
        "/fapi/v2/positionRisk",
        {"symbol": SYMBOL},
    )

    open_count_after = len(open_orders_after) if isinstance(open_orders_after, list) else 0

    matching_positions = []
    if isinstance(position_result, list):
        matching_positions = [p for p in position_result if p.get("symbol") == SYMBOL]
    elif isinstance(position_result, dict):
        matching_positions = [position_result]

    non_zero_positions = []
    for pos in matching_positions:
        amount = float(pos.get("positionAmt", "0") or 0)
        if abs(amount) > 0:
            non_zero_positions.append(pos)

    report = {
        "phase": "phase_16_7_testnet_cleanup_check",
        "generated_at_unix": int(time.time()),
        "binance_base_url": BASE_URL,
        "symbol": SYMBOL,
        "open_orders_before": open_count_before,
        "open_orders_after": open_count_after,
        "cancel_attempted": open_count_before > 0,
        "cancel_result": cancel_result,
        "position_check": {
            "positions_found": len(matching_positions),
            "non_zero_positions": len(non_zero_positions),
            "raw": matching_positions,
        },
        "passed": open_count_after == 0,
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(report, indent=2))

    print(f"Open orders after cleanup: {open_count_after}")
    print(f"Non-zero positions: {len(non_zero_positions)}")
    print(f"Report written to: {OUTPUT_PATH}")
    print(f"passed={report['passed']}")

    if non_zero_positions:
        print("")
        print("⚠️ Non-zero testnet position detected.")
        print("Do not proceed to micro-live planning until this is reviewed.")


if __name__ == "__main__":
    main()
