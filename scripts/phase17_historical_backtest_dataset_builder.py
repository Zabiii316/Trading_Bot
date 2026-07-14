import json, os, subprocess, time
from pathlib import Path

OUT = Path("data/processed/phase17_historical_backtest_dataset_builder.json")
DATASET_DIR = Path("data/processed/backtest_datasets")

TARGET_SYMBOLS = ["BTCUSDT", "ETHUSDT", "BNBUSDT"]
SCAN_DIRS = ["data/raw", "data/processed"]
MAX_RECORDS_PER_SYMBOL = 20000
MAX_FILE_SIZE_BYTES = 80_000_000

def run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True)

def git_clean():
    return run(["git", "status", "--short"]).stdout.strip() == ""

def get_symbol(row):
    if not isinstance(row, dict):
        return ""
    for key in ["symbol", "s", "pair"]:
        value = row.get(key)
        if value:
            return str(value).upper()
    return ""

def get_time(row):
    if not isinstance(row, dict):
        return 0
    for key in ["event_time_ms", "received_time_ms", "time_ms", "timestamp_ms", "start_time_ms", "t", "T"]:
        value = row.get(key)
        if isinstance(value, int):
            return value
        if isinstance(value, str) and value.isdigit():
            return int(value)
    return 0

def should_scan(path):
    if not path.is_file():
        return False
    if path.suffix.lower() != ".jsonl":
        return False
    if "phase16_" in path.name or "phase17_" in path.name:
        return False
    if "backtest_datasets" in str(path):
        return False
    try:
        if path.stat().st_size > MAX_FILE_SIZE_BYTES:
            return False
    except Exception:
        return False
    return True

def collect(symbol):
    rows = []
    sources = []

    for folder in SCAN_DIRS:
        root = Path(folder)
        if not root.exists():
            continue

        for path in sorted(root.rglob("*.jsonl")):
            if len(rows) >= MAX_RECORDS_PER_SYMBOL:
                break

            if not should_scan(path):
                continue

            used = False

            try:
                with path.open("r", errors="ignore") as f:
                    for line in f:
                        if len(rows) >= MAX_RECORDS_PER_SYMBOL:
                            break

                        line = line.strip()
                        if not line or "{" not in line:
                            continue

                        try:
                            row = json.loads(line)
                        except Exception:
                            continue

                        row_symbol = get_symbol(row)
                        path_match = symbol.lower() in str(path).lower()

                        if row_symbol == symbol or path_match:
                            rows.append(row)
                            used = True
            except Exception:
                continue

            if used:
                sources.append(str(path))

    rows.sort(key=get_time)
    return rows, sources

flags = {
    "BINANCE_TESTNET": os.getenv("BINANCE_TESTNET", ""),
    "BINANCE_USE_TESTNET": os.getenv("BINANCE_USE_TESTNET", ""),
    "BINANCE_ENABLE_LIVE_TRADING": os.getenv("BINANCE_ENABLE_LIVE_TRADING", ""),
    "LIVE_TRADING_ALLOWED": os.getenv("LIVE_TRADING_ALLOWED", ""),
}

safe_mode = flags["BINANCE_ENABLE_LIVE_TRADING"] == "false" and flags["LIVE_TRADING_ALLOWED"] == "false"

DATASET_DIR.mkdir(parents=True, exist_ok=True)

datasets = {}

for symbol in TARGET_SYMBOLS:
    rows, sources = collect(symbol)
    dataset_path = DATASET_DIR / f"{symbol.lower()}_phase17_backtest_dataset.jsonl"

    if rows:
        with dataset_path.open("w") as f:
            for row in rows:
                f.write(json.dumps(row, separators=(",", ":")) + "\n")

    times = [get_time(r) for r in rows if get_time(r)]

    datasets[symbol] = {
        "record_count": len(rows),
        "source_file_count": len(sources),
        "source_files": sources[:20],
        "dataset_path": str(dataset_path) if rows else "",
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
    "git_working_tree_clean": git_clean(),
    "max_records_per_symbol": MAX_RECORDS_PER_SYMBOL,
    "datasets": datasets,
    "ready_symbols": ready_symbols,
    "missing_symbols": missing_symbols,
    "approved_for_micro_live_execution": False,
    "approved_for_real_live_trading": False,
    "decision": "HISTORICAL_BACKTEST_DATASET_BUILT_PARTIAL_DATASET_EXPANSION_STILL_REQUIRED",
    "next_phase": "Phase 17.4 — Baseline Historical Backtest Runner",
}

OUT.write_text(json.dumps(report, indent=2))

print(f"Report written to: {OUT}")
print(f"safe_mode_active={safe_mode}")
print(f"ready_symbols={','.join(ready_symbols) if ready_symbols else 'none'}")
print(f"missing_symbols={','.join(missing_symbols) if missing_symbols else 'none'}")
print("approved_for_micro_live_execution=False")
print("approved_for_real_live_trading=False")
print(f"decision={report['decision']}")
