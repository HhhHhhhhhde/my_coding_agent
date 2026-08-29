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
    if observation.tool == "parser" and observation.error_type == "InvalidJson":
        return (
            "Retry with exactly one valid JSON object. If you were writing code, avoid raw quotes/docstrings "
            "inside JSON strings; use write_file with content_base64 as one single-line UTF-8 base64 string."
        )
    if observation.tool == "parser":
        return "Retry using the required shape: {\"thought\":\"...\",\"action\":{\"tool\":\"name\",\"args\":{}}}."
    if observation.error_type == "ReplacementNotUnique":
        return "Retry by reading the file and choosing a smaller unique old string, or use write_file for the whole file."
    if observation.error_type == "UnknownTool":
        return "Retry with one of the available tool names shown in the prompt."
    if action and action.tool == "write_file":
        return "Retry write_file with either content, content_lines, or content_base64."
    return ""
