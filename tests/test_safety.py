from pathlib import Path

from mini_agent.protocol import Action, Observation
from mini_agent.safety import classify_shell_command, is_sensitive_path
from mini_agent.tools import ToolContext, build_default_registry


def make_context(workspace: Path) -> ToolContext:
    return ToolContext(workspace=workspace, modified_files=[], inspected_paths=[], verification_records=[])


def test_file_tools_block_paths_outside_workspace(tmp_path: Path) -> None:
    outside = tmp_path.parent / "outside.txt"
    outside.write_text("secret\n", encoding="utf-8")
    registry = build_default_registry(make_context(tmp_path))

    result = registry.execute(Action("read outside", "read_file", {"path": str(outside)}))

    assert not result.ok
    assert result.error_type == "PermissionError"
    assert "outside workspace" in result.message


def test_read_file_blocks_env_files(tmp_path: Path) -> None:
    (tmp_path / ".env").write_text("OPENAI_API_KEY=x\n", encoding="utf-8")
    registry = build_default_registry(make_context(tmp_path))

    result = registry.execute(Action("read env", "read_file", {"path": ".env"}))

    assert not result.ok
    assert result.error_type == "PermissionError"
    assert "sensitive" in result.message


def test_search_skips_sensitive_files(tmp_path: Path) -> None:
    (tmp_path / "app.py").write_text("token = None\n", encoding="utf-8")
    (tmp_path / ".env").write_text("token=secret\n", encoding="utf-8")
    registry = build_default_registry(make_context(tmp_path))

    result = registry.execute(Action("search", "search", {"pattern": "token", "path": "."}))

    assert result.ok
    assert "app.py" in result.content
    assert ".env" not in result.content


def test_write_file_requires_confirmation_before_overwrite(tmp_path: Path) -> None:
    target = tmp_path / "sample.py"
    target.write_text("old\n", encoding="utf-8")
    registry = build_default_registry(make_context(tmp_path))

    result = registry.execute(Action("overwrite", "write_file", {"path": "sample.py", "content": "new\n"}))

    assert not result.ok
    assert result.needs_confirmation
    assert result.error_type == "OverwriteFile"
    assert target.read_text(encoding="utf-8") == "old\n"


def test_write_file_overwrites_after_host_confirmation(tmp_path: Path) -> None:
    target = tmp_path / "sample.py"
    target.write_text("old\n", encoding="utf-8")
    confirmations: list[Observation] = []

    def confirm(observation: Observation) -> bool:
        confirmations.append(observation)
        return True

    context = ToolContext(
        workspace=tmp_path,
        modified_files=[],
        inspected_paths=[],
        verification_records=[],
        confirmation_callback=confirm,
    )
    registry = build_default_registry(context)

    result = registry.execute(Action("overwrite", "write_file", {"path": "sample.py", "content": "new\n"}))

    assert result.ok
    assert len(confirmations) == 1
    assert target.read_text(encoding="utf-8") == "new\n"


def test_blocked_shell_command_is_not_executed(tmp_path: Path) -> None:
    registry = build_default_registry(make_context(tmp_path))

    result = registry.execute(Action("delete", "run_shell", {"command": "Remove-Item build -Recurse -Force"}))

    assert not result.ok
    assert result.error_type == "PermissionError"
    assert result.data["risk_level"] == "blocked"


def test_review_shell_command_requires_confirmation(tmp_path: Path) -> None:
    registry = build_default_registry(make_context(tmp_path))

    result = registry.execute(Action("install", "run_shell", {"command": "pip install pytest"}))

    assert not result.ok
    assert result.needs_confirmation
    assert result.error_type == "ShellCommandRequiresConfirmation"


def test_safe_shell_command_runs_without_confirmation(tmp_path: Path) -> None:
    calls = 0

    def confirm(_observation: Observation) -> bool:
        nonlocal calls
        calls += 1
        return False

    context = ToolContext(
        workspace=tmp_path,
        modified_files=[],
        inspected_paths=[],
        verification_records=[],
        confirmation_callback=confirm,
    )
    registry = build_default_registry(context)

    result = registry.execute(Action("check", "run_shell", {"command": "python --version"}))

    assert result.ok
    assert calls == 0
    assert result.data["risk_level"] == "safe"


def test_shell_risk_classifier_levels() -> None:
    assert classify_shell_command("python -m pytest -q").level == "safe"
    assert classify_shell_command("npm install").level == "review"
    assert classify_shell_command("git reset --hard HEAD").level == "blocked"
    assert classify_shell_command("cat .env").level == "blocked"


def test_sensitive_path_detection() -> None:
    assert is_sensitive_path(Path(".env"))
    assert is_sensitive_path(Path("config") / "api_token.txt")
    assert not is_sensitive_path(Path("src") / "config.py")
