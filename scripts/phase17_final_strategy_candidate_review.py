import json, os, subprocess, time
from pathlib import Path

OUT = Path("data/processed/phase17_final_strategy_candidate_review.json")
CANDIDATE_OUT_DIR = Path("data/processed/final_strategy_candidates")
WALK_FORWARD_INPUT = Path("data/processed/phase17_walk_forward_validation_runner.json")
OOS_REVIEW_INPUT = Path("data/processed/phase17_oos_results_review_overfitting_check.json")
SWEEP_REVIEW_INPUT = Path("data/processed/phase17_parameter_sweep_results_review_candidate_selection.json")

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

def safe_num(v, default=0.0):
    try:
        if v is None:
            return default
        return float(v)
    except Exception:
        return default

flags = {
    "BINANCE_TESTNET": os.getenv("BINANCE_TESTNET", ""),
    "BINANCE_USE_TESTNET": os.getenv("BINANCE_USE_TESTNET", ""),
    "BINANCE_ENABLE_LIVE_TRADING": os.getenv("BINANCE_ENABLE_LIVE_TRADING", ""),
    "LIVE_TRADING_ALLOWED": os.getenv("LIVE_TRADING_ALLOWED", ""),
}

safe_mode = flags["BINANCE_ENABLE_LIVE_TRADING"] == "false" and flags["LIVE_TRADING_ALLOWED"] == "false"

walk_forward = load_json(WALK_FORWARD_INPUT)
oos_review = load_json(OOS_REVIEW_INPUT)
sweep_review = load_json(SWEEP_REVIEW_INPUT)

wf_passed = walk_forward.get("walk_forward_passed_candidates", [])
wf_failed = walk_forward.get("walk_forward_failed_candidates", [])

final_candidates = []
rejected_candidates = []

CANDIDATE_OUT_DIR.mkdir(parents=True, exist_ok=True)

for idx, candidate in enumerate(wf_passed, start=1):
    symbol = candidate.get("symbol", "UNKNOWN")
    params = candidate.get("candidate_parameters", {})

    avg_net = safe_num(candidate.get("average_net_return_bps"))
    worst_dd = safe_num(candidate.get("worst_drawdown_pct"), 999)
    passing_ratio = safe_num(candidate.get("passing_window_ratio"))

    risk_review_required = True
    stress_test_required = True
    paper_shadow_required = True
    manual_approval_required = True

    review_score = round(avg_net - (worst_dd * 10) + (passing_ratio * 100), 4)

    final_candidate = {
        "final_candidate_id": f"{symbol}_final_strategy_candidate_{idx}",
        "symbol": symbol,
        "candidate_parameters": params,
        "walk_forward_summary": {
            "passing_window_ratio": passing_ratio,
            "average_net_return_bps": avg_net,
            "worst_drawdown_pct": worst_dd,
            "passing_window_count": candidate.get("passing_window_count"),
            "window_count": candidate.get("window_count"),
        },
        "review_score": review_score,
        "risk_review_required": risk_review_required,
        "stress_test_required": stress_test_required,
        "paper_shadow_required": paper_shadow_required,
        "manual_approval_required": manual_approval_required,
        "approved_for_micro_live_execution": False,
        "approved_for_real_live_trading": False,
        "candidate_status": "FINAL_CANDIDATE_SELECTED_FOR_RISK_AND_STRESS_REVIEW_NOT_EXECUTION",
        "blockers_before_execution": [
            "risk_sizing_review_required",
            "stress_test_required",
            "paper_shadow_required",
            "manual_approval_required",
            "production_key_permission_review_required",
            "live_trading_flags_must_remain_disabled"
        ]
    }

    candidate_path = CANDIDATE_OUT_DIR / f"{final_candidate['final_candidate_id'].lower()}.json"
    candidate_path.write_text(json.dumps(final_candidate, indent=2))
    final_candidate["candidate_file"] = str(candidate_path)

    final_candidates.append(final_candidate)

for candidate in wf_failed:
    rejected_candidates.append({
        "candidate_id": candidate.get("candidate_id"),
        "symbol": candidate.get("symbol"),
        "candidate_parameters": candidate.get("candidate_parameters"),
        "reason": "walk_forward_validation_failed",
        "approved_for_execution": False,
    })

final_candidates = sorted(final_candidates, key=lambda x: x.get("review_score", -999999), reverse=True)

if final_candidates:
    decision = "FINAL_STRATEGY_CANDIDATE_REVIEW_COMPLETE_CANDIDATES_SELECTED_RISK_REVIEW_REQUIRED_NOT_APPROVED_FOR_EXECUTION"
    next_phase = "Phase 17.14 — Candidate Risk Sizing and Stress Test Plan"
    blockers = [
        "risk_sizing_review_required",
        "stress_test_required",
        "paper_shadow_required",
        "manual_approval_required",
        "live_trading_flags_disabled",
    ]
else:
    decision = "FINAL_STRATEGY_CANDIDATE_REVIEW_COMPLETE_NO_CANDIDATES_STRATEGY_REWORK_REQUIRED_NOT_APPROVED_FOR_EXECUTION"
    next_phase = "Phase 17.14 — Strategy Redesign or Candidate Risk Sizing if Manually Approved"
    blockers = [
        "no_walk_forward_passed_candidates",
        "strategy_rework_required",
        "live_trading_flags_disabled",
    ]

report = {
    "phase": "phase_17_13_final_strategy_candidate_review",
    "generated_at_unix": int(time.time()),
    "scope": "final_strategy_candidate_review_only",
    "safety_flags": flags,
    "safe_mode_active": safe_mode,
    "git_working_tree_clean": git_clean(),
    "inputs_present": {
        "walk_forward_input": WALK_FORWARD_INPUT.exists(),
        "oos_review_input": OOS_REVIEW_INPUT.exists(),
        "sweep_review_input": SWEEP_REVIEW_INPUT.exists(),
    },
    "walk_forward_passed_count": len(wf_passed),
    "walk_forward_failed_count": len(wf_failed),
    "final_candidate_count": len(final_candidates),
    "final_candidates": final_candidates,
    "rejected_candidates": rejected_candidates,
    "execution_blockers": blockers,
    "approved_for_micro_live_execution": False,
    "approved_for_real_live_trading": False,
    "decision": decision,
    "next_phase": next_phase,
    "safety_notes": [
        "This phase performs final strategy candidate review only.",
        "This phase does not approve live trading.",
        "This phase does not approve micro-live execution.",
        "This phase does not submit Binance orders.",
        "Final candidates require risk sizing, stress testing, paper shadow, and manual approval before any future execution review."
    ],
}

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(report, indent=2))

print(f"Report written to: {OUT}")
print(f"safe_mode_active={safe_mode}")
print(f"walk_forward_passed_count={len(wf_passed)}")
print(f"walk_forward_failed_count={len(wf_failed)}")
print(f"final_candidate_count={len(final_candidates)}")
print("approved_for_micro_live_execution=False")
print("approved_for_real_live_trading=False")
print(f"decision={decision}")
