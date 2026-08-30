from __future__ import annotations

import re
from pathlib import Path, PurePosixPath

from .context import should_capture_working_note
from .protocol import Action, AgentState, Observation


PATH_TOOL_NAMES = {
    "list_dir",
    "read_file",
    "search",
    "write_file",
    "append_file",
    "replace_in_file",
}
PATH_TOKEN_RE = re.compile(r"(?<!\w)([A-Za-z0-9_.-]+(?:[\\/][A-Za-z0-9_.-]+)+)")


def infer_initial_target_scope(task: str, workspace: Path) -> tuple[str, str]:
    for raw_path in PATH_TOKEN_RE.findall(task):
        normalized = normalize_rel_path(raw_path)
        if not normalized or normalized == ".":
            continue
        candidate = (workspace / normalized).resolve()
        try:
            candidate.relative_to(workspace.resolve())
        except ValueError:
            continue
        if candidate.exists():
            if candidate.is_file():
                parent = normalize_rel_path(str(PurePosixPath(normalized).parent))
                return parent, f"user named file path {normalized}"
            if candidate.is_dir():
                return normalized, f"user named directory path {normalized}"
    return "", ""


def apply_target_scope_guard(state: AgentState, action: Action) -> Observation | None:
    if not state.target_scope or action.tool not in PATH_TOOL_NAMES:
        return None
    raw_path = action.args.get("path")
    if not isinstance(raw_path, str):
        return None
    path = normalize_rel_path(raw_path)
    scope = normalize_rel_path(state.target_scope)
    if path_is_inside_scope(path, scope):
        return None
    if task_explicitly_mentions_path(state.user_task, path):
        return None

    message = (
        f"Target scope is locked to {scope!r}. Do not inspect or edit {path!r}. "
        f"Retry with a path inside {scope!r}, or act using the requirements already in Persistent Working Notes."
    )
    return Observation(
        False,
        "target_scope",
        content=message,
        error_type="TargetScopeViolation",
        message=message,
        data={
            "target_scope": scope,
            "blocked_path": path,
            "retryable": True,
            "retry_hint": message,
        },
    )


def update_target_scope_from_observation(state: AgentState, action: Action, observation: Observation) -> None:
    if state.target_scope or not observation.ok:
        return
    if action.tool == "read_file":
        path = str(observation.data.get("path") or action.args.get("path", ""))
        lock_scope_from_important_path(state, path, "read important task file")
    elif action.tool == "list_dir":
        listed_dir = str(observation.data.get("path") or action.args.get("path", ""))
        for line in observation.content.splitlines():
            _, _, listed_path = line.partition("\t")
            if listed_path and should_capture_working_note(listed_path):
                state.target_scope = normalize_rel_path(listed_dir)
                state.target_scope_reason = f"listed important task file {normalize_rel_path(listed_path)}"
                return


def lock_scope_from_important_path(state: AgentState, path: str, reason: str) -> None:
    normalized = normalize_rel_path(path)
    if not normalized or not should_capture_working_note(normalized):
        return
    parent = normalize_rel_path(str(PurePosixPath(normalized).parent))
    if parent and parent != ".":
        state.target_scope = parent
        state.target_scope_reason = f"{reason}: {normalized}"


def normalize_rel_path(path: str) -> str:
    normalized = path.replace("\\", "/").strip().strip("\"'")
    while normalized.startswith("./"):
        normalized = normalized[2:]
    normalized = normalized.rstrip("/")
    return normalized or "."


def path_is_inside_scope(path: str, scope: str) -> bool:
    if scope in {"", "."}:
        return True
    return path == scope or path.startswith(scope + "/")


def task_explicitly_mentions_path(task: str, path: str) -> bool:
    if path in {"", "."}:
        return False
    normalized_task = task.replace("\\", "/")
    return path in normalized_task
