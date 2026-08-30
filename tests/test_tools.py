from pathlib import Path
import base64

from mini_agent.protocol import VerificationRecord
from mini_agent.tools import ToolContext, build_default_registry
from mini_agent.protocol import Action


def make_context(workspace: Path) -> ToolContext:
    return ToolContext(workspace=workspace, modified_files=[], inspected_paths=[], verification_records=[])


def test_file_tools_read_and_replace(tmp_path: Path) -> None:
    target = tmp_path / "sample.py"
    target.write_text("def add(a, b):\n    return a - b\n", encoding="utf-8")
    registry = build_default_registry(make_context(tmp_path))

    read = registry.execute(Action("read", "read_file", {"path": "sample.py", "start": 1, "end": 2}))
    assert read.ok
    assert "1: def add" in read.content

    replaced = registry.execute(
        Action("fix", "replace_in_file", {"path": "sample.py", "old": "return a - b", "new": "return a + b"})
    )
    assert replaced.ok
    assert "return a + b" in target.read_text(encoding="utf-8")


def test_replace_requires_unique_match(tmp_path: Path) -> None:
    target = tmp_path / "sample.txt"
    target.write_text("x\nx\n", encoding="utf-8")
    registry = build_default_registry(make_context(tmp_path))

    result = registry.execute(Action("replace", "replace_in_file", {"path": "sample.txt", "old": "x", "new": "y"}))

    assert not result.ok
    assert result.error_type == "ReplacementNotUnique"


def test_write_file_accepts_content_lines(tmp_path: Path) -> None:
    registry = build_default_registry(make_context(tmp_path))

    result = registry.execute(
        Action("write", "write_file", {"path": "multi.py", "content_lines": ["def value():", "    return 42"]})
    )

    assert result.ok
    assert result.data["line_count"] == 2
    assert result.data["next_write_tool"] == "append_file"
    assert (tmp_path / "multi.py").read_text(encoding="utf-8") == "def value():\n    return 42\n"


def test_write_file_accepts_content_base64(tmp_path: Path) -> None:
    registry = build_default_registry(make_context(tmp_path))
    content = '"""quoted docstring"""\nvalue = "hello"\n'
    encoded = base64.b64encode(content.encode("utf-8")).decode("ascii")

    result = registry.execute(Action("write", "write_file", {"path": "quoted.py", "content_base64": encoded}))

    assert result.ok
    assert (tmp_path / "quoted.py").read_text(encoding="utf-8") == content


def test_write_file_requires_one_content_form(tmp_path: Path) -> None:
    registry = build_default_registry(make_context(tmp_path))

    result = registry.execute(
        Action("write", "write_file", {"path": "bad.py", "content": "a", "content_lines": ["b"]})
    )

    assert not result.ok
    assert result.error_type == "ValueError"


def test_write_file_rejects_more_than_100_lines(tmp_path: Path) -> None:
    registry = build_default_registry(make_context(tmp_path))
    lines = [f"line {index}" for index in range(101)]

    result = registry.execute(Action("write", "write_file", {"path": "large.py", "content_lines": lines}))

    assert not result.ok
    assert result.error_type == "WriteChunkTooLarge"
    assert result.data["max_lines"] == 100
    assert not (tmp_path / "large.py").exists()


def test_write_file_accepts_100_lines(tmp_path: Path) -> None:
    registry = build_default_registry(make_context(tmp_path))
    lines = [f"line {index}" for index in range(100)]

    result = registry.execute(Action("write", "write_file", {"path": "chunk.py", "content_lines": lines}))

    assert result.ok
    assert result.data["line_count"] == 100
    assert len((tmp_path / "chunk.py").read_text(encoding="utf-8").splitlines()) == 100


def test_append_file_adds_content_without_overwriting(tmp_path: Path) -> None:
    registry = build_default_registry(make_context(tmp_path))
    target = tmp_path / "story.txt"
    target.write_text("first\n", encoding="utf-8")

    result = registry.execute(Action("append", "append_file", {"path": "story.txt", "content_lines": ["second"]}))

    assert result.ok
    assert result.data["line_count"] == 1
    assert result.data["next_write_tool"] == "append_file"
    assert target.read_text(encoding="utf-8") == "first\nsecond\n"


def test_append_file_rejects_more_than_100_lines(tmp_path: Path) -> None:
    registry = build_default_registry(make_context(tmp_path))
    target = tmp_path / "story.txt"
    target.write_text("first\n", encoding="utf-8")
    lines = [f"line {index}" for index in range(101)]

    result = registry.execute(Action("append", "append_file", {"path": "story.txt", "content_lines": lines}))

    assert not result.ok
    assert result.error_type == "WriteChunkTooLarge"
    assert target.read_text(encoding="utf-8") == "first\n"


def test_plan_mode_does_not_expose_append_file(tmp_path: Path) -> None:
    registry = build_default_registry(make_context(tmp_path), mode="plan")

    result = registry.execute(Action("append", "append_file", {"path": "x.txt", "content": "x"}))

    assert not result.ok
    assert result.error_type == "UnknownTool"


def test_search_ignores_trajectories(tmp_path: Path) -> None:
    (tmp_path / "code.py").write_text("snake = True\n", encoding="utf-8")
    trajectory_dir = tmp_path / "trajectories"
    trajectory_dir.mkdir()
    (trajectory_dir / "run.jsonl").write_text("snake hidden in logs\n", encoding="utf-8")
    registry = build_default_registry(make_context(tmp_path))

    result = registry.execute(Action("search", "search", {"pattern": "snake", "path": "."}))

    assert result.ok
    assert "code.py" in result.content
    assert "trajectories" not in result.content


def test_tools_record_inspected_paths(tmp_path: Path) -> None:
    (tmp_path / "sample.py").write_text("value = 1\n", encoding="utf-8")
    context = make_context(tmp_path)
    registry = build_default_registry(context)

    registry.execute(Action("list", "list_dir", {"path": "."}))
    registry.execute(Action("read", "read_file", {"path": "sample.py"}))
    registry.execute(Action("search", "search", {"pattern": "value", "path": "."}))

    assert "." in context.inspected_paths
    assert "sample.py" in context.inspected_paths


def test_run_shell_records_verification(tmp_path: Path) -> None:
    context = make_context(tmp_path)
    registry = build_default_registry(context)

    result = registry.execute(Action("verify", "run_shell", {"command": "python --version"}))

    assert result.ok
    assert context.verification_records == []

    test_result = registry.execute(Action("verify", "run_shell", {"command": "python -c \"print('test ok')\""}))

    assert test_result.ok
    assert len(context.verification_records) == 1
    assert isinstance(context.verification_records[0], VerificationRecord)


def test_run_shell_rejects_file_reading_commands(tmp_path: Path) -> None:
    (tmp_path / "sample.py").write_text("value = 1\n", encoding="utf-8")
    context = make_context(tmp_path)
    registry = build_default_registry(context)

    result = registry.execute(Action("read through shell", "run_shell", {"command": "Get-Content sample.py"}))

    assert not result.ok
    assert result.error_type == "UseReadFile"
    assert context.verification_records == []
