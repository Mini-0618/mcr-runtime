"""
Adaptive Policy Layer — Phase IV-A
==================================

Bounded adaptive behavior for MCR:
- retrieval weight adaptation
- task routine persistence
- habit formation
- tool preference formation

All adaptive state stored externally (JSON file, WAL-compatible).
Zero writes to LayeredMemory layers.
Zero runtime self-rewrite.

CRITICAL CONSTRAINTS:
- Zero runtime self-rewrite
- Zero architecture mutation
- Zero governance generation
- Zero recursive self-modification
- Zero autonomous code overwrite
"""

import json
import os
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, List, Optional


# ── Adaptive State ────────────────────────────────────────────────────────────

@dataclass
class AdaptiveState:
    """Serializable adaptive state snapshot."""
    retrieval_weights: Dict[str, Dict] = field(default_factory=dict)
    habit_sequence: List[str] = field(default_factory=list)
    habit_counts: Dict[str, int] = field(default_factory=dict)
    adaptation_count: int = 0
    tick_of_last_adaptation: int = 0

    def to_dict(self) -> Dict:
        return {
            "retrieval_weights": self.retrieval_weights,
            "habit_sequence": self.habit_sequence[-20:],  # Last 20 steps
            "habit_counts": self.habit_counts,
            "adaptation_count": self.adaptation_count,
            "tick_of_last_adaptation": self.tick_of_last_adaptation,
        }

    @staticmethod
    def from_dict(d: Optional[Dict]) -> 'AdaptiveState':
        if not d:
            return AdaptiveState()
        return AdaptiveState(
            retrieval_weights=d.get("retrieval_weights", {}),
            habit_sequence=d.get("habit_sequence", []),
            habit_counts=d.get("habit_counts", {}),
            adaptation_count=d.get("adaptation_count", 0),
            tick_of_last_adaptation=d.get("tick_of_last_adaptation", 0),
        )


# ── Adaptive Policy ────────────────────────────────────────────────────────────

class AdaptivePolicy:
    """
    Bounded adaptive policy layer.

    Lives OUTSIDE LayeredMemory.
    State stored in a separate JSON file per runtime root.
    WAL-compatible via external file (not in memory layers).
    """

    # ── Constants ─────────────────────────────────────────────────────────────
    MAX_HABIT_WINDOW: int = 20      # Max steps in habit window
    WEIGHT_BOUNDS: tuple = (0.3, 3.0)  # Min/max retrieval weight
    ADAPTATION_INTERVAL: int = 50    # Feedbacks before weight adaptation
    SAVE_INTERVAL: int = 200         # Ticks before state file save

    def __init__(self, root: str):
        self._root: str = root
        self._feedback_buffer: List[Dict] = []
        self._habit_window: List[str] = []
        self._tick: int = 0
        self._adaptation_count: int = 0
        self._state: AdaptiveState = self._load()

    # ── Persistence ─────────────────────────────────────────────────────────
    def _state_file(self) -> str:
        return str(Path(self._root) / "adaptive_state.json")

    def _load(self) -> AdaptiveState:
        f = self._state_file()
        if os.path.exists(f):
            try:
                with open(f) as fh:
                    return AdaptiveState.from_dict(json.load(fh))
            except (json.JSONDecodeError, IOError):
                pass
        return AdaptiveState()

    def _save(self) -> None:
        with open(self._state_file(), "w") as fh:
            json.dump(self._state.to_dict(), fh)

    def force_save(self) -> None:
        """Force-save current state (call on runtime shutdown)."""
        self._save()

    # ── Tick ────────────────────────────────────────────────────────────────
    def tick(self, current_tick: int) -> None:
        self._tick = current_tick
        if current_tick % self.SAVE_INTERVAL == 0:
            self._save()

    # ── Step Recording ─────────────────────────────────────────────────────
    def record_step(self, step_name: str) -> None:
        """
        Record a step in the current task routine.
        Steps are windowed (last MAX_HABIT_WINDOW only).
        """
        self._habit_window.append(step_name)
        if len(self._habit_window) > self.MAX_HABIT_WINDOW:
            self._habit_window.pop(0)
        hc = dict(self._state.habit_counts)
        hc[step_name] = hc.get(step_name, 0) + 1
        self._state = AdaptiveState(
            retrieval_weights=self._state.retrieval_weights,
            habit_sequence=list(self._habit_window),
            habit_counts=hc,
            adaptation_count=self._adaptation_count,
            tick_of_last_adaptation=self._tick,
        )

    # ── Retrieval Feedback ──────────────────────────────────────────────────
    def record_retrieval_feedback(self, channel: str,
                                  relevance: float,
                                  was_useful: bool) -> None:
        """
        Record outcome of a retrieval from a given channel.

        channel: "working", "episodic", or "semantic"
        relevance: 0.0-1.0 relevance score from caller
        was_useful: bool, did caller find the results useful?
        """
        self._feedback_buffer.append({
            "channel": channel,
            "relevance": relevance,
            "was_useful": was_useful,
            "tick": self._tick,
        })
        if len(self._feedback_buffer) >= self.ADAPTATION_INTERVAL:
            self._adapt()

    # ── Adaptation ──────────────────────────────────────────────────────────
    def _adapt(self) -> None:
        """
        Process feedback buffer and update retrieval weights.
        Called automatically every ADAPTATION_INTERVAL feedbacks.
        """
        if not self._feedback_buffer:
            return

        rw = dict(self._state.retrieval_weights)
        for fb in self._feedback_buffer:
            ch = fb["channel"]
            if ch not in rw:
                rw[ch] = {"weight": 1.0, "count": 0, "success": 0}
            w = rw[ch]
            w["count"] += 1
            if fb["was_useful"]:
                w["success"] += 1

            # Weight update: success rate + relevance signal
            success_rate = w["success"] / max(1, w["count"])
            delta = (success_rate - 0.5) * 0.05 + (fb["relevance"] - 0.5) * 0.02
            w["weight"] = max(
                self.WEIGHT_BOUNDS[0],
                min(self.WEIGHT_BOUNDS[1], w["weight"] + delta)
            )

        self._feedback_buffer.clear()
        self._adaptation_count += 1
        self._state = AdaptiveState(
            retrieval_weights=rw,
            habit_sequence=self._state.habit_sequence,
            habit_counts=self._state.habit_counts,
            adaptation_count=self._adaptation_count,
            tick_of_last_adaptation=self._tick,
        )

    # ── Advice ───────────────────────────────────────────────────────────────
    def get_weights(self) -> Dict[str, float]:
        """
        Return current adaptive weights for retrieval channels.
        Returns {channel: weight} for all known channels.
        """
        result = {}
        for ch, w in self._state.retrieval_weights.items():
            result[ch] = w.get("weight", 1.0)
        # Always include all standard channels
        for ch in ["working", "episodic", "semantic"]:
            if ch not in result:
                result[ch] = 1.0
        return result

    def get_habit(self) -> Dict[str, int]:
        """Return habit counts (step_name → frequency)."""
        return self._state.habit_counts

    def get_adaptation_count(self) -> int:
        """Total number of adaptation events."""
        return self._adaptation_count

    def get_adaptation_summary(self) -> Dict:
        """Full human-readable adaptation state."""
        return {
            "weights": self.get_weights(),
            "habit": self.get_habit(),
            "adaptation_count": self.get_adaptation_count(),
            "tick_of_last_adaptation": self._state.tick_of_last_adaptation,
        }
