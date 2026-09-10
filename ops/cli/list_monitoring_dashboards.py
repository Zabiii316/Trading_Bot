#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

from trading_monitoring.dashboard import dashboard_titles


ROOT = Path(__file__).resolve().parents[2]


def main() -> None:
    for title in dashboard_titles(ROOT / "infra" / "grafana" / "dashboards"):
        print(title)


if __name__ == "__main__":
    main()
