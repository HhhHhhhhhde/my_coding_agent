from pathlib import Path

from mini_agent.cli import (
    BANNER_LINES,
    MODE_BOX_WIDTH,
    box_prefix,
    center_line,
    is_context_dependent_task,
    is_exit_command,
    is_session_command,
    print_box,
    print_banner,
    save_plan_result,
    summarize_step,
    wrap_box_line,
    wrap_visual,
)
from mini_agent.protocol import Action, Observation


def test_wrap_visual_accounts_for_wide_characters() -> None:
    lines = wrap_visual("Task      : 请你plan一个定时闹钟的核心模块架构", 24)

    assert len(lines) > 1
    assert lines[0] == "Task      : 请你plan一个"


def test_wrap_box_line_aligns_field_continuation() -> None:
    lines = wrap_box_line("Task      : 请你plan一个定时闹钟的核心模块架构", 24)

    assert len(lines) > 1
    assert lines[0].startswith("Task      : ")
    assert lines[1].startswith(" " * len("Task      : "))


def test_print_box_supports_wider_centered_lines(capsys) -> None:
    print_box(["Run Mode", "", center_line("● BUILD             ○ plan")], indent=2, width=MODE_BOX_WIDTH)

    output = capsys.readouterr().out

    assert "__center__" not in output
    assert "● BUILD" in output
    assert "○ plan" in output
    assert "  ╭" in output
    assert "─" * (MODE_BOX_WIDTH - 2) in output


def test_print_box_can_center_itself(monkeypatch, capsys) -> None:
    monkeypatch.setattr("mini_agent.cli.shutil.get_terminal_size", lambda fallback: os_size(120, 24))

    print_box(["Run Mode"], width=MODE_BOX_WIDTH, center=True)

    output = capsys.readouterr().out
    assert output.startswith(" " * 14 + "╭")


def test_banner_uses_large_ascii_letters(capsys) -> None:
    print_banner("build")

    output = capsys.readouterr().out
    assert BANNER_LINES[0].strip() in output
    assert "/ __|" in output
    assert "agent mode: build" in output


def test_box_prefix_falls_back_to_indent_when_terminal_is_narrow(monkeypatch) -> None:
    monkeypatch.setattr("mini_agent.cli.shutil.get_terminal_size", lambda fallback: os_size(70, 24))

    assert box_prefix(MODE_BOX_WIDTH, indent=2, center=True) == "  "


def os_size(columns: int, lines: int):
    return type("Size", (), {"columns": columns, "lines": lines})()


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


def test_session_commands_are_recognized_by_slash_prefix() -> None:
    assert is_session_command("/clear")
    assert is_session_command("/mode plan")
    assert is_session_command("/unknown")
    assert not is_session_command("clear")


def test_context_dependent_tasks_are_recognized() -> None:
    assert is_context_dependent_task("继续刚才的任务")
    assert is_context_dependent_task("continue previous task")
    assert is_context_dependent_task("把上一轮继续做完")
    assert not is_context_dependent_task("请阅读 examples/demo_calculator")


def test_step_summary_is_continuous_chinese_text() -> None:
    text = summarize_step(
        1,
        Action("read", "read_file", {"path": "calculator.py"}),
        Observation(True, "read_file", content="1: def add(a, b):"),
    )

    assert text.startswith("第 01 步：")
    assert "我读取了文件 calculator.py" in text
    assert text.endswith("。")


def test_step_summary_explains_rejected_shell_file_read() -> None:
    text = summarize_step(
        10,
        Action("read", "run_shell", {"command": "Get-Content sample.py"}),
        Observation(False, "run_shell", error_type="UseReadFile", message="Use read_file instead."),
    )

    assert "我拒绝了这条 shell 命令" in text
    assert "改用 read_file" in text


def test_step_summary_describes_append_file() -> None:
    text = summarize_step(
        3,
        Action("append", "append_file", {"path": "runner_game.py"}),
        Observation(True, "append_file", content="Appended"),
    )

    assert "我向文件 runner_game.py 追加了内容" in text
    assert "分块完成较大的文件" in text


def test_step_summary_describes_target_scope_violation() -> None:
    text = summarize_step(
        7,
        Action("inspect", "read_file", {"path": "pyproject.toml"}),
        Observation(
            False,
            "target_scope",
            error_type="TargetScopeViolation",
            data={"target_scope": "examples/demo_runner_game", "blocked_path": "pyproject.toml"},
        ),
    )

    assert "我拦截了对 pyproject.toml 的访问" in text
    assert "examples/demo_runner_game" in text
