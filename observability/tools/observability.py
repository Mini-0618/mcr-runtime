"""
Observability Module
Cognitive trace and state snapshots
"""
import json
import os
import uuid
from datetime import datetime
from typing import Any

from config import TRACE_DIR, SNAPSHOT_DIR, SNAPSHOT_EVERY


class CognitiveTrace:
    """
    Records each cognitive tick for analysis.
    Enables frame-by-frame inspection of state transitions.
    """

    def __init__(self, trace_dir: str = TRACE_DIR):
        self.trace_dir = trace_dir
        os.makedirs(trace_dir, exist_ok=True)
        self.trace_index = self._load_index()

    def _load_index(self) -> dict:
        index_path = os.path.join(self.trace_dir, "index.json")
        if os.path.exists(index_path):
            with open(index_path, "r", encoding="utf-8") as f:
                return json.load(f)
        return {"ticks": [], "count": 0}

    def _save_index(self) -> None:
        index_path = os.path.join(self.trace_dir, "index.json")
        with open(index_path, "w", encoding="utf-8") as f:
            json.dump(self.trace_index, f, ensure_ascii=False, indent=2)

    def record_tick(
        self,
        tick_id: str,
        cycle: int,
        state_before: dict,
        state_after: dict,
        events_processed: list[dict],
        activated_memories: list[dict],
        drift_report: dict,
        plan_summary: str,
        compression_actions: list[str],
        reasoning_summary: str,
    ) -> str:
        """Record a single cognitive tick."""
        # Calculate state diff
        diff = {
            "goal_changed": state_before.get("current_goal") != state_after.get("current_goal"),
            "plan_changed": state_before.get("active_plan") != state_after.get("active_plan"),
            "observation_delta": (
                len(state_after.get("observations", [])) -
                len(state_before.get("observations", []))
            ),
            "goal_stability_delta": (
                state_after.get("metadata", {}).get("goal_stability_score", 1.0) -
                state_before.get("metadata", {}).get("goal_stability_score", 1.0)
            ),
        }

        trace_entry = {
            "tick_id": tick_id,
            "cycle": cycle,
            "timestamp": datetime.now().isoformat(),
            "observed_events": [e.get("type", "unknown") for e in events_processed],
            "event_count": len(events_processed),
            "activated_memories": [
                {"id": m.get("id"), "content": m.get("content", "")[:100], "score": m.get("relevance_score", 0)}
                for m in activated_memories
            ],
            "memory_activation_count": len(activated_memories),
            "state_diff": diff,
            "drift_report": {
                "overall_score": drift_report.get("overall_drift_score", 0),
                "detected_types": drift_report.get("drifts_detected", []),
            },
            "plan_summary": plan_summary,
            "compression_actions": compression_actions,
            "reasoning_summary": reasoning_summary,
        }

        # Write individual tick file
        tick_path = os.path.join(self.trace_dir, f"tick_{tick_id}.json")
        with open(tick_path, "w", encoding="utf-8") as f:
            json.dump(trace_entry, f, ensure_ascii=False, indent=2)

        # Update index
        self.trace_index["ticks"].append({
            "tick_id": tick_id,
            "cycle": cycle,
            "timestamp": datetime.now().isoformat(),
            "path": tick_path,
            "goal_changed": diff["goal_changed"],
            "drift_score": drift_report.get("overall_drift_score", 0),
        })
        self.trace_index["count"] += 1
        self._save_index()

        return tick_id

    def get_last_n_traces(self, n: int = 10) -> list[dict]:
        """Get the last N trace summaries."""
        ticks = self.trace_index.get("ticks", [])[-n:]
        traces = []
        for t in ticks:
            with open(t["path"], "r", encoding="utf-8") as f:
                traces.append(json.load(f))
        return traces

    def analyze_trend(self, last_n: int = 20) -> dict:
        """Analyze recent trace patterns."""
        traces = self.get_last_n_traces(last_n)
        if not traces:
            return {"status": "no_data"}

        goal_changes = sum(1 for t in traces if t.get("state_diff", {}).get("goal_changed"))
        avg_drift = sum(t.get("drift_report", {}).get("overall_score", 0) for t in traces) / len(traces)
        total_compressions = sum(len(t.get("compression_actions", [])) for t in traces)

        return {
            "analyzed_traces": len(traces),
            "goal_changes": goal_changes,
            "avg_drift_score": avg_drift,
            "total_compressions": total_compressions,
            "drift_trend": "increasing" if avg_drift > 0.3 else "stable" if avg_drift > 0.1 else "low",
        }


class StateSnapshot:
    """
    Periodic full state snapshots for long-term analysis.
    """

    def __init__(self, snapshot_dir: str = SNAPSHOT_DIR):
        self.snapshot_dir = snapshot_dir
        os.makedirs(snapshot_dir, exist_ok=True)

    def save_snapshot(self, state: dict, cycle: int, reason: str = "scheduled") -> str:
        """Save a complete world state snapshot."""
        snapshot_id = str(uuid.uuid4())[:8]
        filename = f"snapshot_c{cycle:04d}_{snapshot_id}.json"
        path = os.path.join(self.snapshot_dir, filename)

        snapshot = {
            "snapshot_id": snapshot_id,
            "cycle": cycle,
            "timestamp": datetime.now().isoformat(),
            "reason": reason,
            "state": state,
        }

        with open(path, "w", encoding="utf-8") as f:
            json.dump(snapshot, f, ensure_ascii=False, indent=2)

        return path

    def get_latest_snapshot(self) -> dict | None:
        """Get the most recent state snapshot."""
        if not os.path.exists(self.snapshot_dir):
            return None

        files = [
            f for f in os.listdir(self.snapshot_dir)
            if f.startswith("snapshot_") and f.endswith(".json")
        ]
        if not files:
            return None

        files.sort(reverse=True)
        with open(os.path.join(self.snapshot_dir, files[0]), "r", encoding="utf-8") as f:
            return json.load(f)

    def compare_snapshots(self, snap1_path: str, snap2_path: str) -> dict:
        """Compare two snapshots to analyze state evolution."""
        with open(snap1_path, "r", encoding="utf-8") as f:
            s1 = json.load(f)
        with open(snap2_path, "r", encoding="utf-8") as f:
            s2 = json.load(f)

        state1 = s1.get("state", {})
        state2 = s2.get("state", {})

        return {
            "snap1": {"cycle": s1.get("cycle"), "timestamp": s1.get("timestamp")},
            "snap2": {"cycle": s2.get("cycle"), "timestamp": s2.get("timestamp")},
            "cycles_elapsed": s2.get("cycle", 0) - s1.get("cycle", 0),
            "goal_changed": state1.get("current_goal") != state2.get("current_goal"),
            "goal_stability_change": (
                state2.get("metadata", {}).get("goal_stability_score", 1.0) -
                state1.get("metadata", {}).get("goal_stability_score", 1.0)
            ),
            "observation_count_change": (
                len(state2.get("observations", [])) -
                len(state1.get("observations", []))
            ),
        }
