"""
action_selector.py — Action selection module

Selects the single optimal next action from the plan.
"""
from typing import Any, Dict, List, Optional


class ActionSelector:
    """Action: selects the optimal next action from the plan."""

    def select_next(self, plan: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Select the best action from the plan (first by score)."""
        if not plan:
            return None
        return plan[0]

    def explain_selection(self, action: Dict[str, Any]) -> str:
        """Explain why this action was selected."""
        return (
            f"Selected '{action.get('title')}' "
            f"(score={action.get('score', 0):.4f}, "
            f"cost={action.get('estimated_cost', 0)})"
        )
