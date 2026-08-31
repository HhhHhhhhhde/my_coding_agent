import json
import os
from pathlib import Path

from mini_agent.cli import main
from mini_agent.replay import latest_trajectory, render_trajectory_report, resolve_trajectory, verification_from_steps


def write_jsonl(path: Path, events: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(event, ensure_ascii=False) for event in events) + "\n", encoding="utf-8")


def sample_events() -> list[dict]:
    return [
        {
            "type": "start",
            "task": "Fix calculator",
            "workspace": "demo",
            "mode": "build",
            "max_steps": 5,
            "has_session_context": True,
        },
        {
            "type": "step",
            "step": 1,
            "parsed_action": {"tool": "read_file", "args": {"path": "calculator.py"}},
            "observation": {"ok": True, "tool": "read_file", "content": "1: def add(a, b):"},
        },
        {
            "type": "step",
            "step": 2,
            "parsed_action": {
                "tool": "replace_in_file",
                "args": {"path": "calculator.py", "old": "a - b", "new": "a + b"},
            },
            "observation": {"ok": True, "tool": "replace_in_file", "content": "Replaced text."},
        },
        {
            "type": "step",
            "step": 3,
            "parsed_action": {"tool": "run_shell", "args": {"command": "python -m pytest -q"}},
            "observation": {
                "ok": False,
                "tool": "run_shell",
                "error_type": "VerificationError",
                "message": "Verification command exited with 1.",
                "data": {"command": "python -m pytest -q", "exit_code": 1},
            },
        },
        {"type": "end", "termination_reason": "finished", "summary": "Fixed add.", "success": True},
        {"type": "turn_summary", "turn_summary": "修复了 calculator。", "output_path": None},
    ]


def test_render_trajectory_report_summarizes_run(tmp_path: Path) -> None:
    trajectory = tmp_path / "run.jsonl"
    write_jsonl(trajectory, sample_events())

    report = render_trajectory_report(trajectory)

    assert "# Agent Run Report" in report.markdown
    assert "Fix calculator" in report.markdown
    assert "2. `replace_in_file` `calculator.py` -> **ok**" in report.markdown
    assert "- `calculator.py`" in report.markdown
    assert "`python -m pytest -q` -> failed (1)" in report.markdown
    assert "step 3: `VerificationError`" in report.markdown
    assert "修复了 calculator" in report.markdown


def test_latest_trajectory_uses_newest_file(tmp_path: Path) -> None:
    old = tmp_path / "trajectories" / "run-1.jsonl"
    new = tmp_path / "trajectories" / "run-2.jsonl"
    write_jsonl(old, [{"type": "start"}])
    write_jsonl(new, [{"type": "start"}])
    os.utime(old, (1, 1))
    os.utime(new, (2, 2))

    assert latest_trajectory(tmp_path) == new
    assert resolve_trajectory(tmp_path, "latest") == new
    assert resolve_trajectory(tmp_path, "1") == new
    assert resolve_trajectory(tmp_path, "2") == old


def test_cli_replay_writes_report_file(tmp_path: Path) -> None:
    trajectory = tmp_path / "trajectories" / "run-1.jsonl"
    write_jsonl(trajectory, sample_events())

    exit_code = main(["--workspace", str(tmp_path), "--replay", "latest", "--replay-output", "reports/run.md"])

    assert exit_code == 0
    report = (tmp_path / "reports" / "run.md").read_text(encoding="utf-8")
    assert "Agent Run Report" in report
    assert "Fix calculator" in report


def test_replay_does_not_treat_dependency_install_as_verification() -> None:
    steps = [
        {
            "type": "step",
            "step": 1,
            "parsed_action": {"tool": "run_shell", "args": {"command": "python -m pip install pytest"}},
            "observation": {
                "ok": True,
                "tool": "run_shell",
                "data": {"command": "python -m pip install pytest", "exit_code": 0, "risk_level": "review"},
            },
        },
        {
            "type": "step",
            "step": 2,
            "parsed_action": {"tool": "run_shell", "args": {"command": "python -m pytest -q"}},
            "observation": {
                "ok": True,
                "tool": "run_shell",
                "data": {"command": "python -m pytest -q", "exit_code": 0, "risk_level": "safe"},
            },
        },
    ]

    verification = verification_from_steps(steps)

    assert verification == ["- `python -m pytest -q` -> passed (0)"]
