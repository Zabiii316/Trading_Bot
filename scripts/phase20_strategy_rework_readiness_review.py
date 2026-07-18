import json, os, subprocess, time
from pathlib import Path

OUT = Path("data/processed/phase20_strategy_rework_readiness_review.json")
RUNTIME_OUT = Path("runtime/phase20_strategy_rework_readiness_review_state.json")
PHASE20_DIR = Path("data/processed/phase20_strategy_rework")

PHASE19_CLOSEOUT = Path("data/processed/phase19_historical_data_expansion_safety_closeout.json")
PHASE19_RUNTIME = Path("runtime/phase19_historical_data_expansion_safety_closeout_state.json")
PHASE17_BACKTEST_REVIEW = Path("data/processed/phase17_backtest_results_review_quality_gate.json")
PHASE17_SWEEP_DESIGN = Path("data/processed/phase17_strategy_rework_parameter_sweep_design.json")
PHASE17_SWEEP_RESULTS = Path("data/processed/phase17_parameter_sweep_backtest_runner.json")
PHASE17_CANDIDATES = Path("data/processed/phase17_parameter_sweep_results_review_candidate_selection.json")
BTC_DATASET = Path("data/processed/backtest_datasets/btcusdt_phase17_backtest_dataset.jsonl")
ETH_DATASET = Path("data/processed/backtest_datasets/ethusdt_phase17_backtest_dataset.jsonl")

def run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True)

def git_clean():
    return run(["git", "status", "--short"]).stdout.strip() == ""

def git_head():
    r = run(["git", "rev-parse", "HEAD"])
    return r.stdout.strip() if r.returncode == 0 else None

def load_json(path):
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except Exception:
        return {}

def count_lines(path):
    if not path.exists():
        return 0
    try:
        with path.open("r") as f:
            return sum(1 for _ in f)
    except Exception:
        return 0

def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2))

flags = {
    "BINANCE_TESTNET": os.getenv("BINANCE_TESTNET", ""),
    "BINANCE_USE_TESTNET": os.getenv("BINANCE_USE_TESTNET", ""),
    "BINANCE_ENABLE_LIVE_TRADING": os.getenv("BINANCE_ENABLE_LIVE_TRADING", ""),
    "LIVE_TRADING_ALLOWED": os.getenv("LIVE_TRADING_ALLOWED", ""),
}

safe_mode = flags["BINANCE_ENABLE_LIVE_TRADING"] == "false" and flags["LIVE_TRADING_ALLOWED"] == "false"
current_git_head = git_head()
git_clean_before_outputs = git_clean()

phase19 = load_json(PHASE19_CLOSEOUT)
phase19_runtime = load_json(PHASE19_RUNTIME)
backtest_review = load_json(PHASE17_BACKTEST_REVIEW)
sweep_design = load_json(PHASE17_SWEEP_DESIGN)
sweep_results = load_json(PHASE17_SWEEP_RESULTS)
candidate_review = load_json(PHASE17_CANDIDATES)

selected_option = phase19.get("selected_option") or phase19_runtime.get("selected_option")
selected_phase19_path = phase19.get("selected_phase19_path") or phase19_runtime.get("selected_phase19_path")
selected_next_action = phase19.get("selected_next_action") or phase19_runtime.get("selected_next_action")

phase19_safety_closeout_passed = (
    phase19.get("phase19_safety_closeout_passed") is True
    or phase19_runtime.get("phase19_safety_closeout_passed") is True
)

btc_rows = count_lines(BTC_DATASET)
eth_rows = count_lines(ETH_DATASET)

manual_collection_approval_granted = False
collection_start_allowed = False
download_allowed = False
network_download_allowed = False
execution_allowed = False
paper_shadow_started = False
approved_for_paper_shadow_start = False
exchange_order_submission = False
approved_for_micro_live_execution = False
approved_for_real_live_trading = False

readiness_checks = {
    "safe_mode_active": safe_mode,
    "phase19_closeout_present": PHASE19_CLOSEOUT.exists(),
    "phase19_runtime_present": PHASE19_RUNTIME.exists(),
    "phase19_safety_closeout_passed": phase19_safety_closeout_passed,
    "selected_option_is_remain_on_hold": selected_option == "remain_on_hold",
    "selected_next_action_is_remain_on_hold": selected_next_action == "remain_on_hold",
    "phase17_backtest_review_present": PHASE17_BACKTEST_REVIEW.exists(),
    "phase17_sweep_design_present": PHASE17_SWEEP_DESIGN.exists(),
    "phase17_sweep_results_present": PHASE17_SWEEP_RESULTS.exists(),
    "phase17_candidate_review_present": PHASE17_CANDIDATES.exists(),
    "btc_dataset_present": BTC_DATASET.exists(),
    "eth_dataset_present": ETH_DATASET.exists(),
    "btc_dataset_has_rows": btc_rows > 0,
    "eth_dataset_has_rows": eth_rows > 0,
    "manual_collection_approval_not_granted": manual_collection_approval_granted is False,
    "collection_start_blocked": collection_start_allowed is False,
    "download_blocked": download_allowed is False,
    "network_download_blocked": network_download_allowed is False,
    "execution_blocked": execution_allowed is False,
    "paper_shadow_not_started": paper_shadow_started is False,
    "paper_shadow_start_not_approved": approved_for_paper_shadow_start is False,
    "exchange_order_submission_disabled": exchange_order_submission is False,
    "micro_live_not_approved": approved_for_micro_live_execution is False,
    "real_live_not_approved": approved_for_real_live_trading is False,
}

blockers = [k for k, v in readiness_checks.items() if v is not True]

research_only_strategy_rework_ready = all(readiness_checks.values())
approved_for_execution = False
approved_for_paper_shadow = False
approved_for_live = False

if research_only_strategy_rework_ready:
    decision = "PHASE_20_STRATEGY_REWORK_READINESS_REVIEW_COMPLETE_RESEARCH_ONLY_NOT_APPROVED_FOR_EXECUTION"
    next_phase = "Phase 20.2 — Strategy Failure Review"
else:
    decision = "PHASE_20_STRATEGY_REWORK_READINESS_REVIEW_BLOCKED_REVIEW_REQUIRED"
    next_phase = "Phase 20.2 — Strategy Rework Readiness Fix"

PHASE20_DIR.mkdir(parents=True, exist_ok=True)

record = {
    "phase": "phase_20_1_strategy_rework_readiness_review_record",
    "created_at_unix": int(time.time()),
    "git_head": current_git_head,
    "system_state": "HOLD",
    "selected_option": selected_option,
    "selected_phase19_path": selected_phase19_path,
    "selected_next_action": selected_next_action,
    "research_only_strategy_rework_ready": research_only_strategy_rework_ready,
    "approved_for_execution": approved_for_execution,
    "approved_for_paper_shadow": approved_for_paper_shadow,
    "approved_for_live": approved_for_live,
    "btc_dataset_rows": btc_rows,
    "eth_dataset_rows": eth_rows,
    "readiness_checks": readiness_checks,
    "blockers": blockers,
    "allowed_actions": [
        "strategy_failure_review",
        "research_only_strategy_rework",
        "offline_backtest_design_only",
        "documentation_only"
    ],
    "blocked_actions": [
        "historical_data_download",
        "historical_data_import",
        "paper_shadow_start",
        "micro_live_execution",
        "real_live_trading",
        "exchange_order_submission",
        "real_capital_usage",
        "production_api_key_usage"
    ],
    "manual_collection_approval_granted": False,
    "collection_start_allowed": False,
    "download_allowed": False,
    "network_download_allowed": False,
    "execution_allowed": False,
    "paper_shadow_started": False,
    "approved_for_paper_shadow_start": False,
    "exchange_order_submission": False,
    "approved_for_micro_live_execution": False,
    "approved_for_real_live_trading": False,
    "decision": decision,
    "next_phase": next_phase
}

record_file = PHASE20_DIR / "strategy_rework_readiness_review.json"

write_json(record_file, record)
write_json(RUNTIME_OUT, record)

report = {
    "phase": "phase_20_1_strategy_rework_readiness_review",
    "generated_at_unix": int(time.time()),
    "scope": "research_only_readiness_review_no_execution",
    "git_head": current_git_head,
    "safety_flags": flags,
    "safe_mode_active": safe_mode,
    "git_working_tree_clean": git_clean_before_outputs,
    "selected_option": selected_option,
    "selected_phase19_path": selected_phase19_path,
    "selected_next_action": selected_next_action,
    "research_only_strategy_rework_ready": research_only_strategy_rework_ready,
    "approved_for_execution": False,
    "approved_for_paper_shadow": False,
    "approved_for_live": False,
    "btc_dataset_rows": btc_rows,
    "eth_dataset_rows": eth_rows,
    "readiness_checks": readiness_checks,
    "blockers": blockers,
    "record_file": str(record_file),
    "runtime_record_file": str(RUNTIME_OUT),
    "manual_collection_approval_granted": False,
    "collection_start_allowed": False,
    "download_allowed": False,
    "network_download_allowed": False,
    "execution_allowed": False,
    "paper_shadow_started": False,
    "approved_for_paper_shadow_start": False,
    "exchange_order_submission": False,
    "approved_for_micro_live_execution": False,
    "approved_for_real_live_trading": False,
    "decision": decision,
    "next_phase": next_phase,
    "safety_notes": [
        "This phase starts Phase 20 as research-only strategy rework.",
        "No historical data download is approved.",
        "No historical data import is approved.",
        "No paper shadow execution is approved.",
        "No micro-live execution is approved.",
        "No real live trading is approved.",
        "No Binance exchange order submission is approved."
    ]
}

write_json(OUT, report)

print(f"Report written to: {OUT}")
print(f"Runtime record written to: {RUNTIME_OUT}")
print(f"Record file written to: {record_file}")
print(f"safe_mode_active={safe_mode}")
print(f"selected_option={selected_option}")
print(f"selected_phase19_path={selected_phase19_path}")
print(f"selected_next_action={selected_next_action}")
print(f"research_only_strategy_rework_ready={research_only_strategy_rework_ready}")
print("approved_for_execution=False")
print("approved_for_paper_shadow=False")
print("approved_for_live=False")
print(f"btc_dataset_rows={btc_rows}")
print(f"eth_dataset_rows={eth_rows}")
print("manual_collection_approval_granted=False")
print("collection_start_allowed=False")
print("download_allowed=False")
print("network_download_allowed=False")
print("execution_allowed=False")
print("paper_shadow_started=False")
print("approved_for_paper_shadow_start=False")
print("exchange_order_submission=False")
print("approved_for_micro_live_execution=False")
print("approved_for_real_live_trading=False")
print(f"decision={decision}")
