import json, os, subprocess, time, shutil
from pathlib import Path

OUT = Path("data/processed/phase17_historical_backtest_dataset_builder.json")
DATASET_DIR = Path("data/processed/backtest_datasets")

INPUTS = {
    "coverage_audit": "data/processed/phase17_historical_data_coverage_audit.json",
    "phase17_baseline": "data/processed/phase17_strategy_hardening_baseline.json",
}

TARGET_SYMBOLS = ["BTCUSDT", "ETHUSDT", "BNBUSDT"]
SCAN_DIRS = ["data/raw", "data/processed"]

def run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True)

def git_clean():
    return run(["git", "status", "--short"]).stdout.strip() == ""

def load_json(path):
    p = Path(path)
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text())
    except Exception:
        return {}

def safe_read_json_lines(path):
    records = []
    try:
        for line in path.read_text(errors="ignore").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except Exception:
                continue
    except Exception:
        pass
    return records

def record_symbol(record):
    if isinstance(record, dict):
        for key in ["symbol", "s", "pair"]:
            if key in record and record[key]:
                return str(record[key]).upper()
    return ""

def record_time(record):
    if not isinstance(record, dict):
        return None
    for key in ["event_time_ms", "received_time_ms", "time_ms", "timestamp_ms", "start_time_ms", "t", "T"]:
        value = record.get(key)
        if isinstance(value, int):
            return value
        if isinstance(value, str) and value.isdigit():
            return int(value)
    return None

def collect_symbol_records(symbol):
    rows = []
    source_files = []

    for folder in SCAN_DIRS:
        root = Path(folder)
        if not root.exists():
            continue

        for path in sorted(root.rglob("*")):
            if not path.is_file():
                continue

            if path.suffix.lower() not in [".jsonl", ".json"]:
                continue

            if "phase17_" in path.name:
                continue

            path_text_match = symbol.lower() in str(path).lower()
            records = []

            if path.suffix.lower() == ".jsonl":
                records = safe_read_json_lines(path)
            else:
                try:
                    obj = json.loads(path.read_text(errors="ignore"))
                    if isinstance(obj, list):
                        records = [x for x in obj if isinstance(x, dict)]
                    elif isinstance(obj, dict):
                        records = [obj]
                except Exception:
                    records = []

            selected = []
            for rec in records:
                sym = record_symbol(rec)
                if sym == symbol or path_text_match:
                    selected.append(rec)

            if selected:
                source_files.append(str(path))
                rows.extend(selected)

    rows.sort(key=lambda r: record_time(r) if record_time(r) is not None else 0)
    return rows, source_files

flags = {
    "BINANCE_TESTNET": os.getenv("BINANCE_TESTNET", ""),
    "BINANCE_USE_TESTNET": os.getenv("BINANCE_USE_TESTNET", ""),
    "BINANCE_ENABLE_LIVE_TRADING": os.getenv("BINANCE_ENABLE_LIVE_TRADING", ""),
    "LIVE_TRADING_ALLOWED": os.getenv("LIVE_TRADING_ALLOWED", ""),
}

safe_mode = flags["BINANCE_ENABLE_LIVE_TRADING"] == "false" and flags["LIVE_TRADING_ALLOWED"] == "false"
inputs_present = {k: Path(v).exists() for k, v in INPUTS.items()}

DATASET_DIR.mkdir(parents=True, exist_ok=True)

datasets = {}
for symbol in TARGET_SYMBOLS:
    rows, sources = collect_symbol_records(symbol)
    out_path = DATASET_DIR / f"{symbol.lower()}_phase17_backtest_dataset.jsonl"

    if rows:
        with out_path.open("w") as f:
            for row in rows:
                f.write(json.dumps(row, separators=(",", ":")) + "\n")

    times = [record_time(r) for r in rows if record_time(r) is not None]

    datasets[symbol] = {
        "record_count": len(rows),
        "source_file_count": len(sources),
        "source_files": sources[:20],
        "dataset_path": str(out_path) if rows else "",
        "first_time_ms": min(times) if times else None,
        "last_time_ms": max(times) if times else None,
        "ready_for_backtest": len(rows) > 0,
    }

ready_symbols = [s for s, d in datasets.items() if d["ready_for_backtest"]]
missing_symbols = [s for s, d in datasets.items() if not d["ready_for_backtest"]]

report = {
    "phase": "phase_17_3_historical_backtest_dataset_builder",
    "generated_at_unix": int(time.time()),
    "scope": "historical_backtest_dataset_builder_only",
    "safety_flags": flags,
    "safe_mode_active": safe_mode,
    "inputs_present": inputs_present,
    "all_inputs_present": all(inputs_present.values()),
    "git_working_tree_clean": git_clean(),
    "target_symbols": TARGET_SYMBOLS,
    "datasets": datasets,
    "ready_symbols": ready_symbols,
    "missing_symbols": missing_symbols,
    "approved_for_micro_live_execution": False,
    "approved_for_real_live_trading": False,
    "decision": "HISTORICAL_BACKTEST_DATASET_BUILT_PARTIAL_DATASET_EXPANSION_STILL_REQUIRED",
    "next_phase": "Phase 17.4 — Baseline Historical Backtest Runner",
    "safety_notes": [
        "This phase builds local backtest datasets only.",
        "This phase does not approve live trading.",
        "This phase does not submit Binance orders.",
        "Missing symbols must be collected before full multi-symbol validation.",
    ],
}

OUT.write_text(json.dumps(report, indent=2))

print(f"Report written to: {OUT}")
print(f"safe_mode_active={safe_mode}")
print(f"ready_symbols={','.join(ready_symbols) if ready_symbols else 'none'}")
print(f"missing_symbols={','.join(missing_symbols) if missing_symbols else 'none'}")
print("approved_for_micro_live_execution=False")
print("approved_for_real_live_trading=False")
print(f"decision={report['decision']}")
