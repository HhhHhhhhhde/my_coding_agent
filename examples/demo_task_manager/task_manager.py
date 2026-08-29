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
        raise NotImplementedError

    def complete(self, title: str) -> bool:
        raise NotImplementedError

    def active_titles(self) -> list[str]:
        raise NotImplementedError

    def completed_count(self) -> int:
        raise NotImplementedError
