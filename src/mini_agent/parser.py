from __future__ import annotations

import json
import re

from .protocol import Action, ParseResult


JSON_BLOCK_RE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)


def parse_action(raw_response: str) -> ParseResult:
    text = raw_response.strip()
    if not text:
        return ParseResult(False, error_type="EmptyResponse", message="Model returned an empty response.")

    match = JSON_BLOCK_RE.fullmatch(text)
    if match:
        text = match.group(1).strip()

    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        repaired = repair_trailing_delimiters(text)
        if repaired is None:
            return ParseResult(False, error_type="InvalidJson", message=f"Invalid JSON: {exc.msg}")
        try:
            payload = json.loads(repaired)
        except json.JSONDecodeError:
            return ParseResult(False, error_type="InvalidJson", message=f"Invalid JSON: {exc.msg}")

    if not isinstance(payload, dict):
        return ParseResult(False, error_type="InvalidShape", message="Top-level response must be a JSON object.")

    thought = payload.get("thought", "")
    if not isinstance(thought, str) or not thought.strip():
        return ParseResult(False, error_type="InvalidThought", message="Field 'thought' must be a non-empty string.")

    action = payload.get("action")
    if not isinstance(action, dict):
        return ParseResult(False, error_type="InvalidAction", message="Field 'action' must be an object.")

    tool = action.get("tool")
    if not isinstance(tool, str) or not tool.strip():
        return ParseResult(False, error_type="InvalidTool", message="Field 'action.tool' must be a non-empty string.")

    args = action.get("args", {})
    if not isinstance(args, dict):
        return ParseResult(False, error_type="InvalidArgs", message="Field 'action.args' must be an object.")

    return ParseResult(True, action=Action(thought=thought.strip(), tool=tool.strip(), args=args))


def repair_trailing_delimiters(text: str) -> str | None:
    """Repair responses that are valid JSON except for missing closing delimiters."""
    if not text.startswith("{"):
        return None

    stack: list[str] = []
    in_string = False
    escaped = False

    for char in text:
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue

        if char == '"':
            in_string = True
        elif char in "{[":
            stack.append("}" if char == "{" else "]")
        elif char in "}]":
            if not stack or stack[-1] != char:
                return None
            stack.pop()

    if in_string or not stack:
        return None

    return text + "".join(reversed(stack))
