from pathlib import Path

from trading_features.replay import replay_file


def test_replay_file_emits_features(tmp_path: Path) -> None:
    source = Path("examples/features/order_flow_replay.jsonl")
    target = tmp_path / "features.jsonl"
    count = replay_file(source, target)
    assert count >= 2
    text = target.read_text()
    assert "features.order_flow" in text
