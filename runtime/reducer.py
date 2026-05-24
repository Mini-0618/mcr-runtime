"""
Reducer — Pure State Transition Function (ONLY path for state mutation)
"""
import hashlib
from typing import Dict, Any
from .state import SystemState
from .wal import Event


class DeterministicReducer:
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

    def reduce(self, event: Event, state: SystemState) -> SystemState:
        new_state = state.clone()
        new_state.tick = max(new_state.tick, event.tick)

        if event.event_type in self.handlers:
            new_state = self.handlers[event.event_type](event, new_state)

        new_state.wal_length = state.wal_length + 1
        return new_state

    def _handle_store(self, event: Event, state: SystemState) -> SystemState:
        if not event.memory_id:
            return state
        payload = event.payload
        state.memory[event.memory_id] = {
            'content': payload.get('content', ''),
            'tier': payload.get('tier', 'episodic'),
            'created_tick': event.tick,
        }
        return state

    def _handle_access(self, event: Event, state: SystemState) -> SystemState:
        if event.memory_id not in state.memory:
            return state

        # update access_history
        state.access_history.append({
            'memory_id': event.memory_id,
            'tick': event.tick,
            'coaccess_group_id': event.coaccess_group_id,
        })

        # update coaccess graph
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

    def _handle_archive(self, event: Event, state: SystemState) -> SystemState:
        if event.memory_id in state.memory:
            state.memory[event.memory_id]['tier'] = 'archive'
        return state

    def _handle_purge(self, event: Event, state: SystemState) -> SystemState:
        if event.memory_id in state.memory:
            del state.memory[event.memory_id]
        return state

    def _handle_policy(self, event: Event, state: SystemState) -> SystemState:
        return state

    # No-op handler for event types that are validated by EventGate but have
    # no state-side effect yet (curriculum_task_create, curriculum_task_complete,
    # failure_record). Defined in ALLOWED_EVENT_TYPES and EVENT_SCHEMAS; must
    # be in handlers to avoid silent fall-through.
    def _handle_noop(self, event: Event, state: SystemState) -> SystemState:
        return state
