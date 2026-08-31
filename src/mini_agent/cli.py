from __future__ import annotations

import argparse
from dataclasses import replace
from datetime import datetime
import os
import shutil
import sys
from pathlib import Path
from unicodedata import east_asian_width

from .agent import CodingAgent
from .config import load_config
from .llm import LLMClient
from .logger import append_turn_summary
from .protocol import Action, AgentResult, Observation
from .replay import list_trajectories, render_trajectory_report, resolve_trajectory
from .session import SessionState, build_session_turn, format_turn_summary
from .turn_summary import generate_turn_summary


BOX_WIDTH = 66
MODE_BOX_WIDTH = 92
BANNER_BOX_WIDTH = 92
BANNER_LINES = [
    "  ___  ___  ___  ___  _  _  ___     ___  ___  ___  _  _  _____ ",
    " / __|/ _ \\|   \\|_ _|| \\| |/ __|   /   \\| __|| __|| \\| ||_   _|",
    "| (__| (_) | |) || | | .` | (_ |   | - || _| | _| | .` |  | |  ",
    " \\___|\\___/|___/|___||_|\\_|\\___|   |_|_||___||___||_|\\_|  |_|  ",
    "from-scratch local programming assistant",
]
EXIT_COMMANDS = {"q", "quit", "exit", ":q"}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the mini coding agent.")
    parser.add_argument("task", nargs="?", help="Programming task for the agent.")
    parser.add_argument("-i", "--interactive", action="store_true", help="Open a small text UI before running.")
    parser.add_argument("--workspace", default=".", help="Workspace path. Defaults to current directory.")
    parser.add_argument("--model", default=None, help="Model name. Defaults to AGENT_MODEL or gpt-4.1-mini.")
    parser.add_argument("--max-steps", type=int, default=20, help="Maximum agent loop steps.")
    parser.add_argument("--mode", choices=["plan", "build"], default="build", help="Run in planning or build mode.")
    parser.add_argument(
        "--replay",
        metavar="PATH",
        help="Render a trajectory JSONL report. Use 'latest' for the newest workspace trajectory.",
    )
    parser.add_argument("--replay-output", default=None, help="Optional markdown path for --replay output.")
    parser.add_argument(
        "--plan-output-dir",
        default="plans",
        help="Directory for plan-mode markdown output. Defaults to ./plans.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.replay:
        return run_replay(args)
    if args.interactive or not args.task:
        return run_interactive_session(args)
    config = load_config(args.model)
    result = run_single_task(args, config)
    return 0 if result.success else 1


def run_replay(args: argparse.Namespace) -> int:
    workspace = Path(args.workspace).resolve()
    try:
        trajectory_path = resolve_trajectory(workspace, args.replay)
        report = render_trajectory_report(trajectory_path)
        if args.replay_output:
            output_path = Path(args.replay_output)
            if not output_path.is_absolute():
                output_path = workspace / output_path
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(report.markdown, encoding="utf-8")
            print(f"Wrote replay report: {output_path}")
        else:
            print(report.markdown)
    except Exception as exc:
        print(f"Replay failed: {exc}", file=sys.stderr)
        return 1
    return 0


def run_single_task(args: argparse.Namespace, config: object, session_context: str = "") -> AgentResult:
    workspace = Path(args.workspace).resolve()
    print_header(args.task, workspace, config.model, args.max_steps, args.mode)
    llm = LLMClient(config)
    agent = CodingAgent(
        llm=llm,
        workspace=workspace,
        max_steps=args.max_steps,
        mode=args.mode,
        on_step=print_step,
        on_thinking=print_thinking,
        on_confirmation=confirm_tool_action if sys.stdin.isatty() else None,
    )
    result = agent.run(args.task, session_context=session_context)
    if args.mode == "plan" and result.summary:
        output_path = save_plan_result(result.summary, workspace, Path(args.plan_output_dir), args.task)
        result = replace(result, output_path=str(output_path))
    result = replace(result, turn_summary=generate_turn_summary(llm, args.task, args.mode, workspace, result))
    append_turn_summary(Path(result.trajectory_path), result.turn_summary, result.output_path)
    print_turn_result(result)
    return result


def run_interactive_session(args: argparse.Namespace) -> int:
    config = load_config(args.model)
    session = SessionState()
    clear_screen()
    print_banner(args.mode)
    args.mode = choose_mode(args.mode)
    print("  Enter task or command. Use /help for session commands. q/quit/exit to leave.")

    while True:
        args = read_interactive_args(args)
        if not args.task:
            print("  No task entered. Bye.")
            return 0
        if is_exit_command(args.task):
            print("  Bye.")
            return 0
        if is_session_command(args.task):
            if handle_session_command(args.task, args, session):
                return 0
            args.task = ""
            continue

        session_context = session.to_prompt_context()
        if is_context_dependent_task(args.task) and not session_context:
            print_box(
                [
                    "Session",
                    "",
                    "会话上下文为空，无法继续刚才的任务。",
                    "请重新输入明确目标，例如：请阅读 examples/demo_calculator 并修复测试。",
                    f"当前工作区仍是 {Path(args.workspace).resolve()}。",
                ]
            )
            args.task = ""
            continue

        workspace = str(Path(args.workspace).resolve())
        result = run_single_task(args, config, session_context=session_context)
        turn = build_session_turn(args.task, args.mode, workspace, result)
        session.add_turn(turn)
        args.task = ""
        next_action = input(
            "  Next: Enter=new task, b=build, p=plan, m=switch, /history, /runs, /replay latest, /clear, q=quit\n  > "
        ).strip()
        if is_exit_command(next_action):
            print("  Bye.")
            return 0
        if is_session_command(next_action):
            if handle_session_command(next_action, args, session):
                return 0
            continue
        next_action = next_action.lower()
        if next_action in {"b", "build", "1"}:
            args.mode = "build"
        elif next_action in {"p", "plan", "2"}:
            args.mode = "plan"
        elif next_action in {"m", "t", "switch"}:
            args.mode = "plan" if args.mode == "build" else "build"


def read_interactive_args(args: argparse.Namespace) -> argparse.Namespace:
    print()
    task = input_line("Task", args.task or "")
    args.task = task
    if is_exit_command(task) or is_session_command(task):
        return args
    workspace = input_line("Workspace", args.workspace)
    max_steps_raw = input_line("Max steps", str(args.max_steps))
    if args.mode == "plan":
        args.plan_output_dir = input_line("Plan dir", args.plan_output_dir)
    args.task = task
    args.workspace = workspace or "."
    try:
        args.max_steps = int(max_steps_raw)
    except ValueError:
        args.max_steps = 20
    return args


def is_exit_command(value: str) -> bool:
    return value.strip().lower() in EXIT_COMMANDS


def is_session_command(value: str) -> bool:
    text = value.strip().lower()
    return text.startswith("/")


def handle_session_command(command: str, args: argparse.Namespace, session: SessionState) -> bool:
    text = command.strip()
    lower = text.lower()
    name, _, value = text.partition(" ")
    name = name.lower()
    value = value.strip()

    if lower in {"/q", "/quit", "/exit"}:
        print("  Bye.")
        return True
    if name == "/clear":
        session.clear()
        print_box(
            [
                "Session",
                "",
                "会话上下文已清空，后续任务不会再携带之前的任务摘要。",
                f"当前工作区仍是 {Path(args.workspace).resolve()}，当前模式仍是 {args.mode}。",
            ]
        )
        return False
    if name in {"/summary", "/last"}:
        turn = session.last_turn()
        text = format_turn_summary(turn) if turn else "当前会话还没有上一轮任务总结。"
        print_box(["Session Summary", "", text])
        return False
    if name == "/history":
        print_box(["Session History", "", session.history_text()])
        return False
    if name == "/runs":
        print_box(["Run History", "", format_run_list(Path(args.workspace).resolve())], width=MODE_BOX_WIDTH)
        return False
    if name == "/replay":
        print_replay_command(Path(args.workspace).resolve(), value or "latest")
        return False
    if name == "/mode":
        if value.lower() in {"build", "plan"}:
            args.mode = value.lower()
            print_box(["Session", "", f"后续任务将使用 {args.mode} 模式。"])
        else:
            print_box(["Session", "", "请使用 /mode build 或 /mode plan。"])
        return False
    if name == "/workspace":
        if value:
            args.workspace = value
            print_box(["Session", "", f"后续任务的工作区已切换为 {Path(args.workspace).resolve()}。"])
        else:
            print_box(["Session", "", f"当前工作区是 {Path(args.workspace).resolve()}。"])
        return False
    if name == "/maxsteps":
        try:
            args.max_steps = int(value)
            print_box(["Session", "", f"后续任务的最大步数已设置为 {args.max_steps}。"])
        except ValueError:
            print_box(["Session", "", "请使用 /maxsteps 20 这样的整数参数。"])
        return False
    if name == "/help":
        print_box(
            [
                "Session Commands",
                "",
                "/summary        查看上一轮任务总结",
                "/history        查看最近几轮任务摘要",
                "/runs           列出最近的轨迹日志",
                "/replay latest  查看最新轨迹报告",
                "/replay N       查看 /runs 中第 N 条轨迹",
                "/replay PATH    查看指定 JSONL 轨迹",
                "/clear          清空会话上下文",
                "/mode build     切换到 build 模式",
                "/mode plan      切换到 plan 模式",
                "/workspace PATH 切换工作区",
                "/maxsteps N     设置最大步数",
                "/quit           退出",
            ]
        )
        return False

    print_box(["Session", "", "未知会话命令。使用 /help 查看可用命令。"])
    return False


def format_run_list(workspace: Path, limit: int = 10) -> str:
    items = list_trajectories(workspace, limit=limit)
    if not items:
        return f"未找到轨迹日志：{workspace / 'trajectories'}"
    lines = []
    for item in items:
        lines.append(f"{item.index}. [{item.status}/{item.mode}] {clip(item.task, 44)}")
        lines.append(f"   {item.path}")
    return "\n".join(lines)


def print_replay_command(workspace: Path, value: str) -> None:
    try:
        path = resolve_trajectory(workspace, value)
        report = render_trajectory_report(path)
    except Exception as exc:
        print_box(["Replay", "", f"无法生成轨迹报告：{exc}"])
        return
    print()
    print(report.markdown)


def is_context_dependent_task(task: str) -> bool:
    normalized = task.strip().lower()
    if not normalized:
        return False
    markers = [
        "继续",
        "刚才",
        "上一轮",
        "上一步",
        "前面",
        "之前",
        "continue",
        "previous",
        "last task",
        "last turn",
    ]
    return any(marker in normalized for marker in markers)


def wait_for_enter() -> None:
    input("  Press Enter to continue...")


def print_banner(mode: str) -> None:
    print_box([*BANNER_LINES, "", f"agent mode: {mode}"], border="double", width=BANNER_BOX_WIDTH, center=True)


def input_line(label: str, default: str) -> str:
    shown = f" [{default}]" if default else ""
    value = input(f"  {label:<10}{shown}\n  > ").strip()
    return value or default


def choose_mode(default: str) -> str:
    if os.name != "nt" or not sys.stdin.isatty():
        return choose_mode_fallback(default)

    import msvcrt

    mode = default
    while True:
        clear_screen()
        print_banner(mode)
        print_mode_card(mode)
        try:
            key = msvcrt.getwch()
        except KeyboardInterrupt:
            raise SystemExit("\nCancelled.")
        if key == "\x03":
            raise SystemExit("\nCancelled.")
        if key in {"\r", "\n"}:
            print()
            return mode
        if key in {"\t", "m", "M", " ", "t", "T"}:
            mode = "plan" if mode == "build" else "build"
        elif key in {"b", "B", "1"}:
            mode = "build"
        elif key in {"p", "P", "2"}:
            mode = "plan"


def choose_mode_fallback(default: str) -> str:
    value = input(f"Mode [{default}] (build/plan): ").strip().lower()
    if value in {"2", "plan", "p"}:
        return "plan"
    if value in {"1", "build", "b"}:
        return "build"
    return default


def print_mode_card(mode: str) -> None:
    build = "● BUILD" if mode == "build" else "○ build"
    plan = "● PLAN " if mode == "plan" else "○ plan "
    option_line = f"{build}             {plan}"
    print_box(
        [
            "Run Mode",
            "",
            center_line(option_line),
            "",
            center_line("m / Space / Tab : switch"),
            center_line("b or 1          : build"),
            center_line("p or 2          : plan"),
            center_line("Enter           : confirm"),
        ],
        width=MODE_BOX_WIDTH,
        center=True,
    )
    print()
    print(f"{box_prefix(MODE_BOX_WIDTH, center=True)}Waiting for key...", end="", flush=True)


def clear_screen() -> None:
    os.system("cls" if os.name == "nt" else "clear")


def print_header(task: str, workspace: Path, model: str, max_steps: int, mode: str) -> None:
    print()
    print_box(
        [
            "Mini Coding Agent",
            "",
            f"Task      : {task}",
            f"Workspace : {workspace}",
            f"Model     : {model}",
            f"Mode      : {mode}",
            f"Max steps : {max_steps}",
        ]
    )


def print_step(step: int, action: Action | None, observation: Observation) -> None:
    clear_line = "\r" + " " * 140 + "\r"
    print(clear_line + "  " + summarize_step(step, action, observation))


def confirm_tool_action(observation: Observation) -> bool:
    print()
    print_box(
        [
            "Confirmation",
            "",
            observation.message or observation.content or "This action requires confirmation.",
            f"Tool      : {observation.tool}",
            f"Risk      : {observation.data.get('risk_reason', observation.error_type or 'review required')}",
        ]
    )
    answer = input("  Allow this action? [y/N]\n  > ").strip().lower()
    return answer in {"y", "yes"}


def print_thinking(step: int) -> None:
    print(f"  · step {step:02d}  Thinking... waiting for model response", end="", flush=True)


def print_turn_result(result: AgentResult) -> None:
    summary = result.turn_summary or result.summary or "-"
    lines = ["Turn Summary", "", summary]
    print_box(lines)


def summarize_step(step: int, action: Action | None, observation: Observation) -> str:
    tool = action.tool if action else observation.tool
    status = "成功" if observation.ok else "失败"
    target = summarize_target(action)
    detail = observation.message or first_line(observation.content, limit=80)

    if observation.error_type == "TargetScopeViolation":
        scope = observation.data.get("target_scope", "当前目标目录")
        blocked = observation.data.get("blocked_path", target.strip() or "该路径")
        return f"第 {step:02d} 步：我拦截了对 {blocked} 的访问，因为当前任务已锁定在 {scope}；下一步应回到目标目录内行动。"
    if observation.needs_confirmation:
        return f"第 {step:02d} 步：{tool} 请求执行需要确认的操作{target}，已暂停执行并等待用户确认。"
    if observation.error_type == "PermissionError":
        return f"第 {step:02d} 步：我拒绝了 {tool} 操作{target}，原因是 {detail or '权限策略不允许'}。"
    if tool == "parser":
        return f"第 {step:02d} 步：模型输出没有通过动作格式解析，本步执行失败，原因是 {detail or '格式不合法'}。"
    if tool == "list_dir":
        return f"第 {step:02d} 步：我查看了目录{target}，执行{status}，接下来可以根据目录结构选择相关文件。"
    if tool == "read_file":
        return f"第 {step:02d} 步：我读取了文件{target}，执行{status}，把看到的内容作为下一步判断依据。"
    if tool == "search":
        return f"第 {step:02d} 步：我在工作区中检索了目标信息{target}，执行{status}，用于定位相关代码或测试。"
    if tool == "write_file":
        return f"第 {step:02d} 步：我写入了文件{target}，执行{status}，这一步产生了新的文件内容。"
    if tool == "append_file":
        return f"第 {step:02d} 步：我向文件{target} 追加了内容，执行{status}，这一步用于分块完成较大的文件。"
    if tool == "replace_in_file":
        return f"第 {step:02d} 步：我对文件{target}做了精确替换，执行{status}，这一步用于修复已有代码。"
    if tool == "run_shell":
        if observation.error_type == "UseReadFile":
            return f"第 {step:02d} 步：我拒绝了这条 shell 命令{target}，因为它看起来是在读取文件内容；下一步应该改用 read_file。"
        return f"第 {step:02d} 步：我运行了验证命令{target}，执行{status}，命令输出将用于判断任务是否完成。"
    if tool == "finish":
        return f"第 {step:02d} 步：模型提交了最终结果，执行{status}，本轮任务进入收尾阶段。"
    return f"第 {step:02d} 步：我调用了 {tool} 工具，执行{status}。"


def summarize_target(action: Action | None) -> str:
    if not action:
        return ""
    if "path" in action.args:
        return f" {action.args['path']}"
    if "command" in action.args:
        return f" {action.args['command']}"
    if "pattern" in action.args:
        return f" {action.args['pattern']}"
    return ""


def save_plan_result(summary: str, workspace: Path, output_dir: Path, task: str) -> Path:
    target_dir = output_dir if output_dir.is_absolute() else workspace / output_dir
    target_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    path = target_dir / f"plan-{timestamp}.md"
    content = f"# Agent Plan\n\n## Task\n\n{task}\n\n## Plan\n\n{summary.rstrip()}\n"
    path.write_text(content, encoding="utf-8")
    return path


def first_line(text: str, limit: int = 96) -> str:
    line = next((item.strip() for item in text.splitlines() if item.strip()), "")
    if len(line) <= limit:
        return line
    return line[: limit - 3] + "..."


def clip(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


def print_box(lines: list[str], indent: int = 0, border: str = "single", width: int = BOX_WIDTH, center: bool = False) -> None:
    prefix = box_prefix(width, indent=indent, center=center)
    if border == "double":
        top_left, top_right, bottom_left, bottom_right, horizontal, vertical = "╔", "╗", "╚", "╝", "═", "║"
    else:
        top_left, top_right, bottom_left, bottom_right, horizontal, vertical = "╭", "╮", "╰", "╯", "─", "│"
    inner_width = width - 2
    content_width = inner_width - 2
    print(prefix + top_left + horizontal * inner_width + top_right)
    for raw_line in lines:
        center = should_center_box_line(raw_line)
        visible_line = strip_center_marker(raw_line)
        wrapped_lines = wrap_box_line(visible_line, content_width)
        for line in wrapped_lines:
            if center:
                line = center_visual(line, content_width)
            print(prefix + vertical + " " + pad_visual(line, content_width) + " " + vertical)
    print(prefix + bottom_left + horizontal * inner_width + bottom_right)
    print()


def wrap_box_line(text: str, width: int) -> list[str]:
    if text == "" or should_center_box_line(text):
        return wrap_visual(text, width)

    separator_index = text.find(": ")
    if separator_index <= 0:
        return wrap_visual(text, width)

    prefix = text[: separator_index + 2]
    value = text[separator_index + 2 :]
    prefix_width = visual_width(prefix)
    if prefix_width >= width or not value:
        return wrap_visual(text, width)

    value_lines = wrap_visual(value, width - prefix_width)
    continuation = " " * len(prefix)
    return [prefix + value_lines[0], *[continuation + line for line in value_lines[1:]]]


def box_prefix(width: int, indent: int = 0, center: bool = False) -> str:
    if not center:
        return " " * indent
    terminal_width = shutil.get_terminal_size(fallback=(width + indent, 24)).columns
    return " " * max(indent, (terminal_width - width) // 2)


def wrap_visual(text: str, width: int) -> list[str]:
    if text == "":
        return [""]

    result: list[str] = []
    for raw_line in text.splitlines() or [""]:
        if raw_line == "":
            result.append("")
            continue
        current = ""
        current_width = 0
        for char in raw_line:
            char_width = visual_width(char)
            if current and current_width + char_width > width:
                result.append(current.rstrip())
                current = char
                current_width = char_width
            else:
                current += char
                current_width += char_width
        result.append(current.rstrip())
    return result


def visual_width(text: str) -> int:
    width = 0
    for char in text:
        width += 2 if east_asian_width(char) in {"F", "W"} else 1
    return width


def center_line(text: str) -> str:
    return f"__center__{text}"


def should_center_box_line(text: str) -> bool:
    return text.startswith("__center__") or text in BANNER_LINES or text in {"Run Mode", "Turn Summary", "Mini Coding Agent"}


def strip_center_marker(text: str) -> str:
    if text.startswith("__center__"):
        return text.removeprefix("__center__")
    return text


def pad_visual(text: str, width: int) -> str:
    return text + " " * max(0, width - visual_width(text))


def center_visual(text: str, width: int) -> str:
    padding = max(0, width - visual_width(text))
    left = padding // 2
    right = padding - left
    return " " * left + text + " " * right


if __name__ == "__main__":
    raise SystemExit(main())
