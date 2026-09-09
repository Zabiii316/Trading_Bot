#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from trading_sweep.replay import replay_file


def main() -> int:
    parser = argparse.ArgumentParser(description="Replay liquidity/order-flow/book events into the sweep state machine")
    parser.add_argument("input", type=Path, help="JSONL file containing liquidity.level, features.order_flow and book.reconstructed events")
    parser.add_argument("--output", type=Path, default=None, help="Optional JSONL output for liquidity.sweep events")
    args = parser.parse_args()

    events = replay_file(args.input)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("w", encoding="utf-8") as f:
            for event in events:
                f.write(event.model_dump_json() + "\n")
    else:
        for event in events:
            print(event.model_dump_json())
    print(json.dumps({"emitted": len(events)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
