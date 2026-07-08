from __future__ import annotations

import time


def now_ms() -> int:
    return int(time.time_ns() // 1_000_000)
