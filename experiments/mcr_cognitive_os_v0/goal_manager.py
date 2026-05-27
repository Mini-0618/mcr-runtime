"""
goal_manager.py — Goal module

Tracks the current active goal and checks task alignment.
"""
from typing import Any, Dict, List, Optional


class GoalManager:
    """Goal: tracks active goal and checks task alignment."""

    def __init__(self):
        self.current_goal: Optional[str] = None
        self.goal_history: List[Dict[str, Any]] = []

    def set_goal(self, goal: str, reason: str = ""):
        """Set a new active goal."""
        if self.current_goal:
            self.goal_history.append({
                "goal": self.current_goal,
                "replaced_by": goal,
                "reason": reason,
            })
        self.current_goal = goal

    def check_alignment(self, task: Dict[str, Any]) -> bool:
        """Check if a task aligns with the current goal."""
        if not self.current_goal:
            return True  # no goal = anything is aligned
        category = task.get("category", "")
        # Simple heuristic: maintenance/bugfix align with stability goals
        # release/destructive need explicit alignment
        aligned_categories = {"maintenance", "bugfix", "optimization", "documentation"}
        if self.current_goal == "stability":
            return category in aligned_categories
        return True

    def describe(self) -> Dict[str, Any]:
        """Return current goal state."""
        return {
            "current_goal": self.current_goal,
            "history_count": len(self.goal_history),
        }
