from __future__ import annotations

import json
import sys
from pathlib import Path

from trading_contracts.events import EVENT_MODEL_REGISTRY


def main() -> int:
    if len(sys.argv) != 3:
        print("Usage: python scripts/validate_event.py <event.json> <ModelName>")
        print("Available models:", ", ".join(EVENT_MODEL_REGISTRY))
        return 2

    event_path = Path(sys.argv[1])
    model_name = sys.argv[2]
    model = EVENT_MODEL_REGISTRY.get(model_name)
    if model is None:
        print(f"Unknown model: {model_name}")
        return 2

    payload = json.loads(event_path.read_text(encoding="utf-8"))
    validated = model.model_validate(payload)
    print(validated.model_dump_json(indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
