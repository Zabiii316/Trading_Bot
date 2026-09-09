#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "deployment" / "python"))

from deployment import CapitalControls, OperationalSnapshot, ProductionReadinessValidator


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Phase 15 production-readiness gates.")
    parser.add_argument("--snapshot", required=True, help="Path to operational snapshot JSON")
    parser.add_argument("--capital", required=True, help="Path to capital controls JSON")
    parser.add_argument("--output", help="Optional readiness report output JSON")
    args = parser.parse_args()

    snapshot = OperationalSnapshot.model_validate_json(Path(args.snapshot).read_text())
    capital = CapitalControls.model_validate_json(Path(args.capital).read_text())
    report = ProductionReadinessValidator().evaluate(snapshot, capital)
    payload = report.model_dump(mode="json")
    rendered = json.dumps(payload, indent=2, sort_keys=True)
    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(rendered + "\n")
    print(rendered)
    return 1 if report.blocking_failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
