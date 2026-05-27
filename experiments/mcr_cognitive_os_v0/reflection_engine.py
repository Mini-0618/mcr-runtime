"""
reflection_engine.py — Reflection module

Evaluates whether the selected action was a good choice.
Produces a reflection record for memory.
"""
from typing import Any, Dict


class ReflectionEngine:
    """Reflection: evaluates action outcomes and produces learning records."""

    def reflect(
        self,
        action: Dict[str, Any],
        policy_verdict: str,
        task_count: int,
        attended_count: int,
    ) -> Dict[str, Any]:
        """Reflect on the action selection and produce a reflection record."""
        score = action.get("score", 0) if action else 0
        was_good = score > 0.5 and policy_verdict == "allowed"

        reflection = {
            "action_taken": action.get("title") if action else "none",
            "was_good_choice": was_good,
            "score": score,
            "policy_status": policy_verdict,
            "tasks_total": task_count,
            "tasks_attended": attended_count,
            "lesson": self._derive_lesson(was_good, score, policy_verdict),
        }
        return reflection

    def _derive_lesson(self, was_good: bool, score: float, policy_status: str) -> str:
        """Derive a lesson from the reflection."""
        if was_good:
            return f"Good action selection (score={score:.2f}). Continue prioritizing high-score, low-risk tasks."
        if policy_status == "blocked":
            return "Action was blocked by policy. Review task category and risk before proposing."
        if policy_status == "requires_owner":
            return "Action requires owner approval. Escalate before proceeding."
        return f"Low confidence action (score={score:.2f}). Consider alternatives."

    def should_write_to_memory(self, reflection: Dict[str, Any]) -> bool:
        """Decide if this reflection is worth persisting."""
        # Always write reflections — they're the core learning signal
        return True
