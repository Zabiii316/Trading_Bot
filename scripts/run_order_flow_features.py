#!/usr/bin/env python
from __future__ import annotations

import argparse
from pathlib import Path

from trading_features.replay import replay_file


def main() -> None:
    parser = argparse.ArgumentParser(description="Replay raw market data into order-flow feature events")
    parser.add_argument("--input", required=True, help="Input JSONL file containing trades/snapshots/depth updates")
    parser.add_argument("--output", required=True, help="Output JSONL file for OrderFlowFeatureEvent rows")
    parser.add_argument("--depth", type=int, default=20, help="Top depth levels used for book features")
    args = parser.parse_args()
    count = replay_file(Path(args.input), Path(args.output), depth=args.depth)
    print(f"emitted_order_flow_events={count}")


if __name__ == "__main__":
    main()
