from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

sys.path.insert(0, str(ROOT / "libs" / "python"))
sys.path.insert(0, str(ROOT / "contracts"))
sys.path.insert(0, str(ROOT / "services" / "market_data" / "python"))
sys.path.insert(0, str(ROOT / "services" / "order_book" / "python"))

from trading_contracts.enums import Venue
from trading_contracts.events import DepthUpdateEvent, OrderBookSnapshotEvent
from trading_market_data.publisher import JsonlPublisher
from trading_market_data.serialization import loads_json
from trading_order_book.service import OrderBookReconstructionService
from trading_order_book.snapshot import BinanceDepthSnapshotClient


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Replay normalized depth/snapshot JSONL into reconstructed order books"
    )

    parser.add_argument(
        "--input",
        required=True,
        help="Input JSONL containing raw.depth_update and optional raw.order_book_snapshot events",
    )

    parser.add_argument(
        "--output",
        default="data/reconstructed_books.jsonl",
        help="Output JSONL file for reconstructed_book events",
    )

    parser.add_argument(
        "--symbol",
        default="BTCUSDT",
        help="Symbol to reconstruct, for example BTCUSDT",
    )

    parser.add_argument(
        "--fetch-snapshot",
        action="store_true",
        help="Fetch Binance REST snapshot before replaying depth updates",
    )

    parser.add_argument(
        "--snapshot-limit",
        type=int,
        default=1000,
        help="Depth limit for REST snapshot bootstrap",
    )

    return parser.parse_args()


async def main() -> None:
    args = parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    publisher = JsonlPublisher(str(output_path))

    snapshot_client = (
        BinanceDepthSnapshotClient(venue=Venue.BINANCE_USDM)
        if args.fetch_snapshot
        else None
    )

    service = OrderBookReconstructionService(
        symbol=args.symbol,
        publisher=publisher,
        snapshot_client=snapshot_client,
    )

    await service.start()

    processed_lines = 0
    skipped_lines = 0

    try:
        if args.fetch_snapshot:
            print(f"Fetching Binance REST snapshot for {args.symbol}...")
            await service.bootstrap_snapshot(limit=args.snapshot_limit)
            print("Snapshot loaded successfully.")

        with input_path.open("r") as f:
            for line in f:
                if not line.strip():
                    continue

                payload = loads_json(line)
                event_type = payload.get("event_type")
                symbol = payload.get("symbol")

                if symbol and symbol != args.symbol:
                    skipped_lines += 1
                    continue

                if event_type == "raw.order_book_snapshot":
                    await service.on_snapshot(
                        OrderBookSnapshotEvent.model_validate(payload)
                    )
                    processed_lines += 1

                elif event_type == "raw.depth_update":
                    await service.on_depth(
                        DepthUpdateEvent.model_validate(payload)
                    )
                    processed_lines += 1

                else:
                    skipped_lines += 1

    finally:
        await service.stop()

    print("Replay complete.")
    print(f"Input: {input_path}")
    print(f"Output: {output_path}")
    print(f"Processed lines: {processed_lines}")
    print(f"Skipped lines: {skipped_lines}")
    print(service.health)


if __name__ == "__main__":
    asyncio.run(main())