from __future__ import annotations

import base64
import binascii
import os
import platform
import re
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from .protocol import Action, Observation, VerificationRecord
from .safety import classify_shell_command, is_path_inside_workspace, is_sensitive_path


MAX_OBSERVATION_CHARS = 8000
MAX_READ_LINES = 120
MAX_WRITE_ACTION_LINES = 100
MAX_SEARCH_RESULTS = 50
DEFAULT_TIMEOUT_SECONDS = 30
IGNORED_DIRS = {
    ".git",
    ".venv",
    "venv",
    "env",
    "node_modules",
    "target",
    "dist",
    "build",
    "__pycache__",
    "trajectories",
}


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    args: dict[str, str]


@dataclass
class ToolContext:
    workspace: Path
    modified_files: list[str]
    inspected_paths: list[str]
    verification_records: list[VerificationRecord]
    confirmation_callback: Callable[[Observation], bool] | None = None

    def resolve_path(self, path: str | os.PathLike[str]) -> Path:
        candidate = Path(path)
        if not candidate.is_absolute():
            candidate = self.workspace / candidate
        return candidate.resolve()

    def check_path_permission(self, path: Path, tool: str, access: str) -> Observation | None:
        if not is_path_inside_workspace(path, self.workspace):
            message = f"Permission denied: {ctx_path(path)} is outside workspace {self.workspace}."
            return Observation(False, tool, content=message, error_type="PermissionError", message=message)
        if is_sensitive_path(path):
            message = f"Permission denied: {self.relative_path(path)} looks like a sensitive {access} target."
            return Observation(False, tool, content=message, error_type="PermissionError", message=message)
        return None

    def request_confirmation(self, observation: Observation) -> Observation | None:
        if self.confirmation_callback and self.confirmation_callback(observation):
            return None
        return observation

    def relative_path(self, path: Path) -> str:
        try:
            return str(path.resolve().relative_to(self.workspace))
        except ValueError:
            return str(path.resolve())

    def remember_modified(self, path: Path) -> None:
        rel = self.relative_path(path)
        if rel not in self.modified_files:
            self.modified_files.append(rel)

    def remember_inspected(self, path: Path) -> None:
        rel = self.relative_path(path)
        if rel not in self.inspected_paths:
            self.inspected_paths.append(rel)


ToolHandler = Callable[[ToolContext, dict[str, Any]], Observation]


@dataclass(frozen=True)
class Tool:
    spec: ToolSpec
    handler: ToolHandler


def truncate_text(text: str, limit: int = MAX_OBSERVATION_CHARS) -> tuple[str, bool]:
    if len(text) <= limit:
        return text, False
    half = max(1, limit // 2)
    return text[:half] + "\n... [truncated] ...\n" + text[-half:], True


def ctx_path(path: Path) -> str:
    return str(path.resolve())


def require_string(args: dict[str, Any], key: str) -> str:
    value = args.get(key)
    if not isinstance(value, str):
        raise ValueError(f"Argument '{key}' must be a string.")
    return value


def optional_int(args: dict[str, Any], key: str, default: int) -> int:
    value = args.get(key, default)
    if not isinstance(value, int):
        raise ValueError(f"Argument '{key}' must be an integer.")
    return value


class ToolRegistry:
    def __init__(self, context: ToolContext) -> None:
        self.context = context
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        self._tools[tool.spec.name] = tool

    def specs(self) -> list[ToolSpec]:
        return [tool.spec for tool in self._tools.values()]

    def execute(self, action: Action) -> Observation:
        tool = self._tools.get(action.tool)
        if tool is None:
            return Observation(
                ok=False,
                tool=action.tool,
                error_type="UnknownTool",
                message=f"Unknown tool: {action.tool}",
            )
        try:
            return tool.handler(self.context, action.args)
        except Exception as exc:
            return Observation(
                ok=False,
                tool=action.tool,
                error_type=type(exc).__name__,
                message=str(exc),
            )


def list_dir(ctx: ToolContext, args: dict[str, Any]) -> Observation:
    path = ctx.resolve_path(require_string(args, "path"))
    denied = ctx.check_path_permission(path, "list_dir", "directory listing")
    if denied:
        return denied
    ctx.remember_inspected(path)
    if not path.exists():
        return Observation(False, "list_dir", error_type="NotFound", message=f"Path does not exist: {ctx.relative_path(path)}")
    if not path.is_dir():
        return Observation(False, "list_dir", error_type="NotDirectory", message=f"Path is not a directory: {ctx.relative_path(path)}")

    entries = []
    for child in sorted(path.iterdir(), key=lambda item: (not item.is_dir(), item.name.lower())):
        kind = "dir" if child.is_dir() else "file"
        entries.append(f"{kind}\t{ctx.relative_path(child)}")
    content, truncated = truncate_text("\n".join(entries))
    return Observation(True, "list_dir", content=content, truncated=truncated, data={"path": ctx.relative_path(path)})


def read_file(ctx: ToolContext, args: dict[str, Any]) -> Observation:
    path = ctx.resolve_path(require_string(args, "path"))
    denied = ctx.check_path_permission(path, "read_file", "read")
    if denied:
        return denied
    ctx.remember_inspected(path)
    start = max(1, optional_int(args, "start", 1))
    end = optional_int(args, "end", start + MAX_READ_LINES - 1)
    end = min(end, start + MAX_READ_LINES - 1)

    if not path.exists():
        return Observation(False, "read_file", error_type="NotFound", message=f"File does not exist: {ctx.relative_path(path)}")
    if not path.is_file():
        return Observation(False, "read_file", error_type="NotFile", message=f"Path is not a file: {ctx.relative_path(path)}")

    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    selected = lines[start - 1 : end]
    content = "\n".join(f"{line_no}: {line}" for line_no, line in enumerate(selected, start=start))
    content, truncated_chars = truncate_text(content)
    truncated = truncated_chars or end < len(lines)
    return Observation(
        True,
        "read_file",
        content=content,
        truncated=truncated,
        data={"path": ctx.relative_path(path), "start": start, "end": min(end, len(lines)), "total_lines": len(lines)},
    )


def write_file(ctx: ToolContext, args: dict[str, Any]) -> Observation:
    path = ctx.resolve_path(require_string(args, "path"))
    denied = ctx.check_path_permission(path, "write_file", "write")
    if denied:
        return denied
    if path.exists():
        confirmation = confirmation_observation(
            "write_file",
            "OverwriteFile",
            f"write_file would overwrite existing file {ctx.relative_path(path)}.",
            {"path": ctx.relative_path(path)},
        )
        pending = ctx.request_confirmation(confirmation)
        if pending:
            return pending
    content = file_content_from_args(args)
    too_large = reject_large_write_chunk("write_file", content)
    if too_large:
        return too_large
    line_count = count_content_lines(content)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    ctx.remember_modified(path)
    return Observation(
        True,
        "write_file",
        content=f"Wrote {ctx.relative_path(path)} ({line_count} lines). Use append_file for the next chunk if more code is needed.",
        data={"path": ctx.relative_path(path), "line_count": line_count, "next_write_tool": "append_file"},
    )


def append_file(ctx: ToolContext, args: dict[str, Any]) -> Observation:
    path = ctx.resolve_path(require_string(args, "path"))
    denied = ctx.check_path_permission(path, "append_file", "write")
    if denied:
        return denied
    content = file_content_from_args(args)
    too_large = reject_large_write_chunk("append_file", content)
    if too_large:
        return too_large
    line_count = count_content_lines(content)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as file:
        file.write(content)
    ctx.remember_modified(path)
    return Observation(
        True,
        "append_file",
        content=f"Appended {line_count} lines to {ctx.relative_path(path)}. Continue with append_file if another chunk is needed.",
        data={"path": ctx.relative_path(path), "line_count": line_count, "next_write_tool": "append_file"},
    )


def file_content_from_args(args: dict[str, Any]) -> str:
    provided = [name for name in ("content", "content_lines", "content_base64") if name in args]
    if len(provided) != 1:
        raise ValueError("Provide exactly one of 'content', 'content_lines', or 'content_base64'.")
    if "content_base64" in args:
        encoded = require_string(args, "content_base64")
        try:
            return base64.b64decode(encoded, validate=True).decode("utf-8")
        except (binascii.Error, UnicodeDecodeError) as exc:
            raise ValueError(f"Invalid UTF-8 base64 content: {exc}") from exc
    if "content_lines" in args:
        lines = args["content_lines"]
        if not isinstance(lines, list) or not all(isinstance(line, str) for line in lines):
            raise ValueError("Argument 'content_lines' must be a list of strings.")
        return "\n".join(lines) + "\n"
    return require_string(args, "content")


def reject_large_write_chunk(tool: str, content: str) -> Observation | None:
    line_count = count_content_lines(content)
    if line_count <= MAX_WRITE_ACTION_LINES:
        return None
    message = (
        f"One {tool} action can write at most {MAX_WRITE_ACTION_LINES} lines, "
        f"but received {line_count}. Split the file into chunks and continue with append_file."
    )
    return Observation(
        False,
        tool,
        error_type="WriteChunkTooLarge",
        message=message,
        content=message,
        data={"line_count": line_count, "max_lines": MAX_WRITE_ACTION_LINES},
    )


def count_content_lines(content: str) -> int:
    if not content:
        return 0
    return len(content.splitlines())


def replace_in_file(ctx: ToolContext, args: dict[str, Any]) -> Observation:
    path = ctx.resolve_path(require_string(args, "path"))
    denied = ctx.check_path_permission(path, "replace_in_file", "write")
    if denied:
        return denied
    old = require_string(args, "old")
    new = require_string(args, "new")
    if not path.exists() or not path.is_file():
        return Observation(False, "replace_in_file", error_type="NotFound", message=f"File does not exist: {ctx.relative_path(path)}")

    content = path.read_text(encoding="utf-8", errors="replace")
    count = content.count(old)
    if count != 1:
        return Observation(
            False,
            "replace_in_file",
            error_type="ReplacementNotUnique",
            message=f"Expected exactly one match for old text, found {count}.",
        )
    path.write_text(content.replace(old, new, 1), encoding="utf-8")
    ctx.remember_modified(path)
    return Observation(True, "replace_in_file", content=f"Replaced text in {ctx.relative_path(path)}", data={"path": ctx.relative_path(path)})


def search(ctx: ToolContext, args: dict[str, Any]) -> Observation:
    pattern = require_string(args, "pattern")
    root = ctx.resolve_path(args.get("path", "."))
    denied = ctx.check_path_permission(root, "search", "search")
    if denied:
        return denied
    ctx.remember_inspected(root)
    if not root.exists():
        return Observation(False, "search", error_type="NotFound", message=f"Path does not exist: {ctx.relative_path(root)}")

    try:
        regex = re.compile(pattern)
    except re.error as exc:
        return Observation(False, "search", error_type="InvalidRegex", message=str(exc))

    files = [root] if root.is_file() else [
        path
        for path in root.rglob("*")
        if path.is_file() and not any(part in IGNORED_DIRS for part in path.parts) and not is_sensitive_path(path)
    ]

    results: list[str] = []
    for path in files:
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        for line_no, line in enumerate(lines, start=1):
            if regex.search(line):
                results.append(f"{ctx.relative_path(path)}:{line_no}: {line.strip()}")
                if len(results) >= MAX_SEARCH_RESULTS:
                    content = "\n".join(results)
                    content, truncated_chars = truncate_text(content)
                    return Observation(True, "search", content=content, truncated=True or truncated_chars, data={"matches": len(results)})

    content = "\n".join(results) if results else "No matches found."
    content, truncated = truncate_text(content)
    return Observation(True, "search", content=content, truncated=truncated, data={"matches": len(results)})


def run_shell(ctx: ToolContext, args: dict[str, Any]) -> Observation:
    command = require_string(args, "command")
    if looks_like_file_read_command(command):
        return Observation(
            False,
            "run_shell",
            error_type="UseReadFile",
            message="Use read_file instead of shell commands to inspect file content.",
            data={"command": command},
        )
    risk = classify_shell_command(command)
    if risk.level == "blocked":
        message = f"Blocked shell command: {risk.reason}."
        return Observation(
            False,
            "run_shell",
            content=message,
            error_type="PermissionError",
            message=message,
            data={"command": command, "risk_level": risk.level, "risk_reason": risk.reason},
        )
    if risk.level == "review":
        confirmation = confirmation_observation(
            "run_shell",
            "ShellCommandRequiresConfirmation",
            f"Shell command requires confirmation: {risk.reason}.",
            {"command": command, "risk_level": risk.level, "risk_reason": risk.reason},
        )
        pending = ctx.request_confirmation(confirmation)
        if pending:
            return pending
    timeout = optional_int(args, "timeout", DEFAULT_TIMEOUT_SECONDS)
    start = time.monotonic()
    shell_command = build_shell_command(command)
    try:
        completed = subprocess.run(
            shell_command,
            cwd=ctx.workspace,
            shell=False,
            text=True,
            capture_output=True,
            timeout=timeout,
        )
        duration = time.monotonic() - start
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout or ""
        stderr = exc.stderr or ""
        content, truncated = truncate_text(f"Command timed out after {timeout}s.\nSTDOUT:\n{stdout}\nSTDERR:\n{stderr}")
        return Observation(
            False,
            "run_shell",
            content=content,
            error_type="TimeoutExpired",
            message=f"Command timed out after {timeout}s.",
            truncated=truncated,
            data={"command": command, "timeout": timeout},
        )

    stdout, stdout_truncated = truncate_text(completed.stdout)
    stderr, stderr_truncated = truncate_text(completed.stderr)
    content = f"exit_code: {completed.returncode}\nduration: {duration:.2f}s\nSTDOUT:\n{stdout}\nSTDERR:\n{stderr}"
    content, content_truncated = truncate_text(content)

    is_verification = looks_like_verification(command)
    if is_verification:
        ctx.verification_records.append(
            VerificationRecord(command=command, exit_code=completed.returncode, passed=completed.returncode == 0)
        )
    error_type = None
    message = None
    if completed.returncode != 0:
        error_type = "VerificationError" if is_verification else "CommandFailed"
        message = (
            f"Verification command exited with {completed.returncode}."
            if is_verification
            else f"Command exited with {completed.returncode}."
        )

    return Observation(
        completed.returncode == 0,
        "run_shell",
        content=content,
        error_type=error_type,
        message=message,
        truncated=stdout_truncated or stderr_truncated or content_truncated,
        data={
            "command": command,
            "shell": shell_name(),
            "exit_code": completed.returncode,
            "duration": duration,
            "risk_level": risk.level,
            "is_verification": is_verification,
        },
    )


def confirmation_observation(tool: str, error_type: str, message: str, data: dict[str, Any]) -> Observation:
    return Observation(
        False,
        tool,
        content=message,
        error_type=error_type,
        message=message,
        needs_confirmation=True,
        data={"needs_confirmation": True, **data},
    )


def build_shell_command(command: str) -> list[str]:
    if platform.system().lower() == "windows":
        return ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", command]
    return ["/bin/sh", "-lc", command]


def shell_name() -> str:
    return "PowerShell" if platform.system().lower() == "windows" else "sh"


def looks_like_verification(command: str) -> bool:
    lowered = command.lower()
    if classify_shell_command(command).level == "review":
        return False
    keywords = ["test", "pytest", "unittest", "mvn", "gradle", "npm run", "pnpm test", "cargo test", "go test", "ruff", "mypy"]
    return any(keyword in lowered for keyword in keywords)


def looks_like_file_read_command(command: str) -> bool:
    lowered = command.lower()
    blocked_patterns = [
        r"\bget-content\b",
        r"\bgc\b",
        r"\bcat\b",
        r"\btype\b",
        r"\bhead\b",
        r"\btail\b",
        r"\bsed\s+-n\b",
    ]
    return any(re.search(pattern, lowered) for pattern in blocked_patterns)


def finish(_ctx: ToolContext, args: dict[str, Any]) -> Observation:
    summary = args.get("summary", "")
    changed_files = args.get("changed_files", [])
    verification = args.get("verification", "")
    if not isinstance(summary, str):
        raise ValueError("Argument 'summary' must be a string.")
    if not isinstance(changed_files, list):
        raise ValueError("Argument 'changed_files' must be a list.")
    if not isinstance(verification, str):
        raise ValueError("Argument 'verification' must be a string.")
    content = f"summary: {summary}\nchanged_files: {changed_files}\nverification: {verification}"
    return Observation(True, "finish", content=content, data={"summary": summary, "changed_files": changed_files, "verification": verification})


def build_default_registry(context: ToolContext, mode: str = "build") -> ToolRegistry:
    registry = ToolRegistry(context)
    registry.register(Tool(ToolSpec("list_dir", "List files and directories under a path.", {"path": "Directory path."}), list_dir))
    registry.register(Tool(ToolSpec("read_file", "Read a UTF-8 text file with line numbers.", {"path": "File path.", "start": "Start line.", "end": "End line."}), read_file))
    registry.register(Tool(ToolSpec("search", "Search files by regex pattern.", {"pattern": "Regex pattern.", "path": "Root path."}), search))
    if mode == "plan":
        registry.register(Tool(ToolSpec("finish", "Finish the planning task with a summary.", {"summary": "Plan summary.", "changed_files": "Use an empty list.", "verification": "Use planning only."}), finish))
        return registry
    registry.register(Tool(ToolSpec("write_file", "Create or overwrite a UTF-8 text file. Each write action is limited to 100 lines. Use content_base64 for code containing quotes, docstrings, or backslashes.", {"path": "File path.", "content": "Single string content.", "content_lines": "Optional list of simple lines.", "content_base64": "Optional single-line UTF-8 base64 content."}), write_file))
    registry.register(Tool(ToolSpec("append_file", "Append UTF-8 text to an existing or new file. Each append action is limited to 100 lines. Use this after write_file when generating a large file in chunks.", {"path": "File path.", "content": "Single string content.", "content_lines": "Optional list of simple lines.", "content_base64": "Optional single-line UTF-8 base64 content."}), append_file))
    registry.register(Tool(ToolSpec("replace_in_file", "Replace a unique text span in a file.", {"path": "File path.", "old": "Existing text.", "new": "Replacement text."}), replace_in_file))
    registry.register(Tool(ToolSpec("run_shell", f"Run a {shell_name()} command in the workspace. Prefer this for tests, not file discovery.", {"command": "Command to run.", "timeout": "Optional timeout seconds."}), run_shell))
    registry.register(Tool(ToolSpec("finish", "Finish the task with summary and verification.", {"summary": "What was done.", "changed_files": "Changed files.", "verification": "Verification result."}), finish))
    return registry
