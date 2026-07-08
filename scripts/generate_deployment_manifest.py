#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services" / "deployment" / "python"))

from deployment.manifest import build_deployment_manifest, write_manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate immutable deployment manifest.")
    parser.add_argument("--commit-sha", required=True)
    parser.add_argument("--image-tag", required=True)
    parser.add_argument("--stage", required=True)
    parser.add_argument("--config-hash", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    manifest = build_deployment_manifest(
        commit_sha=args.commit_sha,
        image_tag=args.image_tag,
        stage=args.stage,
        config_hash=args.config_hash,
    )
    write_manifest(args.output, manifest)
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
