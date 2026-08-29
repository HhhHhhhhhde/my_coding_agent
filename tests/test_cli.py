from pathlib import Path

from mini_agent.cli import is_exit_command, save_plan_result, wrap_box_line, wrap_visual


def test_wrap_visual_accounts_for_wide_characters() -> None:
    lines = wrap_visual("Task      : 请你plan一个定时闹钟的核心模块架构", 24)

    assert len(lines) > 1
    assert lines[0] == "Task      : 请你plan一个"


def test_wrap_box_line_aligns_field_continuation() -> None:
    lines = wrap_box_line("Task      : 请你plan一个定时闹钟的核心模块架构", 24)

    assert len(lines) > 1
    assert lines[0].startswith("Task      : ")
    assert lines[1].startswith(" " * len("Task      : "))


def test_save_plan_result_writes_markdown_to_default_style_dir(tmp_path: Path) -> None:
    path = save_plan_result("1. 定时模块\n2. 提醒模块", tmp_path, Path("plans"), "设计闹钟")

    assert path.parent == tmp_path / "plans"
    assert path.name.startswith("plan-")
    assert path.suffix == ".md"
    content = path.read_text(encoding="utf-8")
    assert "# Agent Plan" in content
    assert "设计闹钟" in content
    assert "定时模块" in content


def test_exit_commands_are_recognized_case_insensitively() -> None:
    assert is_exit_command("Q")
    assert is_exit_command(" quit ")
    assert not is_exit_command("build")
