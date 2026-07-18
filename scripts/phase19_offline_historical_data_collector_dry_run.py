import json, time
from pathlib import Path

CONFIG = Path("data/processed/phase19_strategy_rework/offline_historical_data_collection_config.json")
OUT = Path("data/processed/phase19_strategy_rework/offline_historical_data_collection_dry_run_preview.json")

def load_json(path):
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except Exception:
        return {}

def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2))

config = load_json(CONFIG)
targets = config.get("targets", [])

preview = {
    "phase": "phase_19_7_offline_historical_data_collector_dry_run",
    "created_at_unix": int(time.time()),
    "mode": "dry_run_only",
    "download_started": False,
    "download_completed": False,
    "execution_allowed": False,
    "network_download_allowed": False,
    "paper_shadow_allowed": False,
    "live_trading_allowed": False,
    "exchange_order_submission_allowed": False,
    "target_count": len(targets),
    "targets": targets,
    "next_step": "manual_review_before_any_offline_data_import_or_collection"
}

write_json(OUT, preview)

print(f"Dry-run preview written to: {OUT}")
print("mode=dry_run_only")
print("download_started=False")
print("execution_allowed=False")
print("paper_shadow_allowed=False")
print("live_trading_allowed=False")
print("exchange_order_submission_allowed=False")
print(f"target_count={len(targets)}")
