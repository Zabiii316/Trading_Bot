from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
for rel in [
    "libs/python",
    "services/features/python",
    "services/sweep/python",
    "services/avwap/python",
    "services/signals/python",
]:
    p = str(ROOT / rel)
    if p not in sys.path:
        sys.path.insert(0, p)

from trading_signals.replay import replay_file


def main() -> None:
    parser = argparse.ArgumentParser(description="Replay events through the Phase 9 signal scorer")
    parser.add_argument("path", type=Path, help="JSONL file containing book/order-flow/sweep/AVWAP events")
    args = parser.parse_args()
    signals = replay_file(args.path)
    for signal in signals:
        print(signal.model_dump_json())
    print(f"emitted_signals={len(signals)}", file=sys.stderr)


if __name__ == "__main__":
    main()
