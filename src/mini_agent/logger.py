from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .protocol import Action, Observation


class TrajectoryLogger:
    def __init__(self, workspace: Path) -> None:
        self.directory = workspace / "trajectories"
        self.directory.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        self.path = self.directory / f"run-{stamp}.jsonl"

    def record_step(
        self,
        step: int,
        raw_model_response: str,
        action: Action | None,
        observation: Observation,
        extra: dict[str, Any] | None = None,
    ) -> None:
        event: dict[str, Any] = {
            "type": "step",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "step": step,
            "raw_model_response": raw_model_response,
            "parsed_action": action.__dict__ if action else None,
            "observation": observation.to_dict(),
        }
        if extra:
            event.update(extra)
        self._write(event)

    def record_end(self, termination_reason: str, summary: str, success: bool) -> None:
        self._write(
            {
                "type": "end",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "termination_reason": termination_reason,
                "summary": summary,
                "success": success,
            }
        )

    def _write(self, event: dict[str, Any]) -> None:
        with self.path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(event, ensure_ascii=False) + "\n")
