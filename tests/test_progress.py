from mini_agent.progress import apply_progress_guard
from mini_agent.protocol import Action, AgentState, HistoryItem, Observation


def test_progress_guard_allows_first_read_after_directory_exploration() -> None:
    state = AgentState("Add maps", ".", "build", 20)
    for step in range(1, 7):
        action = Action("inspect", "list_dir", {"path": f"dir{step}"})
        state.history.append(HistoryItem(step, "{}", action, Observation(True, "list_dir")))
        state.exploration_streak += 1

    action = Action("read target", "read_file", {"path": "examples/demo_snake_game/snake_game.py"})
    observation = Observation(True, "read_file", content="1: class Game:")

    guarded = apply_progress_guard(state, action, observation)

    assert guarded.ok
    assert guarded.content == "1: class Game:"


def test_progress_guard_allows_non_overlapping_file_chunks() -> None:
    state = AgentState("Add maps", ".", "build", 20)
    for step in range(1, 5):
        action = Action("inspect", "list_dir", {"path": f"dir{step}"})
        state.history.append(HistoryItem(step, "{}", action, Observation(True, "list_dir")))
        state.exploration_streak += 1

    first = Action("read", "read_file", {"path": "snake_game.py", "start": 1, "end": 300})
    state.history.append(
        HistoryItem(5, "{}", first, Observation(True, "read_file", data={"path": "snake_game.py", "start": 1, "end": 120}))
    )
    state.exploration_streak += 1
    second = Action("read", "read_file", {"path": "snake_game.py", "start": 121, "end": 341})
    state.history.append(
        HistoryItem(
            6,
            "{}",
            second,
            Observation(True, "read_file", data={"path": "snake_game.py", "start": 121, "end": 240}),
        )
    )
    state.exploration_streak += 1

    action = Action("read tail", "read_file", {"path": "snake_game.py", "start": 241, "end": 341})
    observation = Observation(True, "read_file", content="241:     self.draw()", data={"start": 241, "end": 341})

    guarded = apply_progress_guard(state, action, observation)

    assert guarded.ok
    assert guarded.content == "241:     self.draw()"


def test_progress_guard_blocks_overlapping_file_chunk() -> None:
    state = AgentState("Read duplicate", ".", "build", 20)
    action = Action("read", "read_file", {"path": "sample.py", "start": 1, "end": 100})
    state.history.append(
        HistoryItem(1, "{}", action, Observation(True, "read_file", data={"path": "sample.py", "start": 1, "end": 100}))
    )

    repeated = Action("read again", "read_file", {"path": "sample.py", "start": 80, "end": 120})
    observation = Observation(True, "read_file", content="80: value = 1", data={"start": 80, "end": 120})

    guarded = apply_progress_guard(state, repeated, observation)

    assert not guarded.ok
    assert guarded.error_type == "RepeatedInspection"


def test_progress_guard_still_blocks_many_different_file_reads() -> None:
    state = AgentState("Inspect too much", ".", "build", 20)
    for step in range(1, 7):
        action = Action("read", "read_file", {"path": f"{step}.py"})
        state.history.append(HistoryItem(step, "{}", action, Observation(True, "read_file")))
        state.exploration_streak += 1

    action = Action("read another", "read_file", {"path": "7.py"})
    observation = Observation(True, "read_file", content="value = 7")

    guarded = apply_progress_guard(state, action, observation)

    assert not guarded.ok
    assert guarded.error_type == "ExplorationBudgetExceeded"
