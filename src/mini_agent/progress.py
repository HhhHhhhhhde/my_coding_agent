from __future__ import annotations

from .protocol import Action, AgentState, Observation


EXPLORATION_TOOLS = {"list_dir", "read_file", "search"}
MAX_EXPLORATION_STREAK = 6
MAX_SAME_PATH_INSPECTIONS = 2
MAX_READ_FILE_CHUNKS_AFTER_BUDGET = 4


def apply_progress_guard(state: AgentState, action: Action, observation: Observation) -> Observation:
    if action.tool not in EXPLORATION_TOOLS or not observation.ok:
        state.exploration_streak = 0
        return observation

    state.exploration_streak += 1
    path = str(action.args.get("path", "."))

    if action.tool == "read_file":
        if overlaps_prior_read(state, path, observation):
            return progress_error(
                "RepeatedInspection",
                (
                    f"You already read this line range from {path!r}. Read a different range, or use the "
                    "information you have and move to write_file, replace_in_file, a verification command, or finish."
                ),
            )
    elif action.tool == "search":
        pattern = str(action.args.get("pattern", ""))
        same_search_count = count_same_searches(state, path, pattern)
        if same_search_count >= MAX_SAME_PATH_INSPECTIONS:
            return progress_error(
                "RepeatedSearch",
                (
                    f"You already searched for pattern {pattern!r} under {path!r}. Search a different pattern or "
                    "move to read_file, write_file, replace_in_file, a verification command, or finish."
                ),
            )
    else:
        same_path_count = count_same_path_inspections(state, action.tool, path)
        if same_path_count >= MAX_SAME_PATH_INSPECTIONS:
            return progress_error(
                "RepeatedInspection",
                (
                    f"You already inspected {path!r} with {action.tool}. Do not inspect it again. "
                    "Use the information you have and move to write_file, replace_in_file, a verification command, or finish."
                ),
            )

    if state.mode == "build" and state.exploration_streak > MAX_EXPLORATION_STREAK:
        if should_allow_read_file_after_budget(state, action, observation):
            return observation
        return progress_error(
            "ExplorationBudgetExceeded",
            (
                "You have spent enough steps inspecting files. Use the code you have already read and move to "
                "write_file, replace_in_file, a verification command, or finish. If the target path does not exist, "
                "create it with write_file."
            ),
        )

    return observation


def should_allow_read_file_after_budget(state: AgentState, action: Action, observation: Observation) -> bool:
    if action.tool != "read_file":
        return False
    path = str(action.args.get("path", "."))
    same_file_reads = count_read_file_chunks(state, path)
    prior_read_count = count_tool_calls(state, "read_file")
    if prior_read_count == 0:
        return True
    if same_file_reads == 0:
        return False
    return not overlaps_prior_read(state, path, observation) and same_file_reads < MAX_READ_FILE_CHUNKS_AFTER_BUDGET


def count_same_path_inspections(state: AgentState, tool: str, path: str) -> int:
    count = 0
    for item in state.history:
        if item.action and item.action.tool == tool and str(item.action.args.get("path", ".")) == path:
            count += 1
    return count


def count_tool_calls(state: AgentState, tool: str) -> int:
    return sum(1 for item in state.history if item.action and item.action.tool == tool)


def count_same_searches(state: AgentState, path: str, pattern: str) -> int:
    count = 0
    for item in state.history:
        if not item.action or item.action.tool != "search":
            continue
        if str(item.action.args.get("path", ".")) == path and str(item.action.args.get("pattern", "")) == pattern:
            count += 1
    return count


def count_read_file_chunks(state: AgentState, path: str) -> int:
    count = 0
    for item in state.history:
        if item.action and item.action.tool == "read_file" and str(item.action.args.get("path", ".")) == path:
            count += 1
    return count


def overlaps_prior_read(state: AgentState, path: str, observation: Observation) -> bool:
    current_range = read_range_from_observation(observation)
    if current_range is None:
        return False

    for item in state.history:
        if not item.action or item.action.tool != "read_file":
            continue
        if str(item.action.args.get("path", ".")) != path:
            continue
        prior_range = read_range_from_observation(item.observation)
        if prior_range is None:
            continue
        if ranges_overlap(current_range, prior_range):
            return True
    return False


def read_range_from_observation(observation: Observation) -> tuple[int, int] | None:
    start = observation.data.get("start")
    end = observation.data.get("end")
    if not isinstance(start, int) or not isinstance(end, int):
        return None
    return start, end


def ranges_overlap(left: tuple[int, int], right: tuple[int, int]) -> bool:
    return left[0] <= right[1] and right[0] <= left[1]


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
