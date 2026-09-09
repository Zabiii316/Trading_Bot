from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from pydantic import TypeAdapter

from trading_contracts.events import RiskDecisionEvent, SignalEvent
from trading_live_execution import BinanceFuturesRestClient, BinanceLiveExecutionAdapter, config_from_env


async def main() -> None:
    parser = argparse.ArgumentParser(description="Submit one approved risk decision to Binance USD-M futures.")
    parser.add_argument("--signal", required=True, help="Path to SignalEvent JSON")
    parser.add_argument("--risk", required=True, help="Path to RiskDecisionEvent JSON")
    parser.add_argument("--dry-run", action="store_true", help="Validate inputs without submitting")
    args = parser.parse_args()

    signal = TypeAdapter(SignalEvent).validate_python(json.loads(Path(args.signal).read_text()))
    risk = TypeAdapter(RiskDecisionEvent).validate_python(json.loads(Path(args.risk).read_text()))
    config = config_from_env()
    print(f"Binance base_url={config.base_url} testnet={config.testnet} live_enabled={config.enable_live_trading}")
    if args.dry_run:
        print("dry_run=true; no order submitted")
        return
    client = BinanceFuturesRestClient(config)
    try:
        adapter = BinanceLiveExecutionAdapter(config, client)
        order, reasons = await adapter.submit_entry(signal=signal, risk_decision=risk, event_time_ms=risk.event_time_ms)
        if reasons:
            print(json.dumps({"submitted": False, "reasons": reasons}, indent=2))
            return
        print(order.model_dump_json(indent=2))
    finally:
        await client.aclose()


if __name__ == "__main__":
    asyncio.run(main())
