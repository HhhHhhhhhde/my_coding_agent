from pathlib import Path
import json

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


def test_parse_error_uses_taxonomy_and_keeps_parser_detail(tmp_path: Path) -> None:
    seen_messages: list[list[dict[str, str]]] = []

    class CapturingLLM(FakeLLM):
        def complete(self, messages: list[dict[str, str]]) -> str:
            seen_messages.append(messages)
            return super().complete(messages)

    llm = CapturingLLM(
        [
            "bad json",
            '{"thought":"finish","action":{"tool":"finish","args":{"summary":"done","changed_files":[],"verification":"not needed"}}}',
        ]
    )

    result = CodingAgent(llm=llm, workspace=tmp_path, max_steps=3).run("Do something.")

    assert result.success
    assert '"error_type": "ParserError"' in seen_messages[1][1]["content"]
    assert '"parser_error_type": "InvalidJson"' in seen_messages[1][1]["content"]


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


def test_llm_exception_uses_llm_error_taxonomy(tmp_path: Path) -> None:
    class BrokenLLM:
        def complete(self, _messages: list[dict[str, str]]) -> str:
            raise RuntimeError("network down")

    result = CodingAgent(llm=BrokenLLM(), workspace=tmp_path, max_steps=3).run("Do something.")

    assert not result.success
    assert result.termination_reason == "llm_error"

    events = Path(result.trajectory_path).read_text(encoding="utf-8")
    assert '"error_type": "LLMError"' in events
    assert '"original_error_type": "RuntimeError"' in events


def test_failed_verification_gets_retry_hint(tmp_path: Path) -> None:
    seen_messages: list[list[dict[str, str]]] = []

    class CapturingLLM(FakeLLM):
        def complete(self, messages: list[dict[str, str]]) -> str:
            seen_messages.append(messages)
            return super().complete(messages)

    llm = CapturingLLM(
        [
            '{"thought":"run tests","action":{"tool":"run_shell","args":{"command":"python -m pytest missing_test.py","timeout":5}}}',
            '{"thought":"finish","action":{"tool":"finish","args":{"summary":"stopped","changed_files":[],"verification":"failed first"}}}',
        ]
    )

    result = CodingAgent(llm=llm, workspace=tmp_path, max_steps=3).run("Run tests.")

    assert result.success
    assert '"error_type": "VerificationError"' in seen_messages[1][1]["content"]
    assert "Read the failing command output" in seen_messages[1][1]["content"]


def test_shell_file_read_errors_include_retry_hint(tmp_path: Path) -> None:
    seen_messages: list[list[dict[str, str]]] = []

    class CapturingLLM(FakeLLM):
        def complete(self, messages: list[dict[str, str]]) -> str:
            seen_messages.append(messages)
            return super().complete(messages)

    (tmp_path / "sample.py").write_text("value = 1\n", encoding="utf-8")
    llm = CapturingLLM(
        [
            '{"thought":"read with shell","action":{"tool":"run_shell","args":{"command":"Get-Content sample.py"}}}',
            '{"thought":"read properly","action":{"tool":"read_file","args":{"path":"sample.py","start":1,"end":5}}}',
            '{"thought":"finish","action":{"tool":"finish","args":{"summary":"done","changed_files":[],"verification":"not needed"}}}',
        ]
    )

    result = CodingAgent(llm=llm, workspace=tmp_path, max_steps=5).run("Inspect sample.")

    assert result.success
    assert "UseReadFile" in seen_messages[1][1]["content"]
    assert "read_file" in seen_messages[1][1]["content"]


def test_large_write_errors_include_chunk_retry_hint(tmp_path: Path) -> None:
    seen_messages: list[list[dict[str, str]]] = []

    class CapturingLLM(FakeLLM):
        def complete(self, messages: list[dict[str, str]]) -> str:
            seen_messages.append(messages)
            return super().complete(messages)

    lines = ",".join(f'"line {index}"' for index in range(101))
    llm = CapturingLLM(
        [
            '{"thought":"write too much","action":{"tool":"write_file","args":{"path":"large.py","content_lines":['
            + lines
            + "]}}}",
            '{"thought":"finish","action":{"tool":"finish","args":{"summary":"stopped","changed_files":[],"verification":"not needed"}}}',
        ]
    )

    result = CodingAgent(llm=llm, workspace=tmp_path, max_steps=3).run("Write a large file.")

    assert result.success
    assert "WriteChunkTooLarge" in seen_messages[1][1]["content"]
    assert "at most 100 lines" in seen_messages[1][1]["content"]


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


def test_session_context_is_visible_to_llm(tmp_path: Path) -> None:
    seen_messages: list[list[dict[str, str]]] = []

    class CapturingLLM(FakeLLM):
        def complete(self, messages: list[dict[str, str]]) -> str:
            seen_messages.append(messages)
            return super().complete(messages)

    llm = CapturingLLM(
        [
            '{"thought":"finish","action":{"tool":"finish","args":{"summary":"done","changed_files":[],"verification":"not needed"}}}',
        ]
    )

    result = CodingAgent(llm=llm, workspace=tmp_path, max_steps=3).run(
        "Continue previous task.", session_context="上一轮修复了 calculator.py。"
    )

    assert result.success
    assert "Recent Session Context" in seen_messages[0][1]["content"]
    assert "上一轮修复了 calculator.py" in seen_messages[0][1]["content"]

    first_event = json.loads(Path(result.trajectory_path).read_text(encoding="utf-8").splitlines()[0])
    assert first_event["type"] == "start"
    assert first_event["has_session_context"] is True
    assert "上一轮修复了 calculator.py" in first_event["session_context_preview"]

    first_step = json.loads(Path(result.trajectory_path).read_text(encoding="utf-8").splitlines()[1])
    assert first_step["llm_duration"] >= 0
    assert first_step["prompt_chars"] > 0


def test_active_skills_are_visible_to_llm_and_logged(tmp_path: Path) -> None:
    seen_messages: list[list[dict[str, str]]] = []

    class CapturingLLM(FakeLLM):
        def complete(self, messages: list[dict[str, str]]) -> str:
            seen_messages.append(messages)
            return super().complete(messages)

    llm = CapturingLLM(
        [
            '{"thought":"finish","action":{"tool":"finish","args":{"summary":"done","changed_files":[],"verification":"not needed"}}}',
        ]
    )

    result = CodingAgent(llm=llm, workspace=tmp_path, max_steps=3).run(
        "Fix tests.",
        skill_context="Active Skills:\n\n## python-testing\nRead failing tests first.",
        active_skills=["python-testing"],
    )

    assert result.success
    assert "Active Skills" in seen_messages[0][1]["content"]
    assert "Read failing tests first" in seen_messages[0][1]["content"]

    first_event = json.loads(Path(result.trajectory_path).read_text(encoding="utf-8").splitlines()[0])
    assert first_event["active_skills"] == ["python-testing"]


def test_important_requirement_file_stays_in_working_notes(tmp_path: Path) -> None:
    seen_messages: list[list[dict[str, str]]] = []

    class CapturingLLM(FakeLLM):
        def complete(self, messages: list[dict[str, str]]) -> str:
            seen_messages.append(messages)
            return super().complete(messages)

    (tmp_path / "GAMEPLAY.md").write_text("# Gameplay\nJump over stones.\nSlide under gates.\n", encoding="utf-8")
    responses = [
        '{"thought":"read rules","action":{"tool":"read_file","args":{"path":"GAMEPLAY.md","start":1,"end":20}}}',
    ]
    responses.extend(
        f'{{"thought":"write chunk","action":{{"tool":"write_file","args":{{"path":"chunk_{index}.txt","content_lines":["line {index}"]}}}}}}'
        for index in range(10)
    )
    responses.append(
        '{"thought":"finish","action":{"tool":"finish","args":{"summary":"done","changed_files":[],"verification":"not needed"}}}'
    )
    llm = CapturingLLM(responses)

    result = CodingAgent(llm=llm, workspace=tmp_path, max_steps=12).run("Complete this game.")

    assert result.success
    final_prompt = seen_messages[-1][1]["content"]
    assert "Persistent Working Notes" in final_prompt
    assert "Path: GAMEPLAY.md" in final_prompt
    assert "Jump over stones" in final_prompt
    assert "Step 1\nAction" not in final_prompt


def test_older_history_is_compressed_into_rolling_summary(tmp_path: Path) -> None:
    seen_messages: list[list[dict[str, str]]] = []

    class CapturingLLM(FakeLLM):
        def complete(self, messages: list[dict[str, str]]) -> str:
            seen_messages.append(messages)
            return super().complete(messages)

    responses = []
    for index in range(11):
        responses.append(
            f'{{"thought":"write chunk","action":{{"tool":"write_file","args":{{"path":"file_{index}.txt","content_lines":["line {index}"]}}}}}}'
        )
    responses.append(
        '{"thought":"finish","action":{"tool":"finish","args":{"summary":"done","changed_files":[],"verification":"not needed"}}}'
    )
    llm = CapturingLLM(responses)

    result = CodingAgent(llm=llm, workspace=tmp_path, max_steps=12).run("Write several files.")

    assert result.success
    final_prompt = seen_messages[-1][1]["content"]
    assert "Rolling Task Summary" in final_prompt
    assert "已压缩较早的 1 个步骤" in final_prompt
    assert "write_file:file_0.txt" in final_prompt
    assert "Step 1\nAction" not in final_prompt


def test_target_scope_blocks_unrelated_exploration_after_gameplay_is_found(tmp_path: Path) -> None:
    seen_messages: list[list[dict[str, str]]] = []

    class CapturingLLM(FakeLLM):
        def complete(self, messages: list[dict[str, str]]) -> str:
            seen_messages.append(messages)
            return super().complete(messages)

    target_dir = tmp_path / "examples" / "demo_runner_game"
    target_dir.mkdir(parents=True)
    (target_dir / "GAMEPLAY.md").write_text("# Gameplay\nJump and slide.\n", encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'x'\n", encoding="utf-8")
    llm = CapturingLLM(
        [
            '{"thought":"find docs","action":{"tool":"list_dir","args":{"path":"examples/demo_runner_game"}}}',
            '{"thought":"inspect project","action":{"tool":"read_file","args":{"path":"pyproject.toml","start":1,"end":20}}}',
            '{"thought":"write game","action":{"tool":"write_file","args":{"path":"examples/demo_runner_game/runner_game.py","content_lines":["def main():","    return None"]}}}',
            '{"thought":"finish","action":{"tool":"finish","args":{"summary":"done","changed_files":["examples/demo_runner_game/runner_game.py"],"verification":"not needed"}}}',
        ]
    )

    result = CodingAgent(llm=llm, workspace=tmp_path, max_steps=5).run("请阅读examples下的跑酷游戏文档，并实现这个游戏")

    assert result.success
    assert (target_dir / "runner_game.py").exists()
    assert "TargetScopeViolation" in seen_messages[2][1]["content"]
    assert '"target_scope": "examples/demo_runner_game"' in seen_messages[2][1]["content"]


def test_prompt_tells_model_to_implement_from_design_docs(tmp_path: Path) -> None:
    seen_messages: list[list[dict[str, str]]] = []

    class CapturingLLM(FakeLLM):
        def complete(self, messages: list[dict[str, str]]) -> str:
            seen_messages.append(messages)
            return super().complete(messages)

    llm = CapturingLLM(
        [
            '{"thought":"finish","action":{"tool":"finish","args":{"summary":"done","changed_files":[],"verification":"not needed"}}}',
        ]
    )

    result = CodingAgent(llm=llm, workspace=tmp_path, max_steps=1).run("请根据 GAMEPLAY.md 实现游戏")

    assert result.success
    system_prompt = seen_messages[0][0]["content"]
    assert "GAMEPLAY" in system_prompt
    assert "enough to start implementation" in system_prompt
    assert "compact runnable MVP" in system_prompt


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
