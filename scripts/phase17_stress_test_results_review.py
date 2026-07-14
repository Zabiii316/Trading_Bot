import json, os, subprocess, time
from pathlib import Path

OUT = Path("data/processed/phase17_stress_test_results_review.json")
STRESS_INPUT = Path("data/processed/phase17_candidate_stress_test_runner.json")
REVIEW_DIR = Path("data/processed/stress_review_candidates")

MIN_PASSING_SCENARIO_RATIO = 0.60
MAX_WORST_DRAWDOWN_PCT = 35.0
BASE_CASE_REQUIRED = True
STRESS_CASE_REQUIRED = True

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

def num(v, default=0.0):
    try:
        if v is None:
            return default
        return float(v)
    except Exception:
        return default

def scenario_name(row):
    return row.get("scenario", {}).get("name", "unknown")

def scenario_passed(row):
    return row.get("result", {}).get("scenario_passed") is True

def scenario_net(row):
    return num(row.get("result", {}).get("net_return_bps"))

def scenario_dd(row):
    return num(row.get("result", {}).get("max_drawdown_pct"), 999)

def review_candidate(candidate):
    scenario_results = candidate.get("scenario_results", [])

    passed = [r for r in scenario_results if scenario_passed(r)]
    failed = [r for r in scenario_results if not scenario_passed(r)]

    names_passed = [scenario_name(r) for r in passed]
    names_failed = [scenario_name(r) for r in failed]

    scenario_count = len(scenario_results)
    passing_ratio = round(len(passed) / scenario_count, 4) if scenario_count else 0.0

    net_returns = [scenario_net(r) for r in scenario_results]
    drawdowns = [scenario_dd(r) for r in scenario_results]

    worst_drawdown = round(max(drawdowns), 4) if drawdowns else 999
    worst_net_return = round(min(net_returns), 4) if net_returns else 0.0
    average_net_return = round(sum(net_returns) / len(net_returns), 4) if net_returns else 0.0

    base_case_ok = True
    stress_case_ok = True

    if BASE_CASE_REQUIRED:
        base_case = [r for r in scenario_results if scenario_name(r) == "base_case"]
        base_case_ok = bool(base_case) and scenario_passed(base_case[0])

    if STRESS_CASE_REQUIRED:
        stress_case = [r for r in scenario_results if scenario_name(r) == "stress_case"]
        stress_case_ok = bool(stress_case) and scenario_passed(stress_case[0])

    checks = {
        "candidate_stress_test_passed": candidate.get("candidate_stress_test_passed") is True,
        "passing_scenario_ratio_ok": passing_ratio >= MIN_PASSING_SCENARIO_RATIO,
        "worst_drawdown_acceptable": worst_drawdown <= MAX_WORST_DRAWDOWN_PCT,
        "base_case_passed": base_case_ok,
        "stress_case_passed": stress_case_ok,
    }

    blockers = []
    if not checks["candidate_stress_test_passed"]:
        blockers.append("candidate_stress_test_failed")
    if not checks["passing_scenario_ratio_ok"]:
        blockers.append("passing_scenario_ratio_too_low")
    if not checks["worst_drawdown_acceptable"]:
        blockers.append("worst_drawdown_too_high")
    if not checks["base_case_passed"]:
        blockers.append("base_case_failed")
    if not checks["stress_case_passed"]:
        blockers.append("stress_case_failed")

    passed_review = all(checks.values())

    return {
        "candidate_id": candidate.get("candidate_id"),
        "symbol": candidate.get("symbol"),
        "candidate_parameters": candidate.get("candidate_parameters"),
        "scenario_count": scenario_count,
        "passed_scenario_count": len(passed),
        "failed_scenario_count": len(failed),
        "passing_scenario_ratio": passing_ratio,
        "passed_scenarios": names_passed,
        "failed_scenarios": names_failed,
        "average_net_return_bps": average_net_return,
        "worst_net_return_bps": worst_net_return,
        "worst_drawdown_pct": worst_drawdown,
        "checks": checks,
        "blockers": blockers,
        "stress_review_passed": passed_review,
        "approved_for_micro_live_execution": False,
        "approved_for_real_live_trading": False,
    }

flags = {
    "BINANCE_TESTNET": os.getenv("BINANCE_TESTNET", ""),
    "BINANCE_USE_TESTNET": os.getenv("BINANCE_USE_TESTNET", ""),
    "BINANCE_ENABLE_LIVE_TRADING": os.getenv("BINANCE_ENABLE_LIVE_TRADING", ""),
    "LIVE_TRADING_ALLOWED": os.getenv("LIVE_TRADING_ALLOWED", ""),
}

safe_mode = flags["BINANCE_ENABLE_LIVE_TRADING"] == "false" and flags["LIVE_TRADING_ALLOWED"] == "false"

stress_report = load_json(STRESS_INPUT)
passed_candidates = stress_report.get("passed_candidates", [])
failed_candidates = stress_report.get("failed_candidates", [])

all_candidates = passed_candidates + failed_candidates

REVIEW_DIR.mkdir(parents=True, exist_ok=True)

reviews = []
forward_candidates = []
rejected_candidates = []

for candidate in all_candidates:
    review = review_candidate(candidate)

    review_path = REVIEW_DIR / f"{str(review.get('candidate_id', 'unknown')).lower()}_stress_review.json"
    review_path.write_text(json.dumps(review, indent=2))
    review["review_path"] = str(review_path)

    reviews.append(review)

    if review["stress_review_passed"]:
        forward_candidates.append(review)
    else:
        rejected_candidates.append(review)

if forward_candidates:
    decision = "STRESS_TEST_REVIEW_COMPLETE_CANDIDATES_FORWARD_PAPER_SHADOW_REQUIRED_NOT_APPROVED_FOR_EXECUTION"
    next_phase = "Phase 17.17 — Paper Shadow Trading Plan"
elif reviews:
    decision = "STRESS_TEST_REVIEW_COMPLETE_NO_FORWARD_CANDIDATES_STRATEGY_REWORK_REQUIRED_NOT_APPROVED_FOR_EXECUTION"
    next_phase = "Phase 17.17 — Paper Shadow Trading Plan or Strategy Redesign"
else:
    decision = "STRESS_TEST_REVIEW_SKIPPED_NO_CANDIDATES_STRATEGY_REWORK_REQUIRED_NOT_APPROVED_FOR_EXECUTION"
    next_phase = "Phase 17.17 — Paper Shadow Trading Plan or Strategy Redesign"

report = {
    "phase": "phase_17_16_stress_test_results_review",
    "generated_at_unix": int(time.time()),
    "scope": "stress_test_results_review_only",
    "safety_flags": flags,
    "safe_mode_active": safe_mode,
    "git_working_tree_clean": git_clean(),
    "stress_input_present": STRESS_INPUT.exists(),
    "reviewed_candidate_count": len(reviews),
    "forward_candidate_count": len(forward_candidates),
    "rejected_candidate_count": len(rejected_candidates),
    "thresholds": {
        "min_passing_scenario_ratio": MIN_PASSING_SCENARIO_RATIO,
        "max_worst_drawdown_pct": MAX_WORST_DRAWDOWN_PCT,
        "base_case_required": BASE_CASE_REQUIRED,
        "stress_case_required": STRESS_CASE_REQUIRED
    },
    "forward_candidates": forward_candidates,
    "rejected_candidates": rejected_candidates,
    "approved_for_micro_live_execution": False,
    "approved_for_real_live_trading": False,
    "decision": decision,
    "next_phase": next_phase,
    "safety_notes": [
        "This phase reviews stress test results only.",
        "This phase does not approve live trading.",
        "This phase does not approve micro-live execution.",
        "This phase does not submit Binance orders.",
        "Forward candidates require paper shadow planning before any future execution gate."
    ],
}

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(report, indent=2))

print(f"Report written to: {OUT}")
print(f"safe_mode_active={safe_mode}")
print(f"reviewed_candidate_count={len(reviews)}")
print(f"forward_candidate_count={len(forward_candidates)}")
print(f"rejected_candidate_count={len(rejected_candidates)}")
print("approved_for_micro_live_execution=False")
print("approved_for_real_live_trading=False")
print(f"decision={decision}")
