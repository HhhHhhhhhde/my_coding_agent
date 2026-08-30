from pathlib import Path

from mini_agent.protocol import AgentResult, VerificationRecord
from mini_agent.turn_summary import (
    build_turn_summary_messages,
    fallback_turn_summary,
    generate_turn_summary,
    normalize_turn_summary,
)


class FakeSummaryLLM:
    def __init__(self, response: str) -> None:
        self.response = response
        self.messages: list[list[dict[str, str]]] = []

    def complete(self, messages: list[dict[str, str]]) -> str:
        self.messages.append(messages)
        return self.response


class FailingSummaryLLM:
    def complete(self, _messages: list[dict[str, str]]) -> str:
        raise RuntimeError("summary failed")


def test_generate_turn_summary_uses_llm_output_as_one_paragraph() -> None:
    llm = FakeSummaryLLM("- 已读取文件\n- 已完成修复")
    result = make_result()

    summary = generate_turn_summary(llm, "修复测试", "build", Path("."), result)

    assert summary == "已读取文件 已完成修复"
    assert "Output exactly one continuous paragraph" in llm.messages[0][0]["content"]
    assert "Use first person" in llm.messages[0][0]["content"]
    assert "Do not say" in llm.messages[0][0]["content"]


def test_generate_turn_summary_falls_back_when_llm_fails() -> None:
    result = make_result()

    summary = generate_turn_summary(FailingSummaryLLM(), "修复测试", "build", Path("."), result)

    assert summary.startswith("我刚才在 build 模式下处理了")
    assert "pytest -q -> passed (0)" in summary


def test_build_turn_summary_messages_include_key_paths() -> None:
    result = make_result()

    messages = build_turn_summary_messages("修复测试", "build", Path("workspace"), result)

    assert "calculator.py" in messages[1]["content"]
    assert "trajectories/run.jsonl" in messages[1]["content"]


def test_normalize_turn_summary_removes_list_shape() -> None:
    assert normalize_turn_summary("1. 读取代码\n2. 完成修复") == "读取代码 完成修复"


def test_fallback_turn_summary_mentions_plan_output() -> None:
    result = make_result(output_path="plans/plan.md")

    summary = fallback_turn_summary("规划", "plan", Path("."), result)

    assert "计划或产物已保存到 plans/plan.md" in summary


def make_result(output_path: str | None = None) -> AgentResult:
    return AgentResult(
        success=True,
        summary="Fixed add.",
        termination_reason="finished",
        modified_files=["calculator.py"],
        verification_records=[VerificationRecord("pytest -q", 0, True)],
        trajectory_path="trajectories/run.jsonl",
        output_path=output_path,
    )
