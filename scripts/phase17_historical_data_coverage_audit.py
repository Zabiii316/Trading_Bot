import json, os, subprocess, time
from pathlib import Path

OUT = Path("data/processed/phase17_historical_data_coverage_audit.json")

INPUTS = {
    "phase17_baseline": "data/processed/phase17_strategy_hardening_baseline.json",
    "phase16_release": "data/processed/phase16_final_documentation_repository_release.json",
}

TARGET_SYMBOLS = ["BTCUSDT", "ETHUSDT", "BNBUSDT"]
SCAN_DIRS = ["data/raw", "data/processed"]

def run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True)

def git_clean():
    return run(["git", "status", "--short"]).stdout.strip() == ""

def git_commit():
    r = run(["git", "rev-parse", "HEAD"])
    return r.stdout.strip() if r.returncode == 0 else ""

def count_lines(path: Path) -> int:
    try:
        with path.open("rb") as f:
            return sum(1 for _ in f)
    except Exception:
        return 0

def file_record(path: Path) -> dict:
    stat = path.stat()
    suffix = path.suffix.lower()
    should_count = suffix in [".jsonl", ".json", ".csv", ".txt"]
    return {
        "path": str(path),
        "size_bytes": stat.st_size,
        "modified_unix": int(stat.st_mtime),
        "line_count": count_lines(path) if should_count and stat.st_size < 50_000_000 else None,
    }

def load(path):
    p = Path(path)
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text())
    except Exception:
        return {}

flags = {
    "BINANCE_TESTNET": os.getenv("BINANCE_TESTNET", ""),
    "BINANCE_USE_TESTNET": os.getenv("BINANCE_USE_TESTNET", ""),
    "BINANCE_ENABLE_LIVE_TRADING": os.getenv("BINANCE_ENABLE_LIVE_TRADING", ""),
    "LIVE_TRADING_ALLOWED": os.getenv("LIVE_TRADING_ALLOWED", ""),
}

safe_mode = flags["BINANCE_ENABLE_LIVE_TRADING"] == "false" and flags["LIVE_TRADING_ALLOWED"] == "false"
inputs_present = {k: Path(v).exists() for k, v in INPUTS.items()}

files = []
for folder in SCAN_DIRS:
    root = Path(folder)
    if root.exists():
        for p in sorted(root.rglob("*")):
            if p.is_file() and p.suffix.lower() in [".jsonl", ".json", ".csv", ".txt"]:
                files.append(file_record(p))

symbol_coverage = {}
for symbol in TARGET_SYMBOLS:
    matched = [f for f in files if symbol.lower() in f["path"].lower()]
    symbol_coverage[symbol] = {
        "file_count": len(matched),
        "total_size_bytes": sum(f["size_bytes"] for f in matched),
        "total_lines_known": sum(f["line_count"] or 0 for f in matched),
        "files": matched[:20],
    }

required_dataset_checks = {
    "btc_data_present": symbol_coverage["BTCUSDT"]["file_count"] > 0,
    "eth_data_present": symbol_coverage["ETHUSDT"]["file_count"] > 0,
    "bnb_data_present": symbol_coverage["BNBUSDT"]["file_count"] > 0,
    "multi_symbol_data_present": sum(1 for s in TARGET_SYMBOLS if symbol_coverage[s]["file_count"] > 0) >= 2,
    "sufficient_for_phase17_backtest_expansion": False,
}

gaps = [k for k, v in required_dataset_checks.items() if v is not True]

report = {
    "phase": "phase_17_2_historical_data_coverage_audit",
    "generated_at_unix": int(time.time()),
    "scope": "historical_data_coverage_audit_only",
    "git_commit": git_commit(),
    "safety_flags": flags,
    "safe_mode_active": safe_mode,
    "inputs_present": inputs_present,
    "all_inputs_present": all(inputs_present.values()),
    "git_working_tree_clean": git_clean(),
    "target_symbols": TARGET_SYMBOLS,
    "scanned_directories": SCAN_DIRS,
    "discovered_file_count": len(files),
    "symbol_coverage": symbol_coverage,
    "required_dataset_checks": required_dataset_checks,
    "dataset_gaps": gaps,
    "approved_for_micro_live_execution": False,
    "approved_for_real_live_trading": False,
    "decision": "HISTORICAL_DATA_COVERAGE_AUDIT_COMPLETE_DATASET_EXPANSION_REQUIRED",
    "next_phase": "Phase 17.3 — Historical Backtest Dataset Builder",
    "safety_notes": [
        "This phase audits local historical data coverage only.",
        "This phase does not approve live trading.",
        "This phase does not submit Binance orders.",
        "More multi-symbol and multi-period historical data is required before strategy approval.",
    ],
}

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(report, indent=2))

print(f"Report written to: {OUT}")
print(f"safe_mode_active={safe_mode}")
print(f"all_inputs_present={report['all_inputs_present']}")
print(f"git_working_tree_clean={report['git_working_tree_clean']}")
print(f"discovered_file_count={len(files)}")
print(f"dataset_gaps={len(gaps)}")
print("approved_for_micro_live_execution=False")
print("approved_for_real_live_trading=False")
print(f"decision={report['decision']}")
