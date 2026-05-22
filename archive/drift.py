"""
Drift Detection
Continuously monitor for cognitive drift
"""
import json
import os
from datetime import datetime
from typing import Any

from config import DRIFT_THRESHOLDS


class DriftDetector:
    """
    Detects various types of cognitive drift:
    - goal_drift: current goal diverging from original intent
    - reasoning_drift: reasoning chain becoming inconsistent
    - context_pollution: context becoming noisy/contaminated
    - execution_divergence: actions diverging from plan
    """

    def __init__(self, state_path: str):
        self.state_path = state_path
        self.history: list[dict] = []
        self._load_history()

    def _load_history(self) -> None:
        hist_file = self.state_path.replace("world_state.json", "drift_history.json")
        if os.path.exists(hist_file):
            with open(hist_file, "r", encoding="utf-8") as f:
                self.history = json.load(f).get("history", [])

    def _save_history(self) -> None:
        hist_file = self.state_path.replace("world_state.json", "drift_history.json")
        with open(hist_file, "w", encoding="utf-8") as f:
            json.dump({"history": self.history[-100:]}, f, ensure_ascii=False, indent=2)

    def detect_all(self, state: dict, events: list[dict]) -> dict:
        """Run all drift detection algorithms."""
        drift_report = {
            "timestamp": datetime.now().isoformat(),
            "goal_drift": self._detect_goal_drift(state),
            "reasoning_drift": self._detect_reasoning_drift(state),
            "context_pollution": self._detect_context_pollution(state),
            "execution_divergence": self._detect_execution_divergence(state, events),
            "overall_drift_score": 0.0,
            "drifts_detected": [],
        }

        # Calculate overall drift score
        drift_scores = [
            drift_report["goal_drift"]["score"],
            drift_report["reasoning_drift"]["score"],
            drift_report["context_pollution"]["score"],
            drift_report["execution_divergence"]["score"],
        ]
        drift_report["overall_drift_score"] = sum(drift_scores) / len(drift_scores)

        # Collect detected drifts
        for drift_type in ["goal_drift", "reasoning_drift", "context_pollution", "execution_divergence"]:
            if drift_report[drift_type]["detected"]:
                drift_report["drifts_detected"].append(drift_type)

        # Save to history
        self.history.append(drift_report)
        self._save_history()

        return drift_report

    def _detect_goal_drift(self, state: dict) -> dict:
        """Detect if current goal has drifted from original intent."""
        goal_stability = state.get("metadata", {}).get("goal_stability_score", 1.0)
        recent_decisions = state.get("recent_decisions", [])
        
        # Count goal changes
        goal_changes = [d for d in recent_decisions if d.get("type") == "goal_change"]
        
        score = 1.0 - goal_stability
        threshold = DRIFT_THRESHOLDS["goal"]
        
        return {
            "detected": score > threshold,
            "score": score,
            "threshold": threshold,
            "goal_stability": goal_stability,
            "goal_change_count": len(goal_changes),
            "message": f"Goal stability: {goal_stability:.2f}, changes: {len(goal_changes)}"
        }

    def _detect_reasoning_drift(self, state: dict) -> dict:
        """Detect if reasoning chain has become inconsistent."""
        reasoning_chain = state.get("reasoning_chain", [])
        
        if len(reasoning_chain) < 2:
            return {"detected": False, "score": 0.0, "chain_length": 0}
        
        # Check for contradictions in reasoning
        contradictions = 0
        for i, r1 in enumerate(reasoning_chain[-5:]):
            for r2 in reasoning_chain[i+1:]:
                if r1.get("conclusion") and r2.get("conclusion"):
                    if r1["conclusion"] != r2["conclusion"]:
                        # Potential contradiction
                        contradictions += 1
        
        score = min(1.0, contradictions * 0.2)
        threshold = DRIFT_THRESHOLDS["reasoning"]
        
        return {
            "detected": score > threshold,
            "score": score,
            "threshold": threshold,
            "chain_length": len(reasoning_chain),
            "contradictions": contradictions,
            "message": f"Reasoning chain: {len(reasoning_chain)}, contradictions: {contradictions}"
        }

    def _detect_context_pollution(self, state: dict) -> dict:
        """Detect if context has become noisy."""
        observations = state.get("observations", [])
        context_summary = state.get("context_summary", "")
        
        # High observation count without summary = potential pollution
        raw_obs_count = len([o for o in observations if not o.get("compressed", False)])
        
        score = 0.0
        if raw_obs_count > 30:
            score += 0.3
        if not context_summary and len(observations) > 10:
            score += 0.2
        
        threshold = DRIFT_THRESHOLDS["context_pollution"]
        
        return {
            "detected": score > threshold,
            "score": score,
            "threshold": threshold,
            "raw_observations": raw_obs_count,
            "has_summary": bool(context_summary),
            "message": f"Raw obs: {raw_obs_count}, summary: {'yes' if context_summary else 'no'}"
        }

    def _detect_execution_divergence(self, state: dict, events: list[dict]) -> dict:
        """Detect if execution has diverged from plan."""
        active_plan = state.get("active_plan", {})
        plan_steps = active_plan.get("steps", []) if active_plan else []
        
        # Count failed tasks vs completed
        task_events = [e for e in events if "TASK" in (e.type.value if hasattr(e.type, 'value') else str(e.type if hasattr(e, 'type') else e.get("type", "")))]
        failed = len([e for e in task_events if "FAILED" in e.get("type", "")])
        completed = len([e for e in task_events if "COMPLETED" in e.get("type", "")])
        
        if completed + failed == 0:
            return {"detected": False, "score": 0.0}
        
        failure_rate = failed / (completed + failed)
        score = failure_rate
        threshold = DRIFT_THRESHOLDS["execution"]
        
        return {
            "detected": score > threshold,
            "score": score,
            "threshold": threshold,
            "completed": completed,
            "failed": failed,
            "failure_rate": failure_rate,
            "message": f"Completed: {completed}, Failed: {failed}, rate: {failure_rate:.2f}"
        }

    def get_drift_trend(self, last_n: int = 10) -> dict:
        """Analyze drift trend over recent cycles."""
        if not self.history:
            return {"trend": "no_data", "message": "No drift history yet"}
        
        recent = self.history[-last_n:]
        avg_scores = [h["overall_drift_score"] for h in recent]
        
        if len(avg_scores) < 2:
            return {"trend": "insufficient_data"}
        
        # Simple trend detection
        first_half = sum(avg_scores[:len(avg_scores)//2]) / (len(avg_scores)//2)
        second_half = sum(avg_scores[len(avg_scores)//2:]) / (len(avg_scores) - len(avg_scores)//2)
        
        delta = second_half - first_half
        
        return {
            "trend": "increasing" if delta > 0.1 else "decreasing" if delta < -0.1 else "stable",
            "delta": delta,
            "avg_score": sum(avg_scores) / len(avg_scores),
            "recent_scores": avg_scores,
            "message": f"Drift trend: {'↑ increasing' if delta > 0.1 else '↓ decreasing' if delta < -0.1 else '→ stable'} (Δ={delta:.3f})"
        }
