#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from trading_risk.models import AccountState, RiskLimits
from trading_risk.replay import iter_jsonl_events, run_risk_replay


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Phase 11 risk engine over a JSONL replay file")
    parser.add_argument("input", type=Path, help="Contract-valid JSONL input containing signal/kill-switch events")
    parser.add_argument("--output", type=Path, default=None, help="Optional JSONL output for risk decisions")
    parser.add_argument("--equity", type=float, default=100_000.0)
    parser.add_argument("--available-margin", type=float, default=None)
    parser.add_argument("--risk-fraction", type=float, default=0.0025)
    args = parser.parse_args()

    account = AccountState(equity_quote=args.equity, available_margin_quote=args.available_margin)
    limits = RiskLimits(risk_fraction_per_trade=args.risk_fraction)
    decisions = run_risk_replay(iter_jsonl_events(args.input), account=account, limits=limits)

    lines = [event.model_dump_json() for event in decisions]
    if args.output:
        args.output.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    else:
        for line in lines:
            print(line)

    decision_count = sum(1 for e in decisions if (e.event_type.value if hasattr(e.event_type, "value") else str(e.event_type)) == "risk.decision")
    print(f"risk decisions emitted: {decision_count}")


if __name__ == "__main__":
    main()
