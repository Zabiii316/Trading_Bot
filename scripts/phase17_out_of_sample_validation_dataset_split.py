import json, os, subprocess, time
from pathlib import Path

OUT = Path("data/processed/phase17_out_of_sample_validation_dataset_split.json")
CANDIDATE_INPUT = Path("data/processed/phase17_parameter_sweep_results_review_candidate_selection.json")
DATASET_DIR = Path("data/processed/backtest_datasets")
OOS_DIR = Path("data/processed/oos_datasets")

TRAIN_RATIO = 0.70
VALIDATION_RATIO = 0.15
TEST_RATIO = 0.15

def run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True)

def git_clean():
    return run(["git", "status", "--short"]).stdout.strip() == ""

def load_json(path):
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except Exception:
        return {}

def count_lines(path):
    count = 0
    with path.open("r", errors="ignore") as f:
        for line in f:
            if line.strip():
                count += 1
    return count

def split_dataset(path):
    symbol = path.name.split("_phase17_")[0].upper()
    total = count_lines(path)

    train_count = int(total * TRAIN_RATIO)
    validation_count = int(total * VALIDATION_RATIO)
    test_count = total - train_count - validation_count

    train_path = OOS_DIR / f"{symbol.lower()}_train_oos_phase17.jsonl"
    validation_path = OOS_DIR / f"{symbol.lower()}_validation_oos_phase17.jsonl"
    test_path = OOS_DIR / f"{symbol.lower()}_test_oos_phase17.jsonl"

    with path.open("r", errors="ignore") as src, train_path.open("w") as train, validation_path.open("w") as validation, test_path.open("w") as test:
        idx = 0
        for line in src:
            if not line.strip():
                continue
            if idx < train_count:
                train.write(line)
            elif idx < train_count + validation_count:
                validation.write(line)
            else:
                test.write(line)
            idx += 1

    return {
        "symbol": symbol,
        "source_dataset": str(path),
        "total_records": total,
        "train_records": train_count,
        "validation_records": validation_count,
        "test_records": test_count,
        "train_path": str(train_path),
        "validation_path": str(validation_path),
        "test_path": str(test_path),
        "split_ready": train_count > 0 and validation_count > 0 and test_count > 0
    }

flags = {
    "BINANCE_TESTNET": os.getenv("BINANCE_TESTNET", ""),
    "BINANCE_USE_TESTNET": os.getenv("BINANCE_USE_TESTNET", ""),
    "BINANCE_ENABLE_LIVE_TRADING": os.getenv("BINANCE_ENABLE_LIVE_TRADING", ""),
    "LIVE_TRADING_ALLOWED": os.getenv("LIVE_TRADING_ALLOWED", "")
}

safe_mode = flags["BINANCE_ENABLE_LIVE_TRADING"] == "false" and flags["LIVE_TRADING_ALLOWED"] == "false"

candidate_report = load_json(CANDIDATE_INPUT)
selected_candidates = candidate_report.get("selected_candidates", [])

OOS_DIR.mkdir(parents=True, exist_ok=True)

datasets = sorted(DATASET_DIR.glob("*_phase17_backtest_dataset.jsonl"))

splits = {}
for dataset in datasets:
    result = split_dataset(dataset)
    splits[result["symbol"]] = result

split_ready_symbols = [s for s, r in splits.items() if r["split_ready"]]
split_not_ready_symbols = [s for s, r in splits.items() if not r["split_ready"]]

if selected_candidates and split_ready_symbols:
    decision = "OOS_DATASET_SPLIT_COMPLETE_CANDIDATE_VALIDATION_REQUIRED_NOT_APPROVED_FOR_EXECUTION"
    next_phase = "Phase 17.10 — Out-of-Sample Candidate Validation Runner"
else:
    decision = "OOS_DATASET_SPLIT_COMPLETE_NO_CANDIDATES_OR_INSUFFICIENT_DATA_NOT_APPROVED_FOR_EXECUTION"
    next_phase = "Phase 17.10 — Out-of-Sample Candidate Validation Runner or Strategy Redesign"

report = {
    "phase": "phase_17_9_out_of_sample_validation_dataset_split",
    "generated_at_unix": int(time.time()),
    "scope": "out_of_sample_validation_dataset_split_only",
    "safety_flags": flags,
    "safe_mode_active": safe_mode,
    "git_working_tree_clean": git_clean(),
    "candidate_input_present": CANDIDATE_INPUT.exists(),
    "selected_candidate_count": len(selected_candidates),
    "dataset_count": len(datasets),
    "split_ratios": {
        "train": TRAIN_RATIO,
        "validation": VALIDATION_RATIO,
        "test": TEST_RATIO
    },
    "splits": splits,
    "split_ready_symbols": split_ready_symbols,
    "split_not_ready_symbols": split_not_ready_symbols,
    "approved_for_micro_live_execution": False,
    "approved_for_real_live_trading": False,
    "decision": decision,
    "next_phase": next_phase
}

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(report, indent=2))

print(f"Report written to: {OUT}")
print(f"safe_mode_active={safe_mode}")
print(f"selected_candidate_count={len(selected_candidates)}")
print(f"dataset_count={len(datasets)}")
print(f"split_ready_symbols={','.join(split_ready_symbols) if split_ready_symbols else 'none'}")
print(f"split_not_ready_symbols={','.join(split_not_ready_symbols) if split_not_ready_symbols else 'none'}")
print("approved_for_micro_live_execution=False")
print("approved_for_real_live_trading=False")
print(f"decision={decision}")
