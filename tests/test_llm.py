from mini_agent.config import Config
from mini_agent.llm import EmptyLLMResponse, LLMClient


class FakeMessage:
    content = '{"thought":"done","action":{"tool":"finish","args":{}}}'


class FakeChoice:
    message = FakeMessage()


class FakeResponse:
    choices = [FakeChoice()]


class FakeCompletions:
    def __init__(self) -> None:
        self.kwargs = {}

    def create(self, **kwargs):
        self.kwargs = kwargs
        return FakeResponse()


class FakeChat:
    def __init__(self) -> None:
        self.completions = FakeCompletions()


class FakeOpenAI:
    last_instance = None

    def __init__(self, **kwargs) -> None:
        self.kwargs = kwargs
        self.chat = FakeChat()
        FakeOpenAI.last_instance = self


def test_llm_client_limits_completion_tokens(monkeypatch) -> None:
    monkeypatch.setattr("mini_agent.llm.OpenAI", FakeOpenAI)
    config = Config(
        api_key="key",
        base_url="https://example.test/v1",
        model="test-model",
        llm_timeout_seconds=12.0,
        llm_max_tokens=1800,
        llm_empty_response_retries=2,
    )

    client = LLMClient(config)
    result = client.complete([{"role": "user", "content": "hi"}])

    assert result.startswith('{"thought"')
    assert FakeOpenAI.last_instance.kwargs["timeout"] == 12.0
    assert FakeOpenAI.last_instance.chat.completions.kwargs["max_tokens"] == 1800


class SequenceCompletions:
    def __init__(self, contents: list[str]) -> None:
        self.contents = contents
        self.calls = 0
        self.kwargs_by_call = []

    def create(self, **kwargs):
        self.kwargs_by_call.append(kwargs)
        content = self.contents[self.calls]
        self.calls += 1
        message = type("Message", (), {"content": content})()
        choice = type("Choice", (), {"message": message, "finish_reason": "stop"})()
        return type("Response", (), {"choices": [choice], "usage": None, "id": "resp_test"})()


class SequenceOpenAI:
    contents: list[str] = []
    last_instance = None

    def __init__(self, **_kwargs) -> None:
        self.chat = type("Chat", (), {"completions": SequenceCompletions(self.contents)})()
        SequenceOpenAI.last_instance = self


def make_config(empty_response_retries: int) -> Config:
    return Config(
        api_key="key",
        base_url=None,
        model="test-model",
        llm_timeout_seconds=12.0,
        llm_max_tokens=1800,
        llm_empty_response_retries=empty_response_retries,
    )


def test_llm_client_retries_empty_content(monkeypatch) -> None:
    monkeypatch.setattr("mini_agent.llm.OpenAI", SequenceOpenAI)
    monkeypatch.setattr("mini_agent.llm.time.sleep", lambda _seconds: None)
    SequenceOpenAI.contents = ["", "", '{"thought":"ok","action":{"tool":"finish","args":{}}}']

    client = LLMClient(make_config(empty_response_retries=2))
    result = client.complete([{"role": "user", "content": "hi"}])

    assert '"thought":"ok"' in result
    completions = SequenceOpenAI.last_instance.chat.completions
    assert completions.calls == 3
    assert completions.kwargs_by_call[0]["max_tokens"] == 1800
    assert completions.kwargs_by_call[1]["max_tokens"] == 4096
    assert completions.kwargs_by_call[2]["max_tokens"] == 5400
    assert len(completions.kwargs_by_call[0]["messages"]) == 1
    assert len(completions.kwargs_by_call[1]["messages"]) == 2
    assert "one short JSON action" in completions.kwargs_by_call[1]["messages"][-1]["content"]


def test_llm_client_raises_diagnostic_error_after_empty_retries(monkeypatch) -> None:
    monkeypatch.setattr("mini_agent.llm.OpenAI", SequenceOpenAI)
    monkeypatch.setattr("mini_agent.llm.time.sleep", lambda _seconds: None)
    SequenceOpenAI.contents = ["", ""]

    client = LLMClient(make_config(empty_response_retries=1))

    try:
        client.complete([{"role": "user", "content": "hi"}])
    except EmptyLLMResponse as exc:
        message = str(exc)
    else:
        raise AssertionError("Expected EmptyLLMResponse")

    assert "after 2 attempt" in message
    assert "finish_reason" in message
    assert "request_max_tokens" in message
