from __future__ import annotations

from dataclasses import dataclass
import re

from .protocol import AgentResult


SECRET_PATTERNS = [
    re.compile(r"(?i)(api[_-]?key|token|secret|password)\s*=\s*[^\s;]+"),
    re.compile(r"sk-[A-Za-z0-9_-]{12,}"),
]


@dataclass(frozen=True)
class SessionTurn:
    task: str
    mode: str
    workspace: str
    success: bool
    summary: str
    modified_files: list[str]
    verification: list[str]
    trajectory_path: str
    output_path: str | None = None


class SessionState:
    def __init__(self, max_turns: int = 5) -> None:
        self.max_turns = max_turns
        self.turns: list[SessionTurn] = []

    def add_turn(self, turn: SessionTurn) -> None:
        self.turns.append(turn)
        if len(self.turns) > self.max_turns:
            self.turns = self.turns[-self.max_turns :]

    def clear(self) -> None:
        self.turns.clear()

    def last_turn(self) -> SessionTurn | None:
        if not self.turns:
            return None
        return self.turns[-1]

    def to_prompt_context(self) -> str:
        if not self.turns:
            return ""

        lines = []
        for index, turn in enumerate(self.turns, start=1):
            status = "success" if turn.success else "stopped"
            modified = ", ".join(turn.modified_files) if turn.modified_files else "none"
            verification = "; ".join(turn.verification) if turn.verification else "none"
            output = turn.output_path or "none"
            lines.append(
                "Turn "
                f"{index}: task={redact_sensitive(shorten(turn.task, 160))}; "
                f"mode={turn.mode}; workspace={redact_sensitive(turn.workspace)}; "
                f"status={status}; modified={redact_sensitive(modified)}; verification={redact_sensitive(verification)}; "
                f"output_path={redact_sensitive(output)}; trajectory={redact_sensitive(turn.trajectory_path)}; "
                f"summary={redact_sensitive(shorten(turn.summary, 240))}"
            )
        return "\n".join(lines)

    def history_text(self) -> str:
        if not self.turns:
            return "当前会话还没有完成过任务。"

        parts = []
        for index, turn in enumerate(self.turns, start=1):
            parts.append(format_turn_summary(turn, index=index))
        return "\n".join(parts)


def build_session_turn(task: str, mode: str, workspace: str, result: AgentResult) -> SessionTurn:
    verification = [
        f"{record.command} -> {'passed' if record.passed else 'failed'} ({record.exit_code})"
        for record in result.verification_records
    ]
    return SessionTurn(
        task=task,
        mode=mode,
        workspace=workspace,
        success=result.success,
        summary=result.turn_summary or result.summary,
        modified_files=list(result.modified_files),
        verification=verification,
        trajectory_path=result.trajectory_path,
        output_path=result.output_path,
    )


def format_turn_summary(turn: SessionTurn, index: int | None = None) -> str:
    summary = turn.summary or "这轮任务没有生成总结。"
    if index is None:
        return summary
    return f"第 {index} 轮：{summary}"


def shorten(text: str, limit: int) -> str:
    normalized = " ".join(text.split())
    if len(normalized) <= limit:
        return normalized
    return normalized[: limit - 3] + "..."


def redact_sensitive(text: str) -> str:
    redacted = text
    for pattern in SECRET_PATTERNS:
        redacted = pattern.sub("[REDACTED]", redacted)
    return redacted
