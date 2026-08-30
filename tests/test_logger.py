import json
from pathlib import Path

from mini_agent.logger import append_turn_summary


def test_append_turn_summary_writes_event(tmp_path: Path) -> None:
    path = tmp_path / "run.jsonl"
    path.write_text("", encoding="utf-8")

    append_turn_summary(path, "我完成了这轮任务。", "plans/plan.md")

    event = json.loads(path.read_text(encoding="utf-8"))
    assert event["type"] == "turn_summary"
    assert event["turn_summary"] == "我完成了这轮任务。"
    assert event["output_path"] == "plans/plan.md"
