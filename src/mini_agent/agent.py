from __future__ import annotations

from pathlib import Path
import time
from typing import Callable

from .context import build_messages, capture_working_note
from .logger import TrajectoryLogger
from .parser import parse_action
from .progress import apply_progress_guard
from .protocol import Action, AgentResult, AgentState, HistoryItem, Observation
from .retry import add_retry_hint
from .target_scope import apply_target_scope_guard, infer_initial_target_scope, update_target_scope_from_observation
from .tools import ToolContext, build_default_registry


MAX_CONSECUTIVE_ERRORS = 3
StepCallback = Callable[[int, Action | None, Observation], None]
ThinkingCallback = Callable[[int], None]


class CodingAgent:
    def __init__(
        self,
        llm: object,
        workspace: Path,
        max_steps: int = 20,
        mode: str = "build",
        on_step: StepCallback | None = None,
        on_thinking: ThinkingCallback | None = None,
    ) -> None:
        self.llm = llm
        self.workspace = workspace.resolve()
        self.max_steps = max_steps
        self.mode = mode
        self.on_step = on_step
        self.on_thinking = on_thinking

    def run(self, user_task: str, session_context: str = "") -> AgentResult:
        target_scope, target_scope_reason = infer_initial_target_scope(user_task, self.workspace)
        state = AgentState(
            user_task=user_task,
            workspace=str(self.workspace),
            mode=self.mode,
            max_steps=self.max_steps,
            session_context=session_context,
            target_scope=target_scope,
            target_scope_reason=target_scope_reason,
        )
        logger = TrajectoryLogger(self.workspace)
        logger.record_start(
            task=user_task,
            workspace=str(self.workspace),
            mode=self.mode,
            max_steps=self.max_steps,
            has_session_context=bool(session_context.strip()),
            session_context=session_context,
        )
        tool_context = ToolContext(
            workspace=self.workspace,
            modified_files=state.modified_files,
            inspected_paths=state.inspected_paths,
            verification_records=state.verification_records,
        )
        registry = build_default_registry(tool_context, mode=self.mode)

        for step in range(1, self.max_steps + 1):
            llm_duration = 0.0
            prompt_chars = 0
            try:
                if self.on_thinking:
                    self.on_thinking(step)
                llm_started_at = time.monotonic()
                messages = build_messages(state, registry.specs())
                prompt_chars = sum(len(message["content"]) for message in messages)
                raw_response = self.llm.complete(messages)
                llm_duration = time.monotonic() - llm_started_at
            except Exception as exc:
                llm_duration = time.monotonic() - llm_started_at if "llm_started_at" in locals() else 0.0
                observation = Observation(False, "llm", error_type=type(exc).__name__, message=str(exc))
                logger.record_step(
                    step,
                    "",
                    None,
                    observation,
                    extra={"llm_duration": llm_duration, "prompt_chars": prompt_chars},
                )
                state.termination_reason = "llm_error"
                state.final_summary = str(exc)
                break

            parsed = parse_action(raw_response)
            if not parsed.ok or parsed.action is None:
                observation = Observation(
                    False,
                    "parser",
                    error_type=parsed.error_type or "ParseError",
                    message=parsed.message or "Could not parse model response.",
                )
                observation = add_retry_hint(observation)
                action = None
            else:
                action = parsed.action
                observation = apply_target_scope_guard(state, action)
                if observation is None:
                    observation = registry.execute(action)
                if observation.ok:
                    observation = apply_progress_guard(state, action, observation)
                if observation.ok and action.tool == "read_file":
                    note_path = str(observation.data.get("path") or action.args.get("path", ""))
                    capture_working_note(state, note_path, observation.content)
                if observation.ok:
                    update_target_scope_from_observation(state, action, observation)
                if not observation.ok:
                    observation = add_retry_hint(observation, action)

            logger.record_step(
                step,
                raw_response,
                action,
                observation,
                extra={"llm_duration": llm_duration, "prompt_chars": prompt_chars},
            )
            state.history.append(HistoryItem(step, raw_response, action, observation))
            state.consecutive_errors = state.consecutive_errors + 1 if not observation.ok else 0
            if self.on_step:
                self.on_step(step, action, observation)

            if action and action.tool == "finish" and observation.ok:
                state.finished = True
                state.termination_reason = "finished"
                state.final_summary = str(observation.data.get("summary") or observation.content)
                break

            if state.consecutive_errors >= MAX_CONSECUTIVE_ERRORS:
                state.termination_reason = "too_many_errors"
                state.final_summary = f"Stopped after {state.consecutive_errors} consecutive errors."
                break
        else:
            state.termination_reason = "max_steps"
            state.final_summary = f"Stopped after reaching max_steps={self.max_steps}."

        success = state.finished
        logger.record_end(state.termination_reason, state.final_summary, success)
        return AgentResult(
            success=success,
            summary=state.final_summary,
            termination_reason=state.termination_reason,
            modified_files=list(state.modified_files),
            verification_records=list(state.verification_records),
            trajectory_path=str(logger.path),
        )
