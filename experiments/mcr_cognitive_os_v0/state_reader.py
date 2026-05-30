"""
state_reader.py — Perception module

Reads the current environment state: loads tasks, checks runtime state,
and produces a perception snapshot for the cognitive loop.
"""
import json
from pathlib import Path
from typing import Any, Dict, List


class StateReader:
    """Perception: reads environment state from tasks.json and runtime."""

    def __init__(self, tasks_path: str):
        self.tasks_path = Path(tasks_path)

    def perceive(self) -> Dict[str, Any]:
        """Read current state and return perception snapshot."""
        tasks = self._load_tasks()
        return {
            "tasks": tasks,
            "task_count": len(tasks),
            "pending_count": sum(1 for t in tasks if t.get("status") == "pending"),
            "timestamp": self._now(),
        }

    def _load_tasks(self) -> List[Dict]:
        """Load tasks from JSON file."""
        if not self.tasks_path.exists():
            return []
        with open(self.tasks_path) as f:
            data = json.load(f)
        return data.get("tasks", [])

    @staticmethod
    def _now() -> float:
        """Current time (no external deps)."""
        import time
        return time.time()
