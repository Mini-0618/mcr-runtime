"""
input_adapter.py — Real task input interface

Converts free-text task descriptions into structured task objects
for the cognitive loop. Supports CLI single-task and stdin modes.
"""
import re
import uuid
from typing import Any, Dict, List, Optional


# High-risk keywords that require owner approval
HIGH_RISK_KEYWORDS = [
    "merge", "push", "delete", "token", "secret", "browser",
    "social", "payment", "deploy", "publish", "release", "pypi",
    "production", "force", "drop", "purge", "destroy", "wipe",
]

# Category detection from keywords
CATEGORY_MAP = {
    "fix": "bugfix",
    "bug": "bugfix",
    "debug": "bugfix",
    "write": "documentation",
    "document": "documentation",
    "doc": "documentation",
    "readme": "documentation",
    "optimize": "optimization",
    "performance": "optimization",
    "speed": "optimization",
    "review": "maintenance",
    "check": "maintenance",
    "test": "maintenance",
    "refactor": "maintenance",
    "deploy": "release",
    "publish": "release",
    "release": "release",
    "merge": "release",
    "push": "release",
    "tag": "release",
    "delete": "destructive",
    "remove": "destructive",
    "purge": "destructive",
    "destroy": "destructive",
}


def text_to_task(text: str, defaults: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Convert free-text description into a structured task object."""
    text = text.strip()
    if not text:
        raise ValueError("Task text cannot be empty")

    task_id = f"cli_{uuid.uuid4().hex[:8]}"
    lower = text.lower()

    # Detect if requires owner
    requires_owner = any(kw in lower for kw in HIGH_RISK_KEYWORDS)

    # Detect category
    category = "maintenance"  # default
    for kw, cat in CATEGORY_MAP.items():
        if kw in lower:
            category = cat
            break

    # Estimate risk
    risk = _estimate_risk(lower, category)

    # Estimate urgency from keywords
    urgency = _estimate_urgency(lower)

    # Estimate priority (inverse of risk for unknown tasks)
    priority = max(0.3, 1.0 - risk * 0.5)

    # Estimate token cost from description length
    token_cost = max(100, len(text) * 10)

    task = {
        "id": task_id,
        "title": text[:100],
        "description": text,
        "priority": round(priority, 2),
        "risk": round(risk, 2),
        "token_cost": token_cost,
        "urgency": round(urgency, 2),
        "category": category,
        "requires_owner": requires_owner,
        "status": "pending",
        "source": "cli",
    }

    # Apply any overrides
    if defaults:
        for k, v in defaults.items():
            if k not in task:
                task[k] = v

    return task


def text_to_tasks(text: str) -> List[Dict[str, Any]]:
    """Convert multi-line text into multiple tasks (one per non-empty line)."""
    lines = [line.strip() for line in text.strip().split("\n") if line.strip()]
    return [text_to_task(line) for line in lines]


def _estimate_risk(text: str, category: str) -> float:
    """Estimate risk level from text content and category."""
    base_risk = {
        "bugfix": 0.2,
        "documentation": 0.1,
        "maintenance": 0.2,
        "optimization": 0.3,
        "release": 0.7,
        "destructive": 0.95,
    }.get(category, 0.4)

    # Boost risk for dangerous keywords
    danger_boost = sum(0.15 for kw in HIGH_RISK_KEYWORDS if kw in text)
    return min(1.0, base_risk + danger_boost)


def _estimate_urgency(text: str) -> float:
    """Estimate urgency from text keywords."""
    if any(w in text for w in ["urgent", "asap", "immediately", "now", "critical"]):
        return 0.9
    if any(w in text for w in ["soon", "important", "priority"]):
        return 0.7
    if any(w in text for w in ["later", "someday", "maybe", "optional"]):
        return 0.2
    return 0.5  # medium default


def format_task_report(task: Dict[str, Any]) -> str:
    """Format a task object into a readable report."""
    lines = [
        f"Task ID:       {task['id']}",
        f"Title:         {task['title']}",
        f"Category:      {task['category']}",
        f"Priority:      {task['priority']}",
        f"Risk:          {task['risk']}",
        f"Urgency:       {task['urgency']}",
        f"Token Cost:    {task['token_cost']}",
        f"Requires Owner:{' YES' if task['requires_owner'] else ' no'}",
        f"Status:        {task['status']}",
    ]
    return "\n".join(lines)
