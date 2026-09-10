from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for rel in ["libs/python", "services/avwap/python", "services/storage/python"]:
    path = str(ROOT / rel)
    if path not in sys.path:
        sys.path.insert(0, path)

from trading_avwap.engine import AnchoredVwapEngine
from trading_avwap.replay import parse_event, replay_events


def main() -> None:
    parser = argparse.ArgumentParser(description="Replay JSONL events through the Anchored VWAP engine")
    parser.add_argument("input", type=Path, help="Input JSONL file")
    parser.add_argument("--output", type=Path, default=None, help="Optional output JSONL path")
    args = parser.parse_args()

    events = []
    with args.input.open("r", encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                events.append(parse_event(json.loads(line)))
    out = replay_events(events, AnchoredVwapEngine())
    if args.output:
        with args.output.open("w", encoding="utf-8") as fh:
            for event in out:
                fh.write(event.model_dump_json() + "\n")
    print(f"processed_events={len(events)} emitted_avwap_events={len(out)}")


if __name__ == "__main__":
    main()
