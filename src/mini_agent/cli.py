from __future__ import annotations

import argparse
from dataclasses import replace
from datetime import datetime
import os
import sys
from pathlib import Path
from unicodedata import east_asian_width

from .agent import CodingAgent
from .config import load_config
from .llm import LLMClient
from .protocol import Action, AgentResult, Observation


BOX_WIDTH = 66
BANNER_LINES = [
    "◆ ◈  C O D I N G   A G E N T  ◈ ◆",
    "from-scratch local programming assistant",
]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the mini coding agent.")
    parser.add_argument("task", nargs="?", help="Programming task for the agent.")
    parser.add_argument("-i", "--interactive", action="store_true", help="Open a small text UI before running.")
    parser.add_argument("--workspace", default=".", help="Workspace path. Defaults to current directory.")
    parser.add_argument("--model", default=None, help="Model name. Defaults to AGENT_MODEL or gpt-4.1-mini.")
    parser.add_argument("--max-steps", type=int, default=20, help="Maximum agent loop steps.")
    parser.add_argument("--mode", choices=["plan", "build"], default="build", help="Run in planning or build mode.")
    parser.add_argument(
        "--plan-output-dir",
        default="plans",
        help="Directory for plan-mode markdown output. Defaults to ./plans.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.interactive or not args.task:
        args = read_interactive_args(args)
    if not args.task:
        raise SystemExit("No task provided.")
    config = load_config(args.model)
    workspace = Path(args.workspace).resolve()
    print_header(args.task, workspace, config.model, args.max_steps, args.mode)
    agent = CodingAgent(
        llm=LLMClient(config),
        workspace=workspace,
        max_steps=args.max_steps,
        mode=args.mode,
        on_step=print_step,
        on_thinking=print_thinking,
    )
    result = agent.run(args.task)
    if args.mode == "plan" and result.summary:
        output_path = save_plan_result(result.summary, workspace, Path(args.plan_output_dir), args.task)
        result = replace(result, output_path=str(output_path))
    print_result(result)
    return 0 if result.success else 1


def read_interactive_args(args: argparse.Namespace) -> argparse.Namespace:
    clear_screen()
    print_banner(args.mode)
    mode = choose_mode(args.mode)
    clear_screen()
    print_banner(mode)
    print("  Enter task and options. Press Enter to keep defaults.")
    print()
    task = input_line("Task", args.task or "")
    workspace = input_line("Workspace", args.workspace)
    max_steps_raw = input_line("Max steps", str(args.max_steps))
    if mode == "plan":
        args.plan_output_dir = input_line("Plan dir", args.plan_output_dir)
    args.task = task
    args.workspace = workspace or "."
    args.mode = mode
    try:
        args.max_steps = int(max_steps_raw)
    except ValueError:
        args.max_steps = 20
    return args


def print_banner(mode: str) -> None:
    print_box([*BANNER_LINES, "", f"agent mode: {mode}"], border="double")


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
    print_box(
        [
            "Run Mode",
            "",
            f"{build:^18}  {plan:^18}",
            "",
            "m / Space / Tab : switch",
            "b or 1          : build",
            "p or 2          : plan",
            "Enter           : confirm",
        ],
        indent=2,
    )
    print()
    print("  Waiting for key...", end="", flush=True)


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
    tool = action.tool if action else observation.tool
    status = "OK" if observation.ok else "ERR"
    detail = observation.message or first_line(observation.content) or "-"
    marker = "✓" if observation.ok else "!"
    print(f"\r  {marker} step {step:02d}  {tool:<16} {status:<3}  {detail}")


def print_thinking(step: int) -> None:
    print(f"  · step {step:02d}  Thinking... waiting for model response", end="", flush=True)


def print_result(result: AgentResult) -> None:
    summary = result.summary or "-"
    if result.output_path:
        summary = f"Plan written to {result.output_path}"
    lines = [
        "Result",
        "",
        f"Status     : {'success' if result.success else 'stopped'}",
        f"Reason     : {result.termination_reason}",
        f"Summary    : {summary}",
        f"Modified   : {', '.join(result.modified_files) if result.modified_files else 'none'}",
    ]
    if result.verification_records:
        for record in result.verification_records:
            status = "passed" if record.passed else "failed"
            text = f"{record.command} -> {status} ({record.exit_code})"
            lines.append(f"Verify     : {text}")
    else:
        lines.append("Verify     : none")
    lines.append(f"Trajectory : {result.trajectory_path}")
    print_box(lines)


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


def print_box(lines: list[str], indent: int = 0, border: str = "single") -> None:
    prefix = " " * indent
    if border == "double":
        top_left, top_right, bottom_left, bottom_right, horizontal, vertical = "╔", "╗", "╚", "╝", "═", "║"
    else:
        top_left, top_right, bottom_left, bottom_right, horizontal, vertical = "╭", "╮", "╰", "╯", "─", "│"
    inner_width = BOX_WIDTH - 2
    content_width = inner_width - 2
    print(prefix + top_left + horizontal * inner_width + top_right)
    for raw_line in lines:
        wrapped_lines = wrap_box_line(raw_line, content_width)
        for line in wrapped_lines:
            if raw_line in BANNER_LINES or raw_line in {"Run Mode", "Result", "Mini Coding Agent"}:
                line = center_visual(line, content_width)
            print(prefix + vertical + " " + pad_visual(line, content_width) + " " + vertical)
    print(prefix + bottom_left + horizontal * inner_width + bottom_right)
    print()


def wrap_box_line(text: str, width: int) -> list[str]:
    if text == "" or text in BANNER_LINES or text in {"Run Mode", "Result", "Mini Coding Agent"}:
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


def pad_visual(text: str, width: int) -> str:
    return text + " " * max(0, width - visual_width(text))


def center_visual(text: str, width: int) -> str:
    padding = max(0, width - visual_width(text))
    left = padding // 2
    right = padding - left
    return " " * left + text + " " * right


if __name__ == "__main__":
    raise SystemExit(main())
