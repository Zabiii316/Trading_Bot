from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def build_deployment_manifest(
    *,
    commit_sha: str,
    image_tag: str,
    stage: str,
    config_hash: str,
    schema_version: str = "1.0",
    generated_by: str = "phase15-controlled-live-deployment",
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "schema_version": schema_version,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "generated_by": generated_by,
        "commit_sha": commit_sha,
        "image_tag": image_tag,
        "stage": stage,
        "config_hash": config_hash,
        "extra": extra or {},
    }


def write_manifest(path: str | Path, manifest: dict[str, Any]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
