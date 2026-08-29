from __future__ import annotations

from .protocol import Action, AgentState, Observation


EXPLORATION_TOOLS = {"list_dir", "read_file", "search"}
MAX_EXPLORATION_STREAK = 6
MAX_SAME_PATH_INSPECTIONS = 2


def apply_progress_guard(state: AgentState, action: Action, observation: Observation) -> Observation:
    if action.tool not in EXPLORATION_TOOLS or not observation.ok:
        state.exploration_streak = 0
        return observation

    state.exploration_streak += 1
    path = str(action.args.get("path", "."))
    same_path_count = count_same_path_inspections(state, action.tool, path)

    if same_path_count >= MAX_SAME_PATH_INSPECTIONS:
        return progress_error(
            "RepeatedInspection",
            (
                f"You already inspected {path!r} with {action.tool}. Do not inspect it again. "
                "Use the information you have and move to write_file, replace_in_file, run_shell, or finish."
            ),
        )

    if state.mode == "build" and state.exploration_streak > MAX_EXPLORATION_STREAK:
        return progress_error(
            "ExplorationBudgetExceeded",
            (
                "You have spent enough steps inspecting files. The next useful action should be write_file, "
                "replace_in_file, run_shell, or finish. If the target path does not exist, create it with write_file."
            ),
        )

    return observation


def count_same_path_inspections(state: AgentState, tool: str, path: str) -> int:
    count = 0
    for item in state.history:
        if item.action and item.action.tool == tool and str(item.action.args.get("path", ".")) == path:
            count += 1
    return count


def progress_error(error_type: str, message: str) -> Observation:
    return Observation(
        ok=False,
        tool="progress_guard",
        content=message,
        error_type=error_type,
        message=message,
        data={
            "retryable": True,
            "retry_hint": message,
        },
    )
