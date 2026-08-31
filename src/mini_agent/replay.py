from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .safety import classify_shell_command


@dataclass(frozen=True)
class ReplayReport:
    trajectory_path: Path
    markdown: str


@dataclass(frozen=True)
class RunListItem:
    index: int
    path: Path
    task: str
    status: str
    mode: str
    modified_time: float


def latest_trajectory(workspace: Path) -> Path | None:
    directory = workspace / "trajectories"
    if not directory.exists():
        return None
    runs = list(directory.glob("run-*.jsonl"))
    if not runs:
        return None
    return max(runs, key=lambda path: path.stat().st_mtime)


def list_trajectories(workspace: Path, limit: int = 10) -> list[RunListItem]:
    directory = workspace / "trajectories"
    if not directory.exists():
        return []
    paths = sorted(directory.glob("run-*.jsonl"), key=lambda path: path.stat().st_mtime, reverse=True)
    items: list[RunListItem] = []
    for index, path in enumerate(paths[:limit], start=1):
        try:
            events = read_jsonl(path)
        except ValueError:
            events = []
        start = first_event(events, "start")
        end = first_event(events, "end")
        status = "success" if end.get("success") else str(end.get("termination_reason") or "unknown")
        items.append(
            RunListItem(
                index=index,
                path=path,
                task=str(start.get("task") or "-"),
                status=status,
                mode=str(start.get("mode") or "-"),
                modified_time=path.stat().st_mtime,
            )
        )
    return items


def resolve_trajectory(workspace: Path, value: str) -> Path:
    if value == "latest":
        latest = latest_trajectory(workspace)
        if latest is None:
            raise FileNotFoundError(f"No trajectories found under {workspace / 'trajectories'}.")
        return latest
    if value.isdigit():
        items = list_trajectories(workspace, limit=max(10, int(value)))
        index = int(value)
        for item in items:
            if item.index == index:
                return item.path
        raise FileNotFoundError(f"No trajectory numbered {index}. Use /runs to list available runs.")
    path = Path(value)
    if not path.is_absolute():
        path = workspace / path
    path = path.resolve()
    if not path.exists():
        raise FileNotFoundError(f"Trajectory does not exist: {path}")
    if not path.is_file():
        raise ValueError(f"Trajectory is not a file: {path}")
    return path


def render_trajectory_report(path: Path) -> ReplayReport:
    events = read_jsonl(path)
    start = first_event(events, "start")
    end = first_event(events, "end")
    turn_summary = first_event(events, "turn_summary")
    steps = [event for event in events if event.get("type") == "step"]

    lines = [
        "# Agent Run Report",
        "",
        f"- Trajectory: `{path}`",
        f"- Task: {value_or_dash(start.get('task'))}",
        f"- Workspace: `{value_or_dash(start.get('workspace'))}`",
        f"- Mode: `{value_or_dash(start.get('mode'))}`",
        f"- Max steps: {value_or_dash(start.get('max_steps'))}",
        f"- Session context: {'yes' if start.get('has_session_context') else 'no'}",
        f"- Result: {format_result(end)}",
        "",
        "## Step Timeline",
        "",
    ]

    if not steps:
        lines.append("No steps recorded.")
    for step in steps:
        lines.extend(format_step(step))

    lines.extend(["", "## Modified Files", ""])
    modified = modified_files_from_steps(steps)
    lines.extend(f"- `{path}`" for path in modified) if modified else lines.append("- none")

    lines.extend(["", "## Shell Commands", ""])
    shell_commands = shell_commands_from_steps(steps)
    lines.extend(shell_commands) if shell_commands else lines.append("- none")

    lines.extend(["", "## Verification", ""])
    verification = verification_from_steps(steps)
    lines.extend(verification) if verification else lines.append("- none")

    errors = errors_from_steps(steps)
    lines.extend(["", "## Errors And Recovery", ""])
    lines.extend(errors) if errors else lines.append("- none")

    if end:
        lines.extend(["", "## Final Summary", "", str(end.get("summary") or "-")])
    if turn_summary:
        lines.extend(["", "## Turn Summary", "", str(turn_summary.get("turn_summary") or "-")])

    return ReplayReport(trajectory_path=path, markdown="\n".join(lines).rstrip() + "\n")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSONL at {path}:{line_no}: {exc.msg}") from exc
        if isinstance(event, dict):
            events.append(event)
    return events


def first_event(events: list[dict[str, Any]], event_type: str) -> dict[str, Any]:
    return next((event for event in events if event.get("type") == event_type), {})


def format_step(step: dict[str, Any]) -> list[str]:
    action = step.get("parsed_action") or {}
    observation = step.get("observation") or {}
    tool = action.get("tool") or observation.get("tool") or "unknown"
    args = action.get("args") if isinstance(action.get("args"), dict) else {}
    ok = "ok" if observation.get("ok") else "failed"
    target = step_target(args)
    line = f"{step.get('step')}. `{tool}` {target} -> **{ok}**"
    details = []
    error_type = observation.get("error_type")
    if error_type:
        details.append(f"error={error_type}")
    if observation.get("needs_confirmation"):
        details.append("needs_confirmation=true")
    message = observation.get("message") or first_content_line(str(observation.get("content") or ""))
    if message:
        details.append(clip(message, 140))
    return [line, f"   - {'; '.join(details)}" if details else ""]


def step_target(args: dict[str, Any]) -> str:
    if "path" in args:
        return f"`{args['path']}`"
    if "command" in args:
        return f"`{args['command']}`"
    if "pattern" in args:
        return f"`{args['pattern']}`"
    return ""


def modified_files_from_steps(steps: list[dict[str, Any]]) -> list[str]:
    modified: list[str] = []
    for step in steps:
        action = step.get("parsed_action") or {}
        if action.get("tool") not in {"write_file", "append_file", "replace_in_file"}:
            continue
        args = action.get("args") if isinstance(action.get("args"), dict) else {}
        path = args.get("path")
        if isinstance(path, str) and path not in modified:
            modified.append(path)
    return modified


def verification_from_steps(steps: list[dict[str, Any]]) -> list[str]:
    results: list[str] = []
    for step in steps:
        action = step.get("parsed_action") or {}
        if action.get("tool") != "run_shell":
            continue
        observation = step.get("observation") or {}
        data = observation.get("data") if isinstance(observation.get("data"), dict) else {}
        command = data.get("command") or (action.get("args") or {}).get("command")
        if not is_verification_command(command, data):
            continue
        exit_code = data.get("exit_code", "-")
        status = "passed" if observation.get("ok") else "failed"
        results.append(f"- `{command}` -> {status} ({exit_code})")
    return results


def shell_commands_from_steps(steps: list[dict[str, Any]]) -> list[str]:
    results: list[str] = []
    for step in steps:
        action = step.get("parsed_action") or {}
        if action.get("tool") != "run_shell":
            continue
        observation = step.get("observation") or {}
        data = observation.get("data") if isinstance(observation.get("data"), dict) else {}
        command = data.get("command") or (action.get("args") or {}).get("command")
        exit_code = data.get("exit_code", "-")
        status = "passed" if observation.get("ok") else "failed"
        risk = data.get("risk_level", "-")
        results.append(f"- `{command}` -> {status} ({exit_code}), risk={risk}")
    return results


def is_verification_command(command: Any, data: dict[str, Any]) -> bool:
    if data.get("is_verification") is True:
        return True
    if not isinstance(command, str) or classify_shell_command(command).level == "review":
        return False
    lowered = command.lower()
    keywords = ["test", "pytest", "unittest", "mvn", "gradle", "pnpm test", "cargo test", "go test", "ruff", "mypy"]
    return any(keyword in lowered for keyword in keywords)


def errors_from_steps(steps: list[dict[str, Any]]) -> list[str]:
    errors: list[str] = []
    for step in steps:
        observation = step.get("observation") or {}
        if observation.get("ok"):
            continue
        error_type = observation.get("error_type") or "Error"
        message = observation.get("message") or first_content_line(str(observation.get("content") or ""))
        errors.append(f"- step {step.get('step')}: `{error_type}` - {clip(message, 180)}")
    return errors


def format_result(end: dict[str, Any]) -> str:
    if not end:
        return "unknown"
    status = "success" if end.get("success") else "failed"
    reason = end.get("termination_reason") or "-"
    return f"{status} (`{reason}`)"


def value_or_dash(value: Any) -> str:
    if value is None or value == "":
        return "-"
    return str(value)


def first_content_line(text: str) -> str:
    return next((line.strip() for line in text.splitlines() if line.strip()), "")


def clip(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."
