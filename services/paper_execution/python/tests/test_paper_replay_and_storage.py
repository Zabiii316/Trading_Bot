from __future__ import annotations

from pathlib import Path

from trading_paper_execution.models import PaperExecutionConfig
from trading_paper_execution.replay import load_jsonl_events, run_paper_replay
from trading_storage.table_map import row_for_event, table_for_event


def test_paper_replay_emits_order_and_fill() -> None:
    events = load_jsonl_events(Path("examples/paper/paper_replay.jsonl"))
    result = run_paper_replay(events, PaperExecutionConfig(slippage_bps=0.0, fee_bps=0.0))
    emitted = result["emitted_events"]
    assert any(event.event_type == "execution.order" for event in emitted)
    assert any(event.event_type == "execution.fill" for event in emitted)
    assert result["reconciliation"].is_healthy


def test_storage_mapping_for_execution_events() -> None:
    events = load_jsonl_events(Path("examples/paper/paper_replay.jsonl"))
    result = run_paper_replay(events, PaperExecutionConfig(slippage_bps=0.0, fee_bps=0.0))
    order = next(event for event in result["emitted_events"] if event.event_type == "execution.order")
    fill = next(event for event in result["emitted_events"] if event.event_type == "execution.fill")
    assert table_for_event(order) == "execution_orders"
    assert table_for_event(fill) == "execution_fills"
    assert row_for_event(order)["client_order_id"].startswith("PAPER-")
    assert row_for_event(fill)["liquidity_tag"] == "paper_taker"
