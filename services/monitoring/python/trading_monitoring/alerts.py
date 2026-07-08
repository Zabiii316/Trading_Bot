from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


def load_alert_rules(path: str | Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as handle:
        loaded = yaml.safe_load(handle)
    if not isinstance(loaded, dict) or "groups" not in loaded:
        raise ValueError("Prometheus rules file must contain a top-level groups key")
    return loaded


def alert_names(rules: dict[str, Any]) -> list[str]:
    names: list[str] = []
    for group in rules.get("groups", []):
        for rule in group.get("rules", []):
            name = rule.get("alert")
            if name:
                names.append(str(name))
    return names
