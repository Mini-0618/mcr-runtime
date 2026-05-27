"""
attention_filter.py — Attention module

Filters tasks based on urgency and relevance.
Only tasks that pass attention are forwarded to the brain.
"""
from typing import Any, Dict, List


class AttentionFilter:
    """Attention: filters tasks by urgency threshold and relevance."""

    def __init__(self, urgency_threshold: float = 0.3):
        self.urgency_threshold = urgency_threshold

    def filter(self, tasks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Return tasks that pass the attention filter."""
        attended = []
        for task in tasks:
            if task.get("status") != "pending":
                continue
            urgency = task.get("urgency", 0)
            if urgency >= self.urgency_threshold:
                attended.append(task)
        return attended

    def explain(self, task: Dict[str, Any]) -> str:
        """Explain why a task passed or failed attention."""
        urgency = task.get("urgency", 0)
        if urgency >= self.urgency_threshold:
            return f"PASSED: urgency={urgency:.2f} >= threshold={self.urgency_threshold:.2f}"
        return f"FILTERED: urgency={urgency:.2f} < threshold={self.urgency_threshold:.2f}"
