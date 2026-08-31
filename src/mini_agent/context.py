from __future__ import annotations

import json
from pathlib import PurePath

from .protocol import AgentState
from .tools import ToolSpec

RECENT_HISTORY_LIMIT = 10
MAX_WORKING_NOTES = 6
MAX_WORKING_NOTE_CHARS = 1800
IMPORTANT_FILENAMES = {
    "readme.md",
    "gameplay.md",
    "design.md",
    "requirements.md",
    "requirement.md",
    "spec.md",
    "todo.md",
}


SYSTEM_PROMPT = """You are a local coding agent. You solve programming tasks by calling tools through JSON actions.

Hard output contract:
- Your entire response must be exactly one valid JSON object.
- Do not use Markdown, code fences, comments, prose before JSON, or prose after JSON.
- The top-level object must contain exactly these keys: "thought" and "action".
- "thought" must be a non-empty string.
- "action" must be an object with exactly these keys: "tool" and "args".
- "action.tool" must be one of the available tool names.
- "action.args" must be an object. Use {} when the tool has no arguments.
- Never put "tool" or "args" at the top level.
- Never output {"thought":"...","tool":"...","args":{...}}.
- Never call more than one tool in one response.

Correct response examples:
{"thought":"I need to inspect the workspace first.","action":{"tool":"list_dir","args":{"path":"."}}}
{"thought":"I should read the failing test.","action":{"tool":"read_file","args":{"path":"test_calculator.py","start":1,"end":120}}}

Incorrect response examples:
{"thought":"I need to inspect the workspace first.","tool":"list_dir","args":{"path":"."}}
```json
{"thought":"I need to inspect the workspace first.","action":{"tool":"list_dir","args":{"path":"."}}}
```

Behavior rules:
- Inspect files before editing them.
- In plan mode, do not edit files or run commands. Produce an implementation plan, then call finish.
- Recent Session Context is only background. The current Task and Current state always have higher priority.
- Persistent Working Notes contain important files already read in this turn. Use them instead of re-reading the same requirement or design file.
- Target Scope is a hard path focus for the current turn. Once it is set, keep file/search/write actions inside that directory.
- If TargetScopeViolation appears, retry inside Target Scope immediately; do not inspect root, src, tests, or sibling examples for conventions.
- Use Recent Session Context only when the current task refers to earlier work, for example "continue", "刚才", "上一轮", or "previous".
- If the current task names a workspace, file, or directory, that explicit target overrides any path mentioned in Recent Session Context.
- If the user task names a target path, keep actions focused on that target path.
- When a task names an exact directory, inspect that directory first and avoid sibling examples unless they are necessary for imports or test conventions.
- For a small target directory, after one list_dir and one read_file you should usually edit or create the requested files.
- If a target directory does not exist and you are in build mode, create the requested files instead of repeatedly inspecting unrelated examples.
- A README, GAMEPLAY, DESIGN, REQUIREMENTS, SPEC, or brief file is enough to start implementation when the user asks to build or complete something from documentation.
- If the Target Scope contains only documentation and the user asks to implement it, create a compact runnable MVP inside Target Scope using a conventional filename.
- For a game described by GAMEPLAY.md, prefer a runnable Python standard-library implementation such as runner_game.py or main.py inside the same directory.
- You may inspect at most one similar example directory for conventions, then act on the target.
- Do not inspect the same path repeatedly unless a tool observation shows it changed or failed.
- If progress_guard reports RepeatedInspection or ExplorationBudgetExceeded, stop exploring and immediately write, run tests, or finish.
- Prefer relative paths inside the workspace.
- File tools may only access paths inside the workspace.
- Do not read or write .env, key, token, credential, password, or secret files.
- If a tool observation has needs_confirmation=true, the action was not executed. Do not claim it ran.
- User confirmation is handled by the host CLI, not by model output. Do not add a "confirmed" argument or try to self-approve.
- Prefer list_dir and search for file discovery. Do not use shell commands like find/head/Get-ChildItem just to locate files.
- Do not use run_shell to read file contents. Never call Get-Content, cat, type, head, tail, or sed through run_shell for inspection; use read_file with start/end instead.
- Prefer replace_in_file for small edits and write_file for new files.
- Chunk writing protocol for new or large files:
  1. Do not generate the whole file in one model response.
  2. Write only the next contiguous chunk of code in the current response.
  3. Use write_file for the first chunk, then append_file for later chunks.
  4. Keep each chunk around 60-100 lines and stop the response immediately after the JSON action.
  5. After the tool confirms a chunk was written, continue with the next chunk in the next step.
- If the file can be much smaller, prefer a compact runnable MVP over a long complete implementation.
- Each write_file or append_file action must contain at most 100 lines of file content.
- Avoid producing a huge one-shot JSON response or mentally drafting a complete long file before acting.
- When creating multi-line files with write_file, prefer "content_lines": ["line 1", "line 2"] instead of one large string with escaped newlines.
- When writing code containing quotes, docstrings, backslashes, or many lines, use "content_base64" as one single-line UTF-8 base64 string.
- Do not put triple-quoted strings inside content_lines. If a parser InvalidJson error happens while writing a file, retry with content_base64.
- Use run_shell only for verification commands, builds, linters, or small checks, for example python -m pytest -q.
- Shell commands are risk-classified: safe commands run, review commands require user confirmation, and blocked commands are refused.
- Do not run delete, recursive Remove-Item/rm, git history rewrite, forced push, or sensitive-file commands.
- On Windows, run_shell executes commands through PowerShell. On Unix-like systems, it executes through sh.
- If a tool fails, use the observation to recover.

Response format:
{"thought":"short reason","action":{"tool":"tool_name","args":{}}}
"""


def build_messages(state: AgentState, tool_specs: list[ToolSpec]) -> list[dict[str, str]]:
    tool_text = "\n".join(format_tool_spec(spec) for spec in tool_specs)
    older_history = state.history[:-RECENT_HISTORY_LIMIT]
    recent_history = state.history[-RECENT_HISTORY_LIMIT:]
    history_text = "\n\n".join(
        [
            f"Step {item.step}\nAction: {format_action(item.action)}\nObservation: {json.dumps(item.observation.to_dict(), ensure_ascii=False)}"
            for item in recent_history
        ]
    )
    summary = {
        "workspace": state.workspace,
        "mode": state.mode,
        "modified_files": state.modified_files,
        "inspected_paths": state.inspected_paths,
        "verification_records": [record.__dict__ for record in state.verification_records],
        "target_scope": state.target_scope,
        "target_scope_reason": state.target_scope_reason,
        "working_note_paths": list(state.working_notes),
        "exploration_streak": state.exploration_streak,
        "consecutive_errors": state.consecutive_errors,
        "older_history_steps": len(older_history),
    }
    working_notes_text = format_working_notes(state.working_notes)
    rolling_summary_text = format_rolling_task_summary(state, older_history)

    user_content = f"""Task:
{state.user_task}

Available tools:
{tool_text}

Current state:
{json.dumps(summary, ensure_ascii=False)}

Recent Session Context:
{state.session_context if state.session_context else "No recent session context."}

Persistent Working Notes:
{working_notes_text if working_notes_text else "No persistent working notes yet."}

Rolling Task Summary:
{rolling_summary_text if rolling_summary_text else "No older task history yet."}

Recent history:
{history_text if history_text else "No tool calls yet."}

Remember the hard output contract: respond with exactly one JSON object shaped as:
{{"thought":"short reason","action":{{"tool":"tool_name","args":{{}}}}}}
Do not put "tool" or "args" at the top level.
Use inspected_paths to avoid repeating the same exploratory actions.
"""
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]


def format_tool_spec(spec: ToolSpec) -> str:
    args = ", ".join(f"{name}: {description}" for name, description in spec.args.items())
    return f"- {spec.name}: {spec.description} Args: {args}"


def format_action(action: object) -> str:
    if action is None:
        return "None"
    return json.dumps(action.__dict__, ensure_ascii=False)


def should_capture_working_note(path: str) -> bool:
    normalized = path.replace("\\", "/")
    name = PurePath(normalized).name.lower()
    if name in IMPORTANT_FILENAMES:
        return True
    stem = PurePath(normalized).stem.lower()
    return any(keyword in stem for keyword in ("requirement", "design", "gameplay", "brief", "spec"))


def capture_working_note(state: AgentState, path: str, content: str) -> None:
    if not should_capture_working_note(path):
        return
    note = compact_note_content(content)
    if not note:
        return
    if path not in state.working_notes and len(state.working_notes) >= MAX_WORKING_NOTES:
        oldest_path = next(iter(state.working_notes))
        del state.working_notes[oldest_path]
    state.working_notes[path] = note


def compact_note_content(content: str) -> str:
    lines = [strip_line_number(line).rstrip() for line in content.splitlines()]
    text = "\n".join(line for line in lines if line.strip())
    if len(text) <= MAX_WORKING_NOTE_CHARS:
        return text
    half = MAX_WORKING_NOTE_CHARS // 2
    return text[:half].rstrip() + "\n... [working note truncated] ...\n" + text[-half:].lstrip()


def strip_line_number(line: str) -> str:
    prefix, separator, rest = line.partition(": ")
    if separator and prefix.isdigit():
        return rest
    return line


def format_working_notes(notes: dict[str, str]) -> str:
    if not notes:
        return ""
    return "\n\n".join(f"Path: {path}\n{content}" for path, content in notes.items())


def format_rolling_task_summary(state: AgentState, older_history: list[object]) -> str:
    if not older_history:
        return ""

    inspected: list[str] = []
    modified: list[str] = []
    verification: list[str] = []
    errors: list[str] = []
    decisions: list[str] = []

    for item in older_history:
        action = getattr(item, "action", None)
        observation = getattr(item, "observation", None)
        if action is None or observation is None:
            continue
        path = action.args.get("path") if isinstance(action.args, dict) else None
        if action.tool in {"list_dir", "read_file", "search"} and isinstance(path, str):
            inspected.append(f"{action.tool}:{path}")
        if action.tool in {"write_file", "append_file", "replace_in_file"} and isinstance(path, str):
            modified.append(f"{action.tool}:{path}")
        if action.tool == "run_shell":
            command = action.args.get("command", "") if isinstance(action.args, dict) else ""
            exit_code = observation.data.get("exit_code")
            verification.append(f"{command} -> {exit_code}")
        if not observation.ok:
            errors.append(f"step {item.step} {observation.tool}:{observation.error_type or 'Error'}")

    if state.target_scope:
        decisions.append(f"当前目标目录锁定为 {state.target_scope}")
    if state.working_notes:
        decisions.append("已保留重要说明文件工作笔记：" + ", ".join(state.working_notes))
    if state.modified_files:
        decisions.append("已修改文件：" + ", ".join(state.modified_files))

    lines = [
        f"已压缩较早的 {len(older_history)} 个步骤，完整细节不再放入 Recent history。",
        "已查看：" + join_limited(unique_keep_order(inspected), "none"),
        "已修改：" + join_limited(unique_keep_order(modified or state.modified_files), "none"),
        "验证记录：" + join_limited(verification, "none"),
        "重要决定：" + join_limited(decisions, "none"),
        "近期错误：" + join_limited(errors[-3:], "none"),
        "下一步建议：基于 Persistent Working Notes 和 Recent history 继续行动，避免重复探索；如已有修改，优先运行验证。",
    ]
    return "\n".join(lines)


def unique_keep_order(values: list[str]) -> list[str]:
    seen = set()
    result = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def join_limited(values: list[str], empty: str, limit: int = 8) -> str:
    if not values:
        return empty
    head = values[:limit]
    suffix = f"，另有 {len(values) - limit} 项" if len(values) > limit else ""
    return "、".join(head) + suffix
