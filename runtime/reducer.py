"""
reducer.py — MCR Deterministic Reducer

Pure state transition function. Given the current state and an event, produces
the next state. No side effects, no randomness, no external calls.

    new_state = reduce(event, old_state)

Every handler returns a NEW state object. The input state is never modified.
This makes reducer calls replayable: replay(WAL) produces identical results
regardless of how many times WAL is replayed.

Event handlers:
  memory_store     → add memory to state.memory
  memory_access   → update access_history + coaccess_graph
  memory_archive  → change memory tier to archive
  memory_purge    → remove memory from state.memory
  policy_update   → no-op (gate validates, reducer accepts)
  *_noop          → no-op handlers for future event types
"""
from .state import SystemState
from .events import MCREvent


class DeterministicReducer:
    """Pure event reducer with typed handlers for each event type."""

    def __init__(self):
        self.handlers = {
            'memory_store': self._handle_store,
            'memory_access': self._handle_access,
            'memory_archive': self._handle_archive,
            'memory_purge': self._handle_purge,
            'policy_update': self._handle_policy,
            'curriculum_task_create': self._handle_noop,
            'curriculum_task_complete': self._handle_noop,
            'failure_record': self._handle_noop,
        }

    def reduce(self, event: MCREvent, state: SystemState) -> SystemState:
        """
        Pure reduce: returns a NEW state. Input state is never modified.
        """
        new_state = state.clone()
        new_state.tick = max(new_state.tick, event.tick)
        handler = self.handlers.get(event.event_type)
        if handler:
            new_state = handler(event, new_state)
        new_state.wal_length = state.wal_length + 1
        return new_state

    # -------------------------------------------------------------------------
    # Event handlers — all return new state
    # -------------------------------------------------------------------------

    def _handle_store(self, event: MCREvent, state: SystemState) -> SystemState:
        if not event.memory_id:
            return state
        state.memory[event.memory_id] = {
            'content': event.payload.get('content', ''),
            'tier': event.payload.get('tier', 'episodic'),
            'created_tick': event.tick,
        }
        return state

    def _handle_access(self, event: MCREvent, state: SystemState) -> SystemState:
        if event.memory_id not in state.memory:
            return state
        state.access_history.append({
            'memory_id': event.memory_id,
            'tick': event.tick,
            'coaccess_group_id': event.coaccess_group_id,
        })
        group_members = [
            e for e in state.access_history
            if e['coaccess_group_id'] == event.coaccess_group_id
            and e['tick'] == event.tick
            and e['memory_id'] != event.memory_id
        ]
        for m in group_members:
            mid = m['memory_id']
            if event.memory_id not in state.coaccess_graph:
                state.coaccess_graph[event.memory_id] = set()
            if mid not in state.coaccess_graph:
                state.coaccess_graph[mid] = set()
            state.coaccess_graph[event.memory_id].add(mid)
            state.coaccess_graph[mid].add(event.memory_id)
        return state

    def _handle_archive(self, event: MCREvent, state: SystemState) -> SystemState:
        if event.memory_id in state.memory:
            state.memory[event.memory_id]['tier'] = 'archive'
        return state

    def _handle_purge(self, event: MCREvent, state: SystemState) -> SystemState:
        if event.memory_id in state.memory:
            del state.memory[event.memory_id]
        return state

    def _handle_policy(self, event: MCREvent, state: SystemState) -> SystemState:
        """policy_update is validated by gate but has no state-side effect."""
        return state

    def _handle_noop(self, event: MCREvent, state: SystemState) -> SystemState:
        """No-op handler for gate-validated but state-neutral event types."""
        return state