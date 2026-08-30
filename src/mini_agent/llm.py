from __future__ import annotations

import json
import time

from openai import OpenAI

from .config import Config


EMPTY_RETRY_NUDGE = (
    "The previous model attempt returned empty message.content after using its output budget. "
    "Now respond with exactly one short JSON action only. Do not draft a full file in this response. "
    "If code must be written, write only a compact 40-80 line first chunk with write_file."
)


class EmptyLLMResponse(RuntimeError):
    pass


class LLMClient:
    def __init__(self, config: Config, temperature: float = 0.0) -> None:
        self.model = config.model
        self.temperature = temperature
        self.timeout = config.llm_timeout_seconds
        self.max_tokens = config.llm_max_tokens
        self.empty_response_retries = config.llm_empty_response_retries
        self.client = OpenAI(api_key=config.api_key, base_url=config.base_url, timeout=self.timeout)

    def complete(self, messages: list[dict[str, str]]) -> str:
        diagnostics: list[dict[str, object]] = []
        attempts = self.empty_response_retries + 1
        for attempt in range(1, attempts + 1):
            max_tokens = max_tokens_for_attempt(self.max_tokens, attempt)
            request_messages = messages_for_attempt(messages, attempt)
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=request_messages,
                    temperature=self.temperature,
                    max_tokens=max_tokens,
                )
            except Exception as exc:
                raise RuntimeError(f"LLM call failed: {exc}") from exc

            content, diagnostic = parse_response_content(response, attempt, max_tokens)
            diagnostics.append(diagnostic)
            if content.strip():
                return content
            if attempt < attempts:
                time.sleep(min(0.2 * attempt, 1.0))

        raise EmptyLLMResponse(
            "LLM returned empty message.content after "
            f"{attempts} attempt(s). Diagnostics: {json.dumps(diagnostics, ensure_ascii=False)}"
        )


def max_tokens_for_attempt(base_max_tokens: int, attempt: int) -> int:
    if attempt <= 1:
        return base_max_tokens
    return min(max(base_max_tokens * attempt, 4096), max(base_max_tokens, 8192))


def messages_for_attempt(messages: list[dict[str, str]], attempt: int) -> list[dict[str, str]]:
    if attempt <= 1:
        return messages
    return [*messages, {"role": "user", "content": EMPTY_RETRY_NUDGE}]


def parse_response_content(response: object, attempt: int, max_tokens: int) -> tuple[str, dict[str, object]]:
    choices = getattr(response, "choices", [])
    choice = choices[0] if choices else None
    message = getattr(choice, "message", None)
    content = getattr(message, "content", "") if message is not None else ""
    diagnostic = {
        "attempt": attempt,
        "request_max_tokens": max_tokens,
        "finish_reason": getattr(choice, "finish_reason", None),
        "content_is_none": content is None,
        "content_length": len(content or ""),
        "message_keys": sorted(message_keys(message)),
        "usage": safe_model_dump(getattr(response, "usage", None)),
        "response_id": getattr(response, "id", None),
    }
    return content or "", diagnostic


def message_keys(message: object) -> set[str]:
    if message is None:
        return set()
    if hasattr(message, "model_dump"):
        dumped = safe_model_dump(message)
        if isinstance(dumped, dict):
            return set(dumped)
    if hasattr(message, "__dict__"):
        return set(vars(message))
    return set()


def safe_model_dump(value: object) -> object:
    if value is None:
        return None
    if hasattr(value, "model_dump"):
        try:
            return value.model_dump()
        except Exception:
            return str(value)
    if hasattr(value, "__dict__"):
        return dict(vars(value))
    return str(value)
