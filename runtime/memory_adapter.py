"""
memory_adapter.py — Bridge stable/ LayeredMemory into runtime/ reducer system

Connects the 4-tier memory lifecycle (working → episodic → semantic → archive)
to the G2 event-sourced kernel. The adapter is injected into the reducer as an
optional dependency — when absent, the reducer falls back to simple dict operations.

Design:
  - Adapter wraps LayeredMemory (from stable/)
  - Each handler returns a new SystemState (immutable-clone model preserved)
  - _sync_to_state() copies LayeredMemory tiers back to state.memory dict
  - LayeredMemory file persistence is independent of runtime/ WAL

Usage:
  adapter = LayeredMemoryAdapter("/path/to/memory_store")
  reducer = DeterministicReducer(memory_adapter=adapter)
  engine = MCRRuntimeEngine(memory_adapter=adapter)
"""
import sys
import os
from pathlib import Path
from typing import Optional

# Ensure stable/ is importable for LayeredMemory
_stable_dir = str(Path(__file__).resolve().parents[1] / "stable")
if _stable_dir not in sys.path:
    sys.path.insert(0, _stable_dir)


class LayeredMemoryAdapter:
    """Bridges stable/ LayeredMemory into runtime/ reducer system."""

    def __init__(self, base_path: str, max_working: int = 10):
        from layered_memory import LayeredMemory
        self._lm = LayeredMemory(base_path, max_working=max_working)

    def store(self, state, event):
        """memory_store event → LayeredMemory.store() + sync to state.
        Respects event's tier field for G2 consistency with basic reducer."""
        event_tier = event.payload.get('tier', 'working')
        self._lm.store(
            content=event.payload.get('content', ''),
            memory_type=event.payload.get('memory_type', 'general'),
            importance=event.payload.get('importance', 0.5),
            tags=event.payload.get('tags'),
            current_tick=event.tick,
            memory_id=event.memory_id,
        )
        # If event specifies a tier different from 'working', move the memory
        if event_tier != 'working':
            mem_id = event.memory_id
            for m in self._lm.working:
                if m['id'] == mem_id:
                    self._lm.working = [x for x in self._lm.working if x['id'] != mem_id]
                    m['state'] = event_tier
                    m['last_state_change_tick'] = event.tick
                    if event_tier == 'episodic':
                        self._lm.episodic.append(m)
                    elif event_tier == 'semantic':
                        self._lm.semantic.append(m)
                    elif event_tier == 'archive':
                        self._lm.archive.append(m)
                    self._lm._mark_dirty('working')
                    self._lm._mark_dirty(event_tier)
                    break
        return self._sync_to_state(state)

    def access(self, state, event):
        """memory_access event → LayeredMemory.access_memory() + coaccess tracking."""
        if not event.memory_id:
            return state
        mem = self._lm.access_memory(event.memory_id, event.tick)
        if mem is None:
            return state

        # Record in access_history (same logic as reducer._handle_access)
        state.access_history.append({
            'memory_id': event.memory_id,
            'tick': event.tick,
            'coaccess_group_id': event.coaccess_group_id,
        })

        # Coaccess graph: find other memories accessed in same group+tick
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

        return self._sync_to_state(state)

    def archive(self, state, event):
        """memory_archive event → move memory to archive tier."""
        if not event.memory_id:
            return state
        # Find the memory across all tiers and force it to archive
        for tier_name in ('working', 'episodic', 'semantic'):
            tier = self._lm.get_layer(tier_name)
            for mem in tier:
                if mem['id'] == event.memory_id:
                    old_state = mem.get('state', tier_name)
                    mem['state'] = 'archive'
                    mem['last_state_change_tick'] = event.tick
                    # Remove from current tier, add to archive
                    tier.remove(mem)
                    self._lm.archive.append(mem)
                    self._lm._mark_dirty(tier_name)
                    self._lm._mark_dirty('archive')
                    # Log transition
                    self._lm._log_transition(
                        event.memory_id, old_state, 'archive',
                        'memory_archive_event', event.tick
                    )
                    return self._sync_to_state(state)
        return self._sync_to_state(state)

    def purge(self, state, event):
        """memory_purge event → remove memory from all tiers."""
        if not event.memory_id:
            return state
        for tier_name in ('working', 'episodic', 'semantic', 'archive'):
            tier = self._lm.get_layer(tier_name)
            for mem in tier[:]:  # copy list to allow removal
                if mem['id'] == event.memory_id:
                    tier.remove(mem)
                    self._lm._mark_dirty(tier_name)
                    self._lm._log_transition(
                        event.memory_id, tier_name, 'DELETED',
                        'memory_purge_event', event.tick
                    )
                    return self._sync_to_state(state)
        return self._sync_to_state(state)

    def lifecycle_tick(self, state, tick):
        """Run lifecycle operations: decay buffer, incremental review, flush."""
        self._lm.process_decay_buffer(tick)
        self._lm.incremental_review(tick)
        self._lm.try_flush(tick)
        return self._sync_to_state(state)

    def retrieve(self, query, goal, tick, max_results=5, goal_history=None):
        """Retrieve from LayeredMemory (read-only, no state mutation)."""
        return self._lm.retrieve(query, goal, tick, max_results, goal_history or [])

    def _sync_to_state(self, state):
        """Sync LayeredMemory tiers back to state.memory dict.
        Matches basic reducer format: content, tier, created_tick only."""
        state.memory.clear()
        for tier_name in ('working', 'episodic', 'semantic', 'archive'):
            for mem in self._lm.get_layer(tier_name):
                state.memory[mem['id']] = {
                    'content': mem.get('content', ''),
                    'tier': tier_name,
                    'created_tick': mem.get('created_tick', 0),
                }
        return state

    def summary(self):
        """Return LayeredMemory summary stats."""
        return self._lm.summary()
