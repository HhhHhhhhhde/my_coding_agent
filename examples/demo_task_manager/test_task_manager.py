from task_manager import TaskManager


def test_new_task_is_active() -> None:
    manager = TaskManager()

    task = manager.add("write spec")

    assert task.title == "write spec"
    assert task.completed is False
    assert manager.active_titles() == ["write spec"]


def test_complete_task() -> None:
    manager = TaskManager()
    manager.add("write tests")

    assert manager.complete("write tests") is True
    assert manager.active_titles() == []
    assert manager.completed_count() == 1


def test_complete_missing_task() -> None:
    manager = TaskManager()

    assert manager.complete("missing") is False
    assert manager.completed_count() == 0
