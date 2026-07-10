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
REPORT_PATH = Path("data/processed/phase16_testnet_execution_report.json")
OUTPUT_PATH = Path("data/processed/phase16_testnet_reconciliation_report.json")


def signed_get(path: str, params: dict[str, str]) -> dict:
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
        method="GET",
    )

    with urllib.request.urlopen(req, timeout=20) as response:
        raw = response.read().decode("utf-8")
        return json.loads(raw)


def main() -> None:
    if not REPORT_PATH.exists():
        raise RuntimeError(f"Missing Phase 16.5 report: {REPORT_PATH}")

    execution_report = json.loads(REPORT_PATH.read_text())

    venue_order_id = execution_report.get("venue_order_id")
    if not venue_order_id:
        raise RuntimeError("No venue_order_id found in Phase 16.5 report.")

    symbol = "BTCUSDT"

    print(f"Reconciling Binance Futures testnet order_id={venue_order_id} symbol={symbol}")

    order_result = signed_get(
        "/fapi/v1/order",
        {
            "symbol": symbol,
            "orderId": str(venue_order_id),
        },
    )

    position_result = signed_get(
        "/fapi/v2/positionRisk",
        {
            "symbol": symbol,
        },
    )

    account_result = signed_get(
        "/fapi/v2/account",
        {},
    )

    order_status = str(order_result.get("status", "")).upper()
    order_symbol = order_result.get("symbol")
    order_id_confirmed = str(order_result.get("orderId")) == str(venue_order_id)

    accepted_statuses = {
        "NEW",
        "PARTIALLY_FILLED",
        "FILLED",
        "CANCELED",
        "EXPIRED",
    }

    matching_positions = []
    if isinstance(position_result, list):
        matching_positions = [
            p for p in position_result
            if p.get("symbol") == symbol
        ]
    elif isinstance(position_result, dict):
        matching_positions = [position_result]

    non_zero_positions = []
    for pos in matching_positions:
        amt = float(pos.get("positionAmt", "0") or 0)
        if abs(amt) > 0:
            non_zero_positions.append(pos)

    report = {
        "phase": "phase_16_6_testnet_order_reconciliation",
        "generated_at_unix": int(time.time()),
        "execution_report_source": str(REPORT_PATH),
        "binance_base_url": BASE_URL,
        "symbol": symbol,
        "venue_order_id": str(venue_order_id),
        "order_query": {
            "order_id_confirmed": order_id_confirmed,
            "symbol_confirmed": order_symbol == symbol,
            "status": order_status,
            "status_accepted": order_status in accepted_statuses,
            "raw": order_result,
        },
        "position_check": {
            "positions_found": len(matching_positions),
            "non_zero_positions": len(non_zero_positions),
            "raw": matching_positions,
        },
        "account_check": {
            "can_query_account": isinstance(account_result, dict),
            "available_balance_present": "availableBalance" in account_result,
            "total_wallet_balance_present": "totalWalletBalance" in account_result,
        },
        "passed": (
            order_id_confirmed
            and order_symbol == symbol
            and order_status in accepted_statuses
            and isinstance(account_result, dict)
        ),
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(report, indent=2))

    print(f"Order status: {order_status}")
    print(f"Order ID confirmed: {order_id_confirmed}")
    print(f"Non-zero positions: {len(non_zero_positions)}")
    print(f"Reconciliation report written to: {OUTPUT_PATH}")
    print(f"passed={report['passed']}")


if __name__ == "__main__":
    main()
