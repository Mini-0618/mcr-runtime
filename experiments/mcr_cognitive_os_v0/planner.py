"""
planner.py — Planning module

Generates an ordered action plan from scored, policy-checked tasks.
"""
from typing import Any, Dict, List


class Planner:
    """Planning: generates ordered action plan from scored tasks."""

    def plan(self, scored_tasks: List[Dict[str, Any]], max_actions: int = 3) -> List[Dict[str, Any]]:
        """Generate a plan: top N tasks by score, with action type assigned."""
        plan = []
        for task in scored_tasks[:max_actions]:
            action = {
                "task_id": task.get("id"),
                "title": task.get("title"),
                "action_type": self._determine_action(task),
                "score": task.get("score", 0),
                "estimated_cost": task.get("token_cost", 0),
            }
            plan.append(action)
        return plan

    def _determine_action(self, task: Dict[str, Any]) -> str:
        """Determine what kind of action to take for a task."""
        category = task.get("category", "")
        action_map = {
            "maintenance": "investigate",
            "bugfix": "fix",
            "documentation": "write",
            "optimization": "profile_and_optimize",
            "release": "prepare_release",
        }
        return action_map.get(category, "investigate")
