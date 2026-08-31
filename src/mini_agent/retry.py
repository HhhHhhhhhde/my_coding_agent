from __future__ import annotations

from .protocol import Action, Observation


def add_retry_hint(observation: Observation, action: Action | None = None) -> Observation:
    hint = retry_hint_for(observation, action)
    if not hint:
        return observation
    observation.data["retryable"] = True
    observation.data["retry_hint"] = hint
    if not observation.content:
        observation.content = hint
    return observation


def retry_hint_for(observation: Observation, action: Action | None = None) -> str:
    if observation.needs_confirmation:
        return "Wait for user confirmation or choose a lower-risk alternative. Do not self-confirm in JSON."
    parser_error_type = observation.data.get("parser_error_type")
    if observation.tool == "parser" and parser_error_type == "InvalidJson":
        return (
            "Retry with exactly one valid JSON object. If the previous response was long or truncated, write a "
            "smaller 40-80 line chunk only. If you were writing code, avoid raw quotes/docstrings inside JSON "
            "strings; use content_lines for simple lines or content_base64 as one single-line UTF-8 base64 string."
        )
    if observation.tool == "parser":
        return "Retry using the required shape: {\"thought\":\"...\",\"action\":{\"tool\":\"name\",\"args\":{}}}."
    if observation.error_type == "ReplacementNotUnique":
        return "Retry by reading the file and choosing a smaller unique old string, or use write_file for the whole file."
    if observation.error_type == "UnknownTool":
        return "Retry with one of the available tool names shown in the prompt."
    if observation.error_type == "TargetScopeViolation":
        scope = observation.data.get("target_scope", "the target scope")
        return f"Retry with a path inside {scope!r}. Do not inspect unrelated directories; use Persistent Working Notes and write the target files."
    if observation.tool == "run_shell" and observation.error_type == "UseReadFile":
        return "Retry with read_file using the same path and a focused line range. Use run_shell only for tests, builds, and checks."
    if observation.error_type == "WriteChunkTooLarge":
        return (
            "Split the file into chunks of at most 100 lines. Use write_file for the first chunk, then append_file "
            "for later chunks, and keep each action small."
        )
    if observation.error_type == "PermissionError":
        return "Retry with an allowed path inside the workspace and avoid sensitive files or blocked shell commands."
    if observation.tool == "run_shell" and observation.error_type == "VerificationError":
        return "Read the failing command output and relevant source or tests, then make a focused fix before running verification again."
    if action and action.tool in {"write_file", "append_file"}:
        return f"Retry {action.tool} with either content, content_lines, or content_base64."
    return ""
