#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from trading_backtest.models import BacktestConfig
from trading_backtest.replay import replay_backtest_file
from trading_backtest.reporting import format_summary, write_report_json


def main() -> None:
    parser = argparse.ArgumentParser(description="Run deterministic event-driven backtest replay")
    parser.add_argument("input", type=Path, help="Contract-valid JSONL replay file")
    parser.add_argument("--output", type=Path, default=Path("backtest_report.json"))
    parser.add_argument("--initial-equity", type=float, default=100_000.0)
    parser.add_argument("--risk-fraction", type=float, default=0.0025)
    parser.add_argument("--fee-bps", type=float, default=4.0)
    parser.add_argument("--slippage-bps", type=float, default=1.5)
    parser.add_argument("--latency-ms", type=int, default=250)
    args = parser.parse_args()

    config = BacktestConfig(
        initial_equity_quote=args.initial_equity,
        risk_fraction_per_trade=args.risk_fraction,
        fee_bps=args.fee_bps,
        slippage_bps=args.slippage_bps,
        latency_ms=args.latency_ms,
    )
    report = replay_backtest_file(args.input, config)
    write_report_json(report, args.output)
    print(format_summary(report))
    print(f"\nWrote report: {args.output}")


if __name__ == "__main__":
    main()
