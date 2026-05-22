"""
World State Management
Persistent, evolving cognitive state
"""
import json
import os
from datetime import datetime
from typing import Any


def load_state(path: str) -> dict:
    """Load world state from file."""
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return _default_state()


def save_state(path: str, state: dict) -> None:
    """Save world state to file."""
    state["last_updated"] = datetime.now().isoformat()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def _default_state() -> dict:
    """Default initial world state."""
    return {
        "current_goal": None,
        "active_tasks": [],
        "recent_decisions": [],
        "observations": [],
        "constraints": [],
        "active_plan": None,
        "plan_history": [],
        "reasoning_chain": [],
        "context_summary": "",
        "metadata": {
            "created_at": datetime.now().isoformat(),
            "tick_count": 0,
            "goal_stability_score": 1.0,
        }
    }


def update_goal(state: dict, new_goal: str, reason: str) -> dict:
    """Update the current goal with drift tracking."""
    old_goal = state.get("current_goal")
    
    if old_goal != new_goal:
        state["recent_decisions"].append({
            "type": "goal_change",
            "from": old_goal,
            "to": new_goal,
            "reason": reason,
            "timestamp": datetime.now().isoformat(),
        })
        state["metadata"]["goal_stability_score"] = max(
            0.0, state["metadata"].get("goal_stability_score", 1.0) - 0.1
        )
    
    state["current_goal"] = new_goal
    return state


def add_observation(state: dict, observation: str, source: str = "system") -> dict:
    """Add an observation to the state."""
    state["observations"].append({
        "content": observation,
        "source": source,
        "timestamp": datetime.now().isoformat(),
    })
    # Keep only recent observations
    state["observations"] = state["observations"][-50:]
    return state


def update_plan(state: dict, plan: dict) -> dict:
    """Update the active plan."""
    old_plan = state.get("active_plan")
    if old_plan:
        state["plan_history"].append(old_plan)
        state["plan_history"] = state["plan_history"][-5:]  # Keep last 5
    
    state["active_plan"] = plan
    state["metadata"]["tick_count"] = state["metadata"].get("tick_count", 0) + 1
    return state


def compress_observations(state: dict, max_items: int = 20) -> dict:
    """Compress observations into summary."""
    if len(state.get("observations", [])) > max_items:
        obs = state["observations"]
        # Create summary from recent observations
        summary_parts = [o["content"][:100] for o in obs[-10:] if o.get("content")]
        state["context_summary"] = "; ".join(summary_parts)
        state["observations"] = obs[-max_items:]
    return state


def get_state_diff(before: dict, after: dict) -> dict:
    """Compare two states and return diff."""
    diff = {
        "goal_changed": before.get("current_goal") != after.get("current_goal"),
        "plan_changed": before.get("active_plan") != after.get("active_plan"),
        "new_observations": len(after.get("observations", [])) - len(before.get("observations", [])),
        "drift_score_change": (
            after.get("metadata", {}).get("goal_stability_score", 1.0) -
            before.get("metadata", {}).get("goal_stability_score", 1.0)
        ),
    }
    return diff
