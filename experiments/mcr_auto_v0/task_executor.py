"""
task_executor.py — MCR-Auto Mock Task Executor

Simulates executing tasks. Returns mock results.
Real execution is deferred to MCR Operator (Stage 4).

NO real browser, NO network, NO file mutation.
"""
import time
from typing import Any, Dict, Optional


class ExecutionResult:
    """Result of a mock task execution."""

    def __init__(self, success: bool, task_id: str, action: str,
                 output: str, duration_ms: float, artifacts: list = None):
        self.success = success
        self.task_id = task_id
        self.action = action
        self.output = output
        self.duration_ms = duration_ms
        self.artifacts = artifacts or []

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "task_id": self.task_id,
            "action": self.action,
            "output": self.output,
            "duration_ms": self.duration_ms,
            "artifacts": self.artifacts,
        }


class MockTaskExecutor:
    """Executes tasks in mock mode. Returns simulated results."""

    def execute(self, action: Dict[str, Any]) -> ExecutionResult:
        """Execute a mock action and return simulated result."""
        start = time.time()
        action_type = action.get("action_type", "unknown")
        title = action.get("title", "untitled")
        task_id = action.get("task_id", "unknown")

        if action_type == "investigate":
            result = self._mock_investigate(title)
        elif action_type == "fix":
            result = self._mock_fix(title)
        elif action_type == "write":
            result = self._mock_write(title)
        elif action_type == "profile_and_optimize":
            result = self._mock_optimize(title)
        elif action_type == "escalate":
            result = self._mock_escalate(title)
        else:
            result = self._mock_generic(title, action_type)

        duration = (time.time() - start) * 1000
        return ExecutionResult(
            success=result["success"],
            task_id=task_id,
            action=action_type,
            output=result["output"],
            duration_ms=round(duration, 2),
            artifacts=result.get("artifacts", []),
        )

    def _mock_investigate(self, title: str) -> dict:
        return {
            "success": True,
            "output": f"[MOCK] Investigated '{title}': found 3 relevant files, no critical issues.",
            "artifacts": ["investigation_report.md"],
        }

    def _mock_fix(self, title: str) -> dict:
        return {
            "success": True,
            "output": f"[MOCK] Fixed '{title}': patched 1 file, all tests pass.",
            "artifacts": ["patch.diff"],
        }

    def _mock_write(self, title: str) -> dict:
        return {
            "success": True,
            "output": f"[MOCK] Wrote documentation for '{title}': 2 pages generated.",
            "artifacts": ["output.md"],
        }

    def _mock_optimize(self, title: str) -> dict:
        return {
            "success": True,
            "output": f"[MOCK] Profiled '{title}': 15% improvement in hot path.",
            "artifacts": ["profile_report.txt"],
        }

    def _mock_escalate(self, title: str) -> dict:
        return {
            "success": False,
            "output": f"[MOCK] ESCALATED '{title}': requires owner approval, not executed.",
            "artifacts": [],
        }

    def _mock_generic(self, title: str, action_type: str) -> dict:
        return {
            "success": True,
            "output": f"[MOCK] Executed '{action_type}' on '{title}': completed.",
            "artifacts": [],
        }
