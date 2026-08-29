from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Task:
    title: str
    completed: bool = False


class TaskManager:
    def __init__(self) -> None:
        self._tasks: list[Task] = []

    def add(self, title: str) -> Task:
        task = Task(title=title, completed=False)
        self._tasks.append(task)
        return task

    def complete(self, title: str) -> bool:
        for task in self._tasks:
            if task.title == title:
                task.completed = True
                return True
        return False

    def active_titles(self) -> list[str]:
        return [task.title for task in self._tasks if not task.completed]

    def completed_count(self) -> int:
        return sum(1 for task in self._tasks if task.completed)