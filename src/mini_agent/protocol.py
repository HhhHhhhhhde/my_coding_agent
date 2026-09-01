from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Action:
    thought: str
    tool: str
    args: dict[str, Any]


@dataclass(frozen=True)
class ParseResult:
    ok: bool
    action: Action | None = None
    error_type: str | None = None
    message: str | None = None


@dataclass
class Observation:
    ok: bool
    tool: str
    content: str = ""
    error_type: str | None = None
    message: str | None = None
    truncated: bool = False
    needs_confirmation: bool = False
    data: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "ok": self.ok,
            "tool": self.tool,
            "content": self.content,
            "truncated": self.truncated,
        }
        if self.error_type:
            result["error_type"] = self.error_type
        if self.message:
            result["message"] = self.message
        if self.needs_confirmation:
            result["needs_confirmation"] = True
        if self.data:
            result["data"] = self.data
        return result


@dataclass
class HistoryItem:
    step: int
    raw_model_response: str
    action: Action | None
    observation: Observation


@dataclass
class VerificationRecord:
    command: str
    exit_code: int
    passed: bool


@dataclass
class AgentState:
    user_task: str
    workspace: str
    mode: str
    max_steps: int
    session_context: str = ""
    skill_context: str = ""
    active_skills: list[str] = field(default_factory=list)
    target_scope: str = ""
    target_scope_reason: str = ""
    working_notes: dict[str, str] = field(default_factory=dict)
    history: list[HistoryItem] = field(default_factory=list)
    modified_files: list[str] = field(default_factory=list)
    inspected_paths: list[str] = field(default_factory=list)
    verification_records: list[VerificationRecord] = field(default_factory=list)
    exploration_streak: int = 0
    consecutive_errors: int = 0
    finished: bool = False
    final_summary: str = ""
    termination_reason: str = ""


@dataclass(frozen=True)
class AgentResult:
    success: bool
    summary: str
    termination_reason: str
    modified_files: list[str]
    verification_records: list[VerificationRecord]
    trajectory_path: str
    output_path: str | None = None
    turn_summary: str = ""
