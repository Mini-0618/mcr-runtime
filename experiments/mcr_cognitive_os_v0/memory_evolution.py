"""
memory_evolution.py — MCR Memory Evolution v0.1

Reads previous run results and generates policy adjustments for next cycle.
Extracts: success_pattern, failure_pattern, avoid_next_time, reuse_next_time.
"""
import json
from pathlib import Path
from typing import Any, Dict, List, Optional


class EvolutionRecord:
    """A single evolution insight derived from a run."""

    def __init__(self, success_pattern: str = "", failure_pattern: str = "",
                 avoid_next_time: str = "", reuse_next_time: str = "",
                 policy_adjustments: List[Dict[str, Any]] = None,
                 confidence: float = 0.5):
        self.success_pattern = success_pattern
        self.failure_pattern = failure_pattern
        self.avoid_next_time = avoid_next_time
        self.reuse_next_time = reuse_next_time
        self.policy_adjustments = policy_adjustments or []
        self.confidence = confidence

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success_pattern": self.success_pattern,
            "failure_pattern": self.failure_pattern,
            "avoid_next_time": self.avoid_next_time,
            "reuse_next_time": self.reuse_next_time,
            "policy_adjustments": self.policy_adjustments,
            "confidence": self.confidence,
        }


class MemoryEvolution:
    """Reads past runs and generates policy evolution for next cycle."""

    def __init__(self, history_path: str = None):
        self.history_path = history_path
        self.history: List[Dict[str, Any]] = []
        if history_path and Path(history_path).exists():
            self._load_history()

    def _load_history(self):
        with open(self.history_path, encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            self.history = data
        else:
            self.history = [data]

    def evolve(self, current_run: Dict[str, Any]) -> EvolutionRecord:
        """Analyze current run and produce evolution record."""
        reflection = current_run.get("reflection", {})
        policy = current_run.get("policy", {})
        execution = current_run.get("execution", {})
        final_state = current_run.get("final_state", "UNKNOWN")
        scoring = current_run.get("scoring", {})
        attention = current_run.get("attention", {})

        lesson = reflection.get("lesson", "")
        was_good = reflection.get("was_good_choice", False)
        exec_success = execution.get("success") if execution else None
        exec_output = execution.get("output", "") if execution else ""

        success_pattern = ""
        failure_pattern = ""
        avoid = ""
        reuse = ""
        adjustments = []

        # Analyze success patterns
        if was_good and exec_success:
            success_pattern = f"Good selection: {scoring.get('top_task', '?')} (score={scoring.get('top_score', 0)})"
            reuse = f"Continue prioritizing tasks with score > 0.5 and low risk"

        # Analyze failure patterns
        if not was_good or exec_success is False:
            failure_pattern = f"Action failed or was blocked: {lesson}"
            if "blocked" in lesson.lower():
                avoid = "Avoid proposing tasks in blocked categories"
                adjustments.append({
                    "type": "risk_threshold",
                    "action": "decrease",
                    "reason": "Too many blocked tasks, lower risk tolerance",
                })
            if "owner" in lesson.lower() or final_state in ("ASK_OWNER", "STOP"):
                avoid = "Pre-check requires_owner before scoring"
                adjustments.append({
                    "type": "pre_check",
                    "action": "add_owner_check",
                    "reason": "Task requires owner approval",
                })

        # Analyze attention efficiency
        attended = attention.get("attended_count", 0)
        filtered = attention.get("filtered_count", 0)
        total = attended + filtered
        if total > 0 and filtered / total > 0.5:
            adjustments.append({
                "type": "attention_threshold",
                "action": "relax",
                "reason": f"{filtered}/{total} tasks filtered, may be too aggressive",
            })

        # Analyze blocked ratio
        blocked = policy.get("blocked", 0)
        allowed = policy.get("allowed", 0)
        if blocked > allowed and blocked > 0:
            adjustments.append({
                "type": "risk_threshold",
                "action": "relax",
                "reason": f"More blocked ({blocked}) than allowed ({allowed})",
            })

        # Learn from execution output
        if exec_output and "MOCK" in exec_output:
            reuse = f"Mock execution pattern worked: {exec_output[:80]}"

        # Default insight if nothing specific
        if not success_pattern and not failure_pattern:
            success_pattern = "Cycle completed without notable pattern"

        return EvolutionRecord(
            success_pattern=success_pattern,
            failure_pattern=failure_pattern,
            avoid_next_time=avoid,
            reuse_next_time=reuse,
            policy_adjustments=adjustments,
            confidence=0.6 if was_good else 0.4,
        )

    def get_policy_hints(self) -> List[Dict[str, Any]]:
        """Return accumulated policy adjustments from history."""
        hints = []
        for record in self.history:
            evolution = record.get("memory_evolution", {})
            for adj in evolution.get("policy_adjustments", []):
                hints.append(adj)
        return hints

    def summarize(self) -> str:
        """One-line summary of evolution state."""
        if not self.history:
            return "No evolution history yet"
        last = self.history[-1].get("memory_evolution", {})
        return f"Last: {last.get('success_pattern', '?')[:60]}"
