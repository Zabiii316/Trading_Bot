from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.extend([
    str(ROOT / "libs" / "python"),
    str(ROOT / "services" / "liquidity" / "python"),
])

from trading_liquidity.replay import load_bars_jsonl, replay_bars  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Replay OHLCV bars into liquidity-level events")
    parser.add_argument("input_jsonl", help="Path to normalized Bar JSONL")
    parser.add_argument("--output-jsonl", default="/tmp/liquidity_levels.jsonl")
    args = parser.parse_args()

    out = Path(args.output_jsonl)
    out.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with out.open("w", encoding="utf-8") as fh:
        for event in replay_bars(load_bars_jsonl(args.input_jsonl)):
            fh.write(event.model_dump_json() + "\n")
            count += 1
    print(json.dumps({"events_written": count, "output": str(out)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
