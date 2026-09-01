import json
from pathlib import Path

from mini_agent.cli import (
    BANNER_LINES,
    MODE_BOX_WIDTH,
    box_prefix,
    center_line,
    format_run_list,
    handle_session_command,
    is_context_dependent_task,
    is_exit_command,
    is_session_command,
    print_replay_command,
    print_box,
    print_banner,
    print_header,
    print_thinking,
    read_interactive_args,
    save_plan_result,
    split_box_line,
    summarize_step,
    wrap_box_line,
    wrap_visual,
)
from mini_agent.protocol import Action, Observation
from mini_agent.session import SessionState
from mini_agent.skills import SkillSession


def write_cli_jsonl(path: Path) -> None:
    events = [
        {
            "type": "start",
            "task": "Fix calculator",
            "workspace": "demo",
            "mode": "build",
            "max_steps": 5,
            "has_session_context": False,
        },
        {
            "type": "step",
            "step": 1,
            "parsed_action": {"tool": "read_file", "args": {"path": "calculator.py"}},
            "observation": {"ok": True, "tool": "read_file", "content": "1: def add(a, b):"},
        },
        {"type": "end", "termination_reason": "finished", "summary": "done", "success": True},
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(event) for event in events) + "\n", encoding="utf-8")


def test_wrap_visual_accounts_for_wide_characters() -> None:
    lines = wrap_visual("Task      : 请你plan一个定时闹钟的核心模块架构", 24)

    assert len(lines) > 1
    assert lines[0] == "Task      : 请你plan一个"


def test_wrap_box_line_aligns_field_continuation() -> None:
    lines = wrap_box_line("Task      : 请你plan一个定时闹钟的核心模块架构", 24)

    assert len(lines) > 1
    assert lines[0].startswith("Task      : ")
    assert lines[1].startswith(" " * len("Task      : "))


def test_wrap_box_line_keeps_bullets_left_aligned() -> None:
    lines = wrap_box_line("- compact-planner: D:/codes/ai_agent/coding_agent/skills/compact-planner/SKILL.md", 36)

    assert lines[0].startswith("- compact-planner")
    assert lines[1]
    assert not lines[1].startswith(" " * len("- compact-planner: "))


def test_split_box_line_preserves_embedded_newlines() -> None:
    assert split_box_line("已启用 skill：\n- python-testing: path") == ["已启用 skill：", "- python-testing: path"]


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


def test_header_uses_wide_box_and_shows_active_skills(capsys, tmp_path: Path) -> None:
    print_header("Fix tests", tmp_path, "model", 20, "build", active_skills=["demo-skill"])

    output = capsys.readouterr().out
    assert "Mini Coding Agent" in output
    assert "Skills    : demo-skill" in output
    assert "─" * (MODE_BOX_WIDTH - 2) in output


def test_header_hides_skills_when_none(capsys, tmp_path: Path) -> None:
    print_header("Fix tests", tmp_path, "model", 20, "build")

    output = capsys.readouterr().out
    assert "Skills    :" not in output


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


def test_format_run_list_shows_recent_trajectories(tmp_path: Path) -> None:
    write_cli_jsonl(tmp_path / "trajectories" / "run-1.jsonl")

    text = format_run_list(tmp_path)

    assert "1. [success/build] Fix calculator" in text
    assert "run-1.jsonl" in text


def test_print_replay_command_renders_report(tmp_path: Path, capsys) -> None:
    write_cli_jsonl(tmp_path / "trajectories" / "run-1.jsonl")

    print_replay_command(tmp_path, "1")

    output = capsys.readouterr().out
    assert "Agent Run Report" in output
    assert "Fix calculator" in output
    assert "╭" not in output


def test_runs_command_uses_wide_box(tmp_path: Path, capsys) -> None:
    write_cli_jsonl(tmp_path / "trajectories" / "run-1.jsonl")
    args = type("Args", (), {"workspace": str(tmp_path), "mode": "build"})()

    handled = handle_session_command("/runs", args, SessionState())

    output = capsys.readouterr().out
    assert handled is False
    assert "Run History" in output
    assert "─" * (MODE_BOX_WIDTH - 2) in output


def test_skills_command_lists_workspace_skills(tmp_path: Path, capsys) -> None:
    skill_path = tmp_path / "skills" / "python-testing" / "SKILL.md"
    skill_path.parent.mkdir(parents=True)
    skill_path.write_text("# Python Testing\n\nRead tests first.\n", encoding="utf-8")
    args = type("Args", (), {"workspace": str(tmp_path), "mode": "build"})()

    handled = handle_session_command("/skills", args, SessionState())

    output = capsys.readouterr().out
    assert handled is False
    assert "python-testing" in output


def test_skill_use_and_remove_persist_in_skill_session(tmp_path: Path, capsys) -> None:
    skill_path = tmp_path / "skills" / "python-testing" / "SKILL.md"
    skill_path.parent.mkdir(parents=True)
    skill_path.write_text("# Python Testing\n\nRead tests first.\n", encoding="utf-8")
    args = type("Args", (), {"workspace": str(tmp_path), "mode": "build"})()
    session = SessionState()
    active_skills = SkillSession()

    handle_session_command("/skill use python-testing", args, session, active_skills)
    assert active_skills.names() == ["python-testing"]

    handle_session_command("/skill remove python-testing", args, session, active_skills)
    assert active_skills.names() == []
    assert "已移除" in capsys.readouterr().out


def test_skill_active_command_keeps_bullet_left_aligned(tmp_path: Path, capsys) -> None:
    skill_path = tmp_path / "skills" / "python-testing" / "SKILL.md"
    skill_path.parent.mkdir(parents=True)
    skill_path.write_text("# Python Testing\n\nRead tests first.\n", encoding="utf-8")
    args = type("Args", (), {"workspace": str(tmp_path), "mode": "build"})()
    active_skills = SkillSession()

    handle_session_command("/skill use python-testing", args, SessionState(), active_skills)
    capsys.readouterr()
    handle_session_command("/skill active", args, SessionState(), active_skills)

    output = capsys.readouterr().out
    assert "│ 已启用 skill：" in output
    assert "│ - python-testing:" in output


def test_skill_new_creates_template(tmp_path: Path, capsys) -> None:
    args = type("Args", (), {"workspace": str(tmp_path), "mode": "build"})()
    active_skills = SkillSession()

    handle_session_command("/skill new Bug Fixing", args, SessionState(), active_skills)

    assert (tmp_path / "skills" / "bug-fixing" / "SKILL.md").exists()
    assert "已创建" in capsys.readouterr().out


def test_read_interactive_args_does_not_clear_screen(monkeypatch) -> None:
    calls = 0

    def fail_clear() -> None:
        nonlocal calls
        calls += 1

    answers = iter(["q"])
    monkeypatch.setattr("mini_agent.cli.clear_screen", fail_clear)
    monkeypatch.setattr("builtins.input", lambda _prompt: next(answers))
    args = type("Args", (), {"task": "", "workspace": ".", "max_steps": 20, "mode": "build"})()

    result = read_interactive_args(args)

    assert result.task == "q"
    assert calls == 0


def test_print_thinking_ends_with_newline(capsys) -> None:
    print_thinking(1)

    output = capsys.readouterr().out
    assert output.endswith("\n")


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
