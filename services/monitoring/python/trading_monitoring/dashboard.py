from __future__ import annotations

import json
from pathlib import Path
from typing import Any


REQUIRED_DASHBOARD_KEYS = {"title", "panels", "schemaVersion"}


def load_dashboard(path: str | Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    missing = REQUIRED_DASHBOARD_KEYS - set(data)
    if missing:
        raise ValueError(f"Dashboard missing required keys: {sorted(missing)}")
    if not isinstance(data["panels"], list) or not data["panels"]:
        raise ValueError("Dashboard must contain at least one panel")
    return data


def dashboard_titles(directory: str | Path) -> list[str]:
    titles: list[str] = []
    for path in sorted(Path(directory).glob("*.json")):
        titles.append(str(load_dashboard(path)["title"]))
    return titles
