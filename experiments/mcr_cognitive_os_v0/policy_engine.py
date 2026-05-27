"""
policy_engine.py — Policy module

Enforces boundaries: blocks destructive actions, flags owner-required tasks,
and checks risk thresholds.
"""
from typing import Any, Dict, List


class PolicyVerdict:
    """Result of a policy check."""
    ALLOWED = "allowed"
    BLOCKED = "blocked"
    REQUIRES_OWNER = "requires_owner"

    def __init__(self, status: str, reason: str, task_id: str = ""):
        self.status = status
        self.reason = reason
        self.task_id = task_id

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "reason": self.reason,
            "task_id": self.task_id,
        }


class PolicyEngine:
    """Policy: enforces safety boundaries on task execution."""

    BLOCKED_CATEGORIES = {"destructive"}
    OWNER_REQUIRED_CATEGORIES = {"release"}
    MAX_RISK_THRESHOLD = 0.85

    def check(self, task: Dict[str, Any]) -> PolicyVerdict:
        """Check a task against all policies."""
        task_id = task.get("id", "unknown")
        category = task.get("category", "")
        risk = task.get("risk", 0)
        requires_owner = task.get("requires_owner", False)

        # Block destructive
        if category in self.BLOCKED_CATEGORIES:
            return PolicyVerdict(
                PolicyVerdict.BLOCKED,
                f"Category '{category}' is blocked by policy",
                task_id,
            )

        # Block excessive risk
        if risk > self.MAX_RISK_THRESHOLD:
            return PolicyVerdict(
                PolicyVerdict.BLOCKED,
                f"Risk {risk:.2f} exceeds threshold {self.MAX_RISK_THRESHOLD}",
                task_id,
            )

        # Flag owner-required
        if requires_owner or category in self.OWNER_REQUIRED_CATEGORIES:
            return PolicyVerdict(
                PolicyVerdict.REQUIRES_OWNER,
                f"Task requires owner approval (category='{category}', requires_owner={requires_owner})",
                task_id,
            )

        return PolicyVerdict(PolicyVerdict.ALLOWED, "All policies passed", task_id)

    def filter_allowed(self, tasks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Return only tasks that pass policy (ALLOWED only, not REQUIRES_OWNER)."""
        return [t for t in tasks if self.check(t).status == PolicyVerdict.ALLOWED]
