from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Config:
    api_key: str
    base_url: str | None
    model: str
    llm_timeout_seconds: float
    llm_max_tokens: int
    llm_empty_response_retries: int


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def load_config(model_override: str | None = None) -> Config:
    load_dotenv(Path(".env"))
    api_key = os.getenv("OPENAI_API_KEY", "")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set. Create a local .env or set the environment variable.")
    return Config(
        api_key=api_key,
        base_url=os.getenv("OPENAI_BASE_URL") or None,
        model=model_override or os.getenv("AGENT_MODEL", "gpt-4.1-mini"),
        llm_timeout_seconds=parse_float_env("AGENT_LLM_TIMEOUT_SECONDS", 60.0),
        llm_max_tokens=parse_int_env("AGENT_LLM_MAX_TOKENS", 5000),
        llm_empty_response_retries=parse_int_env("AGENT_LLM_EMPTY_RESPONSE_RETRIES", 2),
    )


def parse_float_env(name: str, default: float) -> float:
    value = os.getenv(name)
    if not value:
        return default
    try:
        parsed = float(value)
    except ValueError:
        return default
    return parsed if parsed > 0 else default


def parse_int_env(name: str, default: int) -> int:
    value = os.getenv(name)
    if not value:
        return default
    try:
        parsed = int(value)
    except ValueError:
        return default
    return parsed if parsed > 0 else default
