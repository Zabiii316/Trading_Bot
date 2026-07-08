from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
LIB_PATH = str(ROOT / "libs/python")
if LIB_PATH not in sys.path:
    sys.path.insert(0, LIB_PATH)

from trading_contracts.events import EVENT_MODEL_REGISTRY

OUT_DIR = ROOT / "contracts" / "json_schema"


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for name, model in EVENT_MODEL_REGISTRY.items():
        schema = model.model_json_schema()
        path = OUT_DIR / f"{name}.schema.json"
        path.write_text(json.dumps(schema, indent=2, sort_keys=True), encoding="utf-8")
        print(f"wrote {path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
