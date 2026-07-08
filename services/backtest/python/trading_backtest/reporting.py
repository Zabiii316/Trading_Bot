from __future__ import annotations

import json
from pathlib import Path

from .models import BacktestReport


def write_report_json(report: BacktestReport, output_path: str | Path) -> None:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report.as_dict(), indent=2, allow_nan=True), encoding="utf-8")


def format_summary(report: BacktestReport) -> str:
    s = report.summary
    pf = "inf" if s.profit_factor == float("inf") else f"{s.profit_factor:.4f}"
    lines = [
        "Backtest Summary",
        "================",
        f"Events processed:      {s.event_count}",
        f"Trades:                {s.trade_count}",
        f"Win rate:              {s.win_rate:.2%}",
        f"Net PnL:               {s.net_pnl_quote:.4f}",
        f"Net return:            {s.net_return_pct:.4f}%",
        f"Profit factor:         {pf}",
        f"Sharpe / trade:        {s.sharpe_per_trade:.4f}",
        f"Max drawdown:          {s.max_drawdown_quote:.4f} ({s.max_drawdown_pct:.4f}%)",
        f"Total fees:            {s.total_fees_quote:.4f}",
        f"Rejected signals:      {s.rejected_signal_count}",
        f"Expired signals:       {s.expired_signal_count}",
    ]
    return "\n".join(lines)
