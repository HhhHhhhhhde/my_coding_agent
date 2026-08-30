from mini_agent.config import load_config, parse_float_env, parse_int_env


def test_load_config_defaults_to_5000_max_tokens(monkeypatch, tmp_path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("OPENAI_API_KEY", "key")
    monkeypatch.delenv("AGENT_LLM_MAX_TOKENS", raising=False)

    config = load_config()

    assert config.llm_max_tokens == 5000


def test_parse_float_env_uses_default_for_missing_or_invalid_values(monkeypatch) -> None:
    monkeypatch.delenv("AGENT_LLM_TIMEOUT_SECONDS", raising=False)
    assert parse_float_env("AGENT_LLM_TIMEOUT_SECONDS", 60.0) == 60.0

    monkeypatch.setenv("AGENT_LLM_TIMEOUT_SECONDS", "bad")
    assert parse_float_env("AGENT_LLM_TIMEOUT_SECONDS", 60.0) == 60.0

    monkeypatch.setenv("AGENT_LLM_TIMEOUT_SECONDS", "0")
    assert parse_float_env("AGENT_LLM_TIMEOUT_SECONDS", 60.0) == 60.0


def test_parse_float_env_accepts_positive_numbers(monkeypatch) -> None:
    monkeypatch.setenv("AGENT_LLM_TIMEOUT_SECONDS", "12.5")

    assert parse_float_env("AGENT_LLM_TIMEOUT_SECONDS", 60.0) == 12.5


def test_parse_int_env_uses_default_for_missing_or_invalid_values(monkeypatch) -> None:
    monkeypatch.delenv("AGENT_LLM_MAX_TOKENS", raising=False)
    assert parse_int_env("AGENT_LLM_MAX_TOKENS", 5000) == 5000

    monkeypatch.setenv("AGENT_LLM_MAX_TOKENS", "bad")
    assert parse_int_env("AGENT_LLM_MAX_TOKENS", 5000) == 5000

    monkeypatch.setenv("AGENT_LLM_MAX_TOKENS", "0")
    assert parse_int_env("AGENT_LLM_MAX_TOKENS", 5000) == 5000


def test_parse_int_env_accepts_positive_numbers(monkeypatch) -> None:
    monkeypatch.setenv("AGENT_LLM_MAX_TOKENS", "1800")

    assert parse_int_env("AGENT_LLM_MAX_TOKENS", 5000) == 1800


def test_empty_response_retry_count_uses_same_int_parser(monkeypatch) -> None:
    monkeypatch.setenv("AGENT_LLM_EMPTY_RESPONSE_RETRIES", "3")

    assert parse_int_env("AGENT_LLM_EMPTY_RESPONSE_RETRIES", 2) == 3
