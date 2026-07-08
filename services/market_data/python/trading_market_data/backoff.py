from __future__ import annotations

import random
from dataclasses import dataclass


@dataclass
class ExponentialBackoff:
    initial_delay_s: float = 1.0
    max_delay_s: float = 30.0
    jitter_s: float = 0.25
    attempt: int = 0

    def reset(self) -> None:
        self.attempt = 0

    def next_delay(self) -> float:
        delay = min(self.max_delay_s, self.initial_delay_s * (2 ** self.attempt))
        self.attempt += 1
        if self.jitter_s > 0:
            delay += random.uniform(0, self.jitter_s)
        return delay
