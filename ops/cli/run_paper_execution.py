from __future__ import annotations

import argparse
from pathlib import Path

from trading_paper_execution.models import PaperExecutionConfig
from trading_paper_execution.replay import load_jsonl_events, run_paper_replay


def main() -> None:
    parser = argparse.ArgumentParser(description="Replay paper execution events from JSONL")
    parser.add_argument("path", type=Path, nargs="?", default=Path("examples/paper/paper_replay.jsonl"))
    parser.add_argument("--fee-bps", type=float, default=4.0)
    parser.add_argument("--slippage-bps", type=float, default=1.0)
    args = parser.parse_args()
    events = load_jsonl_events(args.path)
    result = run_paper_replay(events, PaperExecutionConfig(fee_bps=args.fee_bps, slippage_bps=args.slippage_bps))
    print(f"orders={result['orders']}")
    print(f"positions={result['positions']}")
    print(f"emitted_events={len(result['emitted_events'])}")
    print(f"rejected={len(result['rejected'])}")
    print(f"reconciliation_healthy={result['reconciliation'].is_healthy}")


if __name__ == "__main__":
    main()
