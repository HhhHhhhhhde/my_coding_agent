from pathlib import Path

from mini_agent.agent import CodingAgent


class FakeLLM:
    def __init__(self, responses: list[str]) -> None:
        self.responses = responses
        self.index = 0

    def complete(self, _messages: list[dict[str, str]]) -> str:
        response = self.responses[self.index]
        self.index += 1
        return response


def test_agent_loop_reaches_finish(tmp_path: Path) -> None:
    (tmp_path / "calculator.py").write_text("def add(a, b):\n    return a - b\n", encoding="utf-8")
    llm = FakeLLM(
        [
            '{"thought":"read source","action":{"tool":"read_file","args":{"path":"calculator.py","start":1,"end":5}}}',
            '{"thought":"fix bug","action":{"tool":"replace_in_file","args":{"path":"calculator.py","old":"return a - b","new":"return a + b"}}}',
            '{"thought":"finish","action":{"tool":"finish","args":{"summary":"Fixed add.","changed_files":["calculator.py"],"verification":"not run in unit test"}}}',
        ]
    )

    result = CodingAgent(llm=llm, workspace=tmp_path, max_steps=5).run("Fix add.")

    assert result.success
    assert result.termination_reason == "finished"
    assert result.modified_files == ["calculator.py"]
    assert "return a + b" in (tmp_path / "calculator.py").read_text(encoding="utf-8")
    assert Path(result.trajectory_path).exists()


def test_agent_loop_stops_after_parse_errors(tmp_path: Path) -> None:
    llm = FakeLLM(["bad json", "bad json", "bad json"])

    result = CodingAgent(llm=llm, workspace=tmp_path, max_steps=5).run("Do something.")

    assert not result.success
    assert result.termination_reason == "too_many_errors"


def test_parser_errors_include_retry_hint(tmp_path: Path) -> None:
    seen_messages: list[list[dict[str, str]]] = []

    class CapturingLLM(FakeLLM):
        def complete(self, messages: list[dict[str, str]]) -> str:
            seen_messages.append(messages)
            return super().complete(messages)

    llm = CapturingLLM(
        [
            '{"thought":"bad","action":{"tool":"write_file","args":{"path":"x.py","content_lines":[""""bad""""]}}}',
            '{"thought":"finish","action":{"tool":"finish","args":{"summary":"stopped","changed_files":[],"verification":"not needed"}}}',
        ]
    )

    result = CodingAgent(llm=llm, workspace=tmp_path, max_steps=3).run("Write a file.")

    assert result.success
    assert "content_base64" in seen_messages[1][1]["content"]


def test_plan_mode_does_not_expose_write_tools(tmp_path: Path) -> None:
    llm = FakeLLM(
        [
            '{"thought":"try to edit","action":{"tool":"replace_in_file","args":{"path":"x.py","old":"a","new":"b"}}}',
            '{"thought":"finish with plan","action":{"tool":"finish","args":{"summary":"Need an edit in build mode.","changed_files":[],"verification":"planning only"}}}',
        ]
    )

    result = CodingAgent(llm=llm, workspace=tmp_path, max_steps=5, mode="plan").run("Plan only.")

    assert result.success
    assert result.modified_files == []


def test_inspected_paths_are_visible_to_llm(tmp_path: Path) -> None:
    seen_messages: list[list[dict[str, str]]] = []

    class CapturingLLM(FakeLLM):
        def complete(self, messages: list[dict[str, str]]) -> str:
            seen_messages.append(messages)
            return super().complete(messages)

    (tmp_path / "sample.py").write_text("value = 1\n", encoding="utf-8")
    llm = CapturingLLM(
        [
            '{"thought":"inspect","action":{"tool":"read_file","args":{"path":"sample.py"}}}',
            '{"thought":"finish","action":{"tool":"finish","args":{"summary":"done","changed_files":[],"verification":"not needed"}}}',
        ]
    )

    result = CodingAgent(llm=llm, workspace=tmp_path, max_steps=3).run("Inspect sample.")

    assert result.success
    assert '"inspected_paths": ["sample.py"]' in seen_messages[1][1]["content"]


def test_repeated_inspection_gets_progress_guard_hint(tmp_path: Path) -> None:
    seen_messages: list[list[dict[str, str]]] = []

    class CapturingLLM(FakeLLM):
        def complete(self, messages: list[dict[str, str]]) -> str:
            seen_messages.append(messages)
            return super().complete(messages)

    (tmp_path / "sample.py").write_text("value = 1\n", encoding="utf-8")
    llm = CapturingLLM(
        [
            '{"thought":"read once","action":{"tool":"read_file","args":{"path":"sample.py"}}}',
            '{"thought":"read twice","action":{"tool":"read_file","args":{"path":"sample.py"}}}',
            '{"thought":"read again","action":{"tool":"read_file","args":{"path":"sample.py"}}}',
            '{"thought":"finish","action":{"tool":"finish","args":{"summary":"done","changed_files":[],"verification":"not needed"}}}',
        ]
    )

    result = CodingAgent(llm=llm, workspace=tmp_path, max_steps=5).run("Inspect without looping.")

    assert result.success
    assert "RepeatedInspection" in seen_messages[3][1]["content"]


def test_exploration_budget_pushes_model_to_act(tmp_path: Path) -> None:
    seen_messages: list[list[dict[str, str]]] = []

    class CapturingLLM(FakeLLM):
        def complete(self, messages: list[dict[str, str]]) -> str:
            seen_messages.append(messages)
            return super().complete(messages)

    for index in range(8):
        (tmp_path / f"{index}.py").write_text(f"value = {index}\n", encoding="utf-8")
    responses = [
        f'{{"thought":"read","action":{{"tool":"read_file","args":{{"path":"{index}.py"}}}}}}'
        for index in range(7)
    ]
    responses.append(
        '{"thought":"finish","action":{"tool":"finish","args":{"summary":"acted","changed_files":[],"verification":"not needed"}}}'
    )
    llm = CapturingLLM(responses)

    result = CodingAgent(llm=llm, workspace=tmp_path, max_steps=10).run("Stop over-exploring.")

    assert result.success
    assert "ExplorationBudgetExceeded" in seen_messages[7][1]["content"]
