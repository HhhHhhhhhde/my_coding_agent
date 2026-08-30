from mini_agent.protocol import AgentResult, VerificationRecord
from mini_agent.session import SessionState, build_session_turn, format_turn_summary, redact_sensitive


def test_session_state_keeps_recent_turns() -> None:
    session = SessionState(max_turns=2)

    session.add_turn(make_turn("task one"))
    session.add_turn(make_turn("task two"))
    session.add_turn(make_turn("task three"))

    assert [turn.task for turn in session.turns] == ["task two", "task three"]
    assert "task two" in session.to_prompt_context()
    assert "task one" not in session.to_prompt_context()


def test_session_state_keeps_five_turns_by_default() -> None:
    session = SessionState()

    for index in range(6):
        session.add_turn(make_turn(f"task {index}"))

    assert [turn.task for turn in session.turns] == ["task 1", "task 2", "task 3", "task 4", "task 5"]


def test_empty_session_context_is_empty() -> None:
    session = SessionState()

    assert session.to_prompt_context() == ""


def test_session_context_redacts_secret_like_values() -> None:
    session = SessionState()
    result = AgentResult(
        success=True,
        summary="Used OPENAI_API_KEY=secret-value and sk-abcdef1234567890.",
        termination_reason="finished",
        modified_files=[],
        verification_records=[],
        trajectory_path="trajectories/run.jsonl",
    )

    session.add_turn(build_session_turn("check key", "plan", ".", result))

    context = session.to_prompt_context()
    assert "secret-value" not in context
    assert "sk-abcdef1234567890" not in context
    assert "[REDACTED]" in context


def test_redact_sensitive_masks_common_secret_patterns() -> None:
    assert redact_sensitive("TOKEN=abc123") == "[REDACTED]"
    assert redact_sensitive("value sk-abcdefghijklmnop") == "value [REDACTED]"


def test_format_turn_summary_is_chinese_paragraph() -> None:
    result = AgentResult(
        success=True,
        summary="原始 finish summary",
        termination_reason="finished",
        modified_files=[],
        verification_records=[],
        trajectory_path="trajectories/run.jsonl",
        turn_summary="这轮任务已经自然地总结完成。",
    )
    turn = build_session_turn("修复 calculator", "build", ".", result)

    text = format_turn_summary(turn)

    assert text == "这轮任务已经自然地总结完成。"
    assert format_turn_summary(turn, index=2) == "第 2 轮：这轮任务已经自然地总结完成。"


def test_build_session_turn_converts_agent_result() -> None:
    result = AgentResult(
        success=True,
        summary="done",
        termination_reason="finished",
        modified_files=["calculator.py"],
        verification_records=[VerificationRecord("pytest -q", 0, True)],
        trajectory_path="trajectories/run.jsonl",
        output_path=None,
    )

    turn = build_session_turn("fix", "build", ".", result)

    assert turn.task == "fix"
    assert turn.summary == "done"
    assert turn.modified_files == ["calculator.py"]
    assert turn.verification == ["pytest -q -> passed (0)"]


def make_turn(task: str):
    result = AgentResult(
        success=True,
        summary="done",
        termination_reason="finished",
        modified_files=[],
        verification_records=[],
        trajectory_path="trajectories/run.jsonl",
    )
    return build_session_turn(task, "build", ".", result)
