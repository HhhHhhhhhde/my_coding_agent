from pathlib import Path

from mini_agent.protocol import Action, AgentState, Observation
from mini_agent.target_scope import (
    apply_target_scope_guard,
    infer_initial_target_scope,
    update_target_scope_from_observation,
)


def test_infer_initial_target_scope_from_user_path(tmp_path: Path) -> None:
    target = tmp_path / "examples" / "demo_runner_game"
    target.mkdir(parents=True)

    scope, reason = infer_initial_target_scope("完成 examples/demo_runner_game 里的游戏", tmp_path)

    assert scope == "examples/demo_runner_game"
    assert "user named directory path" in reason


def test_update_target_scope_from_listed_important_file() -> None:
    state = AgentState("完成跑酷游戏", ".", "build", 20)
    action = Action("list", "list_dir", {"path": "examples/demo_runner_game"})
    observation = Observation(
        True,
        "list_dir",
        content="file\texamples\\demo_runner_game\\GAMEPLAY.md",
        data={"path": "examples\\demo_runner_game"},
    )

    update_target_scope_from_observation(state, action, observation)

    assert state.target_scope == "examples/demo_runner_game"
    assert "GAMEPLAY.md" in state.target_scope_reason


def test_target_scope_guard_blocks_path_outside_scope() -> None:
    state = AgentState("完成跑酷游戏", ".", "build", 20, target_scope="examples/demo_runner_game")
    action = Action("read", "read_file", {"path": "pyproject.toml"})

    observation = apply_target_scope_guard(state, action)

    assert observation is not None
    assert not observation.ok
    assert observation.error_type == "TargetScopeViolation"
    assert observation.data["target_scope"] == "examples/demo_runner_game"


def test_target_scope_guard_allows_path_inside_scope() -> None:
    state = AgentState("完成跑酷游戏", ".", "build", 20, target_scope="examples/demo_runner_game")
    action = Action("write", "write_file", {"path": "examples/demo_runner_game/runner_game.py"})

    observation = apply_target_scope_guard(state, action)

    assert observation is None
