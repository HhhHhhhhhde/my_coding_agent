from __future__ import annotations

from openai import OpenAI

from .config import Config


class LLMClient:
    def __init__(self, config: Config, temperature: float = 0.0) -> None:
        self.model = config.model
        self.temperature = temperature
        self.client = OpenAI(api_key=config.api_key, base_url=config.base_url)

    def complete(self, messages: list[dict[str, str]]) -> str:
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=self.temperature,
            )
        except Exception as exc:
            raise RuntimeError(f"LLM call failed: {exc}") from exc

        content = response.choices[0].message.content
        if content is None:
            raise RuntimeError("LLM call returned no text content.")
        return content
