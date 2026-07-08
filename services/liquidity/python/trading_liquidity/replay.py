from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable, Iterator

from .engine import LiquidityLevelEngine, LiquidityLevelEngineConfig
from .models import Bar


def load_bars_jsonl(path: str | Path) -> Iterator[Bar]:
    with Path(path).open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            payload = json.loads(line)
            yield Bar(**payload)


def replay_bars(bars: Iterable[Bar], config: LiquidityLevelEngineConfig | None = None):
    engine = LiquidityLevelEngine(config)
    for bar in bars:
        for event in engine.update(bar):
            yield event
