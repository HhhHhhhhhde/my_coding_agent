from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Config:
    api_key: str
    base_url: str | None
    model: str


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
    )
