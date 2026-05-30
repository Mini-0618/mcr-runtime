"""
task_scorer.py — Brain scoring module

Scores each task on a composite of priority, risk (inverted), and token cost
(inverted). Higher score = more desirable to execute now.
"""
from typing import Any, Dict, List


class TaskScorer:
    """Brain: scores tasks on composite priority/risk/cost metric."""

    def __init__(self, w_priority: float = 0.5, w_risk: float = 0.3, w_cost: float = 0.2):
        self.w_priority = w_priority
        self.w_risk = w_risk
        self.w_cost = w_cost

    def score(self, tasks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Score each task and return with score attached."""
        scored = []
        for task in tasks:
            t = dict(task)
            t["score"] = self._compute_score(t)
            scored.append(t)
        return scored

    def _compute_score(self, task: Dict[str, Any]) -> float:
        """Composite score: high priority, low risk, low cost = best."""
        priority = task.get("priority", 0.5)
        risk = task.get("risk", 0.5)
        cost = min(task.get("token_cost", 500) / 1000.0, 1.0)  # normalize to 0-1
        score = (
            self.w_priority * priority
            + self.w_risk * (1.0 - risk)
            + self.w_cost * (1.0 - cost)
        )
        return round(score, 4)

    def rank(self, scored_tasks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Return tasks sorted by score descending."""
        return sorted(scored_tasks, key=lambda t: t.get("score", 0), reverse=True)
