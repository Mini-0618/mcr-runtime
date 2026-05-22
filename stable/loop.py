"""
Cognitive Loop
The heart of MCR - never truly stops
"""
import json
import os
import sys
import uuid
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import (
    BASE_DIR, STATE_FILE, EVENT_FILE, TRACE_DIR, SNAPSHOT_DIR,
    MAX_EVENTS_PER_TICK, MAX_ACTIVE_MEMORIES, SNAPSHOT_EVERY,
    COMPRESSION_TRIGGERS, REVIEW_INTERVAL, SEMANTIC_RETRIEVAL_K
)
from world_state import load_state, save_state, update_goal, add_observation, update_plan, compress_observations
from event_system import EventQueue, EventType, create_event
from layered_memory import LayeredMemory, MAX_ACTIVE_PER_TICK
from drift import DriftDetector
from observability import CognitiveTrace, StateSnapshot
from stability import MemoryImmune, ReasoningVaccine, AttentionAnchor, SurvivalTriggers


# Backward-compat adapter for code that expects flat .memories list
class MemoryAdapter:
    """
    Wraps LayeredMemory to provide MemoryStore-compatible interface.
    Exposes .memories (all tiers flattened) for legacy code (stability mechanisms).
    New code should use LayeredMemory APIs directly.
    """
    def __init__(self, layered_memory: LayeredMemory):
        self._lm = layered_memory

    @property
    def memories(self) -> list:
        """Flatten all tiers into one list (for backward-compat only)."""
        return (
            self._lm.working
            + self._lm.episodic
            + self._lm.semantic
            + self._lm.archive
        )

    def store(self, content: str, memory_type: str = "general",
              importance: float = 0.5, tags: list = None,
              current_tick: int = 0) -> str:
        return self._lm.store(content, memory_type, importance, tags, current_tick)

    def retrieve(self, query: str, max_results: int = 5,
                 min_importance: float = 0.0,
                 current_goal: str = "", current_tick: int = 0,
                 goal_history: list = None) -> list:
        # LayeredMemory handles its own scoring; min_importance is ignored
        return self._lm.retrieve(query, current_goal, current_tick,
                                  max_results, goal_history or [])

    def prune_low_value(self, min_importance: float = 0.2) -> int:
        """Bulk prune on flat list — calls incremental review to achieve similar effect."""
        # Trigger one incremental review pass to move low-value items
        before = len(self.memories)
        self._lm.incremental_review(current_tick=0)
        after = len(self.memories)
        return before - after

    def get_active_count(self) -> int:
        return len(self._lm.working) + len(self._lm.episodic)


class CognitiveLoop:
    """
    Core cognitive loop - runs continuously via cron.
    
    Loop structure:
    1. observe()      - read events
    2. update_world() - update world state
    3. detect_changes() - check what changed
    4. retrieve_memory() - activate relevant memories
    5. reason()       - generate reasoning
    6. plan()         - update plan
    7. execute()      - execute planned actions
    8. reflect()      - self-check
    9. compress()     - clean state if needed
    10. continue       - loop
    """

    def __init__(self):
        self.state = load_state(STATE_FILE)
        self.events = EventQueue(EVENT_FILE)

        # Layered memory with adapter for backward-compat
        layered = LayeredMemory(BASE_DIR)
        self.memory = MemoryAdapter(layered)
        self._layered = layered  # direct access for new APIs

        self.drift_detector = DriftDetector(STATE_FILE)
        self.trace = CognitiveTrace(TRACE_DIR)
        self.snapshot = StateSnapshot(SNAPSHOT_DIR)

        # 抗退化稳定性机制 (use adapter.memories for flat list)
        self.memory_immune = MemoryImmune(self.memory)
        self.reasoning_vaccine = ReasoningVaccine(self.state)
        self.attention_anchor = AttentionAnchor(self.state)
        self.survival_triggers = SurvivalTriggers(self.state, self.memory, self.events)

        self.tick_count = self.state.get("metadata", {}).get("tick_count", 0)
        self.tick_id = str(uuid.uuid4())[:8]
        self._last_review_tick = 0

    def run_cycle(self) -> dict:
        """Execute one complete cognitive cycle."""
        cycle_start = datetime.now()
        self.tick_count += 1
        self.tick_id = str(uuid.uuid4())[:8]
        
        # Capture state before
        state_before = self._deep_copy(self.state)
        
        # Step 1: Observe - get events
        events = self.events.pop(MAX_EVENTS_PER_TICK)
        event_types = [self._event_get_type(e) for e in events]
        
        # Step 2: Update world state from events
        self._process_events(events)
        
        # Step 3: Detect changes
        changes = self._detect_changes(state_before, self.state)
        
        # Step 4: Retrieve relevant memories (new API: needs goal + tick)
        query = self.state.get("current_goal", "") or self.state.get("context_summary", "")
        goal_history = self.state.get("goal_history", [])
        activated_memories = self.memory.retrieve(
            query=query,
            max_results=MAX_ACTIVE_MEMORIES,
            current_goal=query,
            current_tick=self.tick_count,
            goal_history=goal_history,
        )

        # Step 5: Reason
        reasoning_summary = self._reason(activated_memories, events, changes)
        
        # Step 6: Plan
        plan_summary = self._plan()
        
        # Step 7: Execute (process pending actions)
        execution_notes = self._execute()
        
        # Step 8: Reflect
        reflection = self._reflect()
        
        # Compression
        compression_actions = self._maybe_compress()

        # --- New memory lifecycle integration ---
        # Process decay buffer every tick
        decay_result = self._layered.process_decay_buffer(self.tick_count)

        # Incremental review (replaces periodic_review spike)
        review_actions = self._layered.incremental_review(self.tick_count)
        self._last_review_tick = self.tick_count

        # Batching persistence — flush at end of cycle
        flushed = self._layered.try_flush(self.tick_count)
        # ---------------------------------------

        # Stability mechanisms - anti-cognitive-entropy
        memory_immune_report = self.memory_immune.immune_check()
        vaccine_report = self.reasoning_vaccine.vaccine_check()
        anchor_report = self.attention_anchor.anchor_check()
        survival = self.survival_triggers.check_triggers()

        # Save updated state
        self.state["metadata"]["tick_count"] = self.tick_count
        save_state(STATE_FILE, self.state)
        self.events.save()
        
        # Drift detection
        drift_report = self.drift_detector.detect_all(self.state, events)
        
        # Record trace
        self.trace.record_tick(
            tick_id=self.tick_id,
            cycle=self.tick_count,
            state_before=state_before,
            state_after=self.state,
            events_processed=[self._event_to_dict(e) for e in events],
            activated_memories=activated_memories,
            drift_report=drift_report,
            plan_summary=plan_summary,
            compression_actions=compression_actions,
            reasoning_summary=reasoning_summary,
        )
        
        # Periodic snapshot
        if self.tick_count % SNAPSHOT_EVERY == 0:
            self.snapshot.save_snapshot(self.state, self.tick_count, reason="periodic")
        
        cycle_duration = (datetime.now() - cycle_start).total_seconds()
        
        # Execute survival actions if needed
        if survival.get("has_survival_action"):
            for action, params in survival.get("decisions", []):
                self.survival_triggers.execute_survival(action, params)

        return {
            "tick_id": self.tick_id,
            "cycle": self.tick_count,
            "duration_seconds": cycle_duration,
            "events_processed": len(events),
            "event_types": event_types,
            "activated_memories": len(activated_memories),
            "drift_score": drift_report.get("overall_drift_score", 0),
            "drifts_detected": drift_report.get("drifts_detected", []),
            "compression_actions": compression_actions,
            "changes": changes,
            "memory": {
                "working": len(self._layered.working),
                "episodic": len(self._layered.episodic),
                "semantic": len(self._layered.semantic),
                "archive": len(self._layered.archive),
                "flush_triggered": flushed,
                "decay_revived": len(decay_result.get("revived", [])),
                "decay_deleted": len(decay_result.get("deleted", [])),
                "review_promoted": len(review_actions.get("promoted_to_semantic", [])),
                "review_archived": len(review_actions.get("archived", [])),
            },
            "stability": {
                "memory_immune": memory_immune_report,
                "reasoning_vaccine": vaccine_report,
                "attention_anchor": anchor_report,
                "survival_triggered": survival.get("has_survival_action", False),
            },
        }

    def _event_to_dict(self, e) -> dict:
        """Convert Event object or dict to dict."""
        if hasattr(e, 'to_dict'):
            return e.to_dict()
        return e if isinstance(e, dict) else {}

    def _event_get_type(self, e) -> str:
        """Get event type from Event object or dict."""
        if hasattr(e, 'type'):
            et = e.type
            return et.value if hasattr(et, 'value') else str(et)
        return e.get("type", "") if isinstance(e, dict) else ""

    def _deep_copy(self, obj: dict) -> dict:
        """Create a deep copy of state."""
        return json.loads(json.dumps(obj))

    def _process_events(self, events: list) -> None:
        """Process events and update world state."""
        for event in events:
            if not hasattr(event, 'type'):
                continue
                
            event_type = event.type
            payload = event.payload
            
            if event_type == EventType.USER_INPUT:
                self.state = add_observation(self.state, payload.get("content", ""), "user")
                
            elif event_type == EventType.GOAL_CREATED:
                new_goal = payload.get("goal", "")
                self.state = update_goal(self.state, new_goal, "goal_created")
                
            elif event_type == EventType.GOAL_UPDATED:
                new_goal = payload.get("goal", "")
                reason = payload.get("reason", "goal_updated")
                self.state = update_goal(self.state, new_goal, reason)
                
            elif event_type == EventType.OBSERVATION_ADDED:
                obs = payload.get("content", "")
                source = payload.get("source", "system")
                self.state = add_observation(self.state, obs, source)
                
            elif event_type == EventType.PLAN_UPDATED:
                plan = payload.get("plan", {})
                self.state = update_plan(self.state, plan)
                
            elif event_type == EventType.TASK_COMPLETED:
                task = payload.get("task", "")
                self.state = add_observation(self.state, f"Task completed: {task}", "execution")
                
            elif event_type == EventType.TASK_FAILED:
                task = payload.get("task", "")
                error = payload.get("error", "")
                self.state = add_observation(self.state, f"Task failed: {task} - {error}", "execution")

    def _detect_changes(self, before: dict, after: dict) -> dict:
        """Detect what changed between cycles."""
        return {
            "goal_changed": before.get("current_goal") != after.get("current_goal"),
            "plan_changed": before.get("active_plan") != after.get("active_plan"),
            "new_observations": len(after.get("observations", [])) - len(before.get("observations", [])),
            "goal_stability_delta": (
                after.get("metadata", {}).get("goal_stability_score", 1.0) -
                before.get("metadata", {}).get("goal_stability_score", 1.0)
            ),
        }

    def _reason(self, memories: list, events: list, changes: dict) -> str:
        """Generate reasoning summary for this cycle."""
        reasoning_parts = []
        
        if changes.get("goal_changed"):
            reasoning_parts.append("Goal changed this cycle")
        
        if memories:
            reasoning_parts.append(f"Activated {len(memories)} relevant memories")
        
        if events:
            reasoning_parts.append(f"Processed {len(events)} events")
            
        drift_trend = self.drift_detector.get_drift_trend(5)
        if drift_trend.get("trend") == "increasing":
            reasoning_parts.append("WARNING: Drift trend increasing")
        
        # Store reasoning in state
        reasoning_text = "; ".join(reasoning_parts) if reasoning_parts else "No significant reasoning this cycle"
        
        self.state.setdefault("reasoning_chain", [])
        self.state["reasoning_chain"].append({
            "cycle": self.tick_count,
            "summary": reasoning_text,
            "timestamp": datetime.now().isoformat(),
        })
        self.state["reasoning_chain"] = self.state["reasoning_chain"][-20:]  # Keep last 20
        
        return reasoning_text

    def _plan(self) -> str:
        """Update plan based on current state."""
        current_goal = self.state.get("current_goal")
        
        if not current_goal:
            return "No active goal - waiting"
        
        # If no active plan, create one
        if not self.state.get("active_plan"):
            self.state = update_plan(self.state, {
                "goal": current_goal,
                "steps": [],
                "created_at": datetime.now().isoformat(),
            })
            return f"Created new plan for: {current_goal}"
        
        return f"Continuing plan: {self.state['active_plan'].get('goal', 'unknown')}"

    def _execute(self) -> list[str]:
        """Execute planned actions."""
        # Placeholder for actual execution
        # In real implementation, this would trigger tools, write files, etc.
        return []

    def _reflect(self) -> dict:
        """Self-reflection on current state."""
        reflection = {
            "tick_count": self.tick_count,
            "goal_stability": self.state.get("metadata", {}).get("goal_stability_score", 1.0),
            "memory_count": len(self.memory.memories),
            "observation_count": len(self.state.get("observations", [])),
            "drift_trend": self.drift_detector.get_drift_trend(5),
        }
        
        # Add warning if needed
        warnings = []
        if reflection["goal_stability"] < 0.5:
            warnings.append("Low goal stability")
        if reflection["observation_count"] > 40:
            warnings.append("High observation count - consider compression")
            
        reflection["warnings"] = warnings
        
        return reflection

    def _maybe_compress(self) -> list[str]:
        """Compress state if triggers are met."""
        actions = []
        
        # Check compression triggers
        event_queue_size = self.events.size()
        observation_count = len(self.state.get("observations", []))
        memory_count = len(self.memory.memories)
        
        if event_queue_size > COMPRESSION_TRIGGERS["event_queue_size"]:
            self.events.queue = self.events.queue[-COMPRESSION_TRIGGERS["event_queue_size"]//2:]
            actions.append(f"Compressed event queue: {event_queue_size} -> {len(self.events.queue)}")
            self.events.save()
        
        if observation_count > COMPRESSION_TRIGGERS.get("context_length", 8000) // 100:
            self.state = compress_observations(self.state)
            actions.append(f"Compressed observations: {observation_count}")
        
        if memory_count > COMPRESSION_TRIGGERS["memory_size"]:
            pruned = self.memory.prune_low_value()
            actions.append(f"Pruned {pruned} low-value memories")
        
        return actions


def main():
    """Entry point for cron-driven tick."""
    loop = CognitiveLoop()
    result = loop.run_cycle()
    
    # Output result for logging
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
