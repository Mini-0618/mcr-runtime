# MCR Event-Sourced Architecture Blueprint
# G2-Complete: WAL is Single Source of Truth
# Generated: 2026-05-23
# Version: blueprint_v1

# ============================================================
# DESIGN PRINCIPLE
# ============================================================
#
# INVARIANT: ALL runtime state MUST be derivable from WAL.
# No exceptions. No "runtime-only" state.
#
# Current system (BROKEN):
#   WAL → memory state (replayable)
#   runtime → access_history (NOT replayable) ← G2 root
#   runtime → coaccess_graph (NOT replayable) ← G2 root
#
# Target system (CORRECT):
#   WAL → deterministic reducer → FULL SYSTEM STATE
#
# ============================================================
# EVENT SCHEMA
# ============================================================

WALEvent = {
    seq: int,                    # monotonic, unique per instance
    tick: int,                   # logical tick
    event_id: str,               # uuid, for causal tracking
    type: str,                   # event type (see below)
    memory_id: str,
    payload: dict,               # type-specific delta

    # Causal tracking
    causal_group_id: str,        # groups events that happen at same tick
    prev_seq: int,              # previous event seq for this memory_id

    # Metadata
    checksum: str,              # adler32 for integrity
    timestamp: str,              # ISO 8601
}

EVENT TYPES (exhaustive):

1. MEMORY_STORE
   payload: {content, memory_type, importance, tags, layer, state}
   → Creates new memory in working layer

2. MEMORY_TRANSITION
   payload: {from_layer, to_layer, reason, access_count, importance}
   → Memory moves between layers

3. ACCESS_RECORD
   payload: {
       access_count_after: int,
       activation_count_after: int,
       last_access_tick: int,
       access_history_delta: list[int],  # NEW accesses added this tick
   }
   → Derivable: access_history = accumulated ACCESS_RECORD.access_history_delta

4. COACCESS_EDGE_ADD
   payload: {
       coaccess_pair: [str, str],   # [memory_id_a, memory_id_b]
       weight_after: float,
   }
   → Derivable: coaccess_graph edges = accumulated COACCESS_EDGE_ADD events

5. COACCESS_EDGE_REMOVE
   payload: {coaccess_pair: [str, str]}
   → Removes edge from coaccess graph

6. TOMBSTONE_CREATE
   payload: {reason, source_tier}
   → Marks memory as tombstoned

7. TOMBSTONE_PURGE
   payload: {reason}
   → Permanently removes memory + all coaccess edges

8. DECAY_APPLY
   payload: {
       affected_memory_ids: list[str],
       decay_factor: float,
       new_weights: dict[str, float],  # memory_id → new weight
   }

9. COMPACTION_TRIGGER
   payload: {
       topic: str,
       candidate_ids: list[str],
       action: "promote" | "archive" | "summarize",
       result_ids: list[str],
   }

# ============================================================
# FULL STATE STRUCTURE (derived from WAL)
# ============================================================

SystemState = {
    # Memory layers (rebuilt from MEMORY_STORE + TRANSITION events)
    memories: {
        memory_id: {
            id: str,
            content: str,
            memory_type: str,
            importance: float,
            tags: list[str],
            state: str,  # working | episodic | semantic | archive | tombstoned | purged
            layer: str,

            # Derived from ACCESS_RECORD events
            access_count: int,
            activation_count: int,
            last_access_tick: int,
            access_history: list[int],  # accumulated from ACCESS_RECORD.payload.access_history_delta

            # Derived from TRANSITION events
            promotion_history: list[dict],
            demotion_history: list[dict],
            last_state_change_tick: int,

            # Decay state
            current_weight: float,

            # Tombstone state
            tombstoned_at: int | None,
            purged_at: int | None,
        }
    },

    # Coaccess graph (rebuilt from COACCESS_EDGE_ADD / COACCESS_EDGE_REMOVE)
    coaccess_graph: {
        edges: {
            memory_id: {neighbor_id: weight}
        },
        # NOT a runtime cache — a derived view of WAL events
    },

    # Tombstone registry (rebuilt from TOMBSTONE_CREATE / TOMBSTONE_PURGE)
    tombstones: {
        memory_id: {tombstoned_at: int, reason: str, source_tier: str}
    },

    # Purged registry (rebuilt from TOMBSTONE_PURGE)
    purged: set[str],

    # System tick
    current_tick: int,

    # Sequence cursor
    last_seq: int,
}

# ============================================================
# DETERMINISTIC REDUCER (pure function)
# ============================================================
#
# state = reduce(wal_events: list[WALEvent], initial_state: SystemState) -> SystemState
#
# IMPORTANT: This is a PURE function. No side effects. No external reads.
# Every state mutation is derived from events, not from runtime.

def reduce_event(state: SystemState, event: WALEvent) -> SystemState:
    """
    Pure reducer. Returns NEW state (immutable updates).
    """
    handlers = {
        "MEMORY_STORE":          reduce_MEMORY_STORE,
        "MEMORY_TRANSITION":     reduce_MEMORY_TRANSITION,
        "ACCESS_RECORD":         reduce_ACCESS_RECORD,
        "COACCESS_EDGE_ADD":     reduce_COACCESS_EDGE_ADD,
        "COACCESS_EDGE_REMOVE": reduce_COACCESS_EDGE_REMOVE,
        "TOMBSTONE_CREATE":      reduce_TOMBSTONE_CREATE,
        "TOMBSTONE_PURGE":       reduce_TOMBSTONE_PURGE,
        "DECAY_APPLY":           reduce_DECAY_APPLY,
        "COMPACTION_TRIGGER":    reduce_COMPACTION_TRIGGER,
    }

    handler = handlers.get(event.type)
    if handler is None:
        return state  # Unknown event type — skip (fail gracefully)

    return handler(state, event)


def reduce_ACCESS_RECORD(state: SystemState, event: WALEvent) -> SystemState:
    """
    Rebuilds access_history as accumulated delta, not a runtime mutation.
    """
    mem_id = event.memory_id
    if mem_id not in state.memories:
        return state  # Memory was already purged — skip

    payload = event.payload

    # Rebuild access_history by appending delta (not replacing)
    old_history = state.memories[mem_id].get("access_history", [])
    new_history = old_history + payload.get("access_history_delta", [])

    # Cap access_history to MAX_ACCESS_HISTORY
    if len(new_history) > MAX_ACCESS_HISTORY:
        new_history = new_history[-MAX_ACCESS_HISTORY:]

    return state.update_in(
        ["memories", mem_id],
        {
            **state.memories[mem_id],
            "access_count": payload["access_count_after"],
            "activation_count": payload["activation_count_after"],
            "last_access_tick": payload["last_access_tick"],
            "access_history": new_history,
        }
    )


def reduce_COACCESS_EDGE_ADD(state: SystemState, event: WALEvent) -> SystemState:
    """
    Rebuilds coaccess graph from WAL events, not runtime mutations.
    """
    a, b = event.payload["coaccess_pair"]
    weight = event.payload["weight_after"]

    new_edges = dict(state.coaccess_graph.edges)
    if a not in new_edges:
        new_edges[a] = {}
    if b not in new_edges:
        new_edges[b] = {}
    new_edges[a][b] = weight
    new_edges[b][a] = weight

    return state.update_coaccess_graph({"edges": new_edges})


def reduce_COACCESS_EDGE_REMOVE(state: SystemState, event: WALEvent) -> SystemState:
    """
    Removes coaccess edge. Rebuilds from WAL, not runtime mutation.
    """
    a, b = event.payload["coaccess_pair"]

    new_edges = dict(state.coaccess_graph.edges)
    if a in new_edges and b in new_edges[a]:
        del new_edges[a][b]
    if b in new_edges and a in new_edges[b]:
        del new_edges[b][a]

    return state.update_coaccess_graph({"edges": new_edges})


def reduce_TOMBSTONE_CREATE(state: SystemState, event: WALEvent) -> SystemState:
    mem_id = event.memory_id
    payload = event.payload

    new_tombstones = dict(state.tombstones)
    new_tombstones[mem_id] = {
        "tombstoned_at": event.tick,
        "reason": payload["reason"],
        "source_tier": payload["source_tier"],
    }

    new_memories = dict(state.memories)
    if mem_id in new_memories:
        new_memories[mem_id] = {
            **new_memories[mem_id],
            "state": "tombstoned",
            "tombstoned_at": event.tick,
        }

    return SystemState(
        memories=new_memories,
        coaccess_graph=state.coaccess_graph,
        tombstones=new_tombstones,
        purged=state.purged,
        current_tick=event.tick,
        last_seq=event.seq,
    )


def reduce_TOMBSTONE_PURGE(state: SystemState, event: WALEvent) -> SystemState:
    """
    Permanently removes memory from ALL layers and cleans coaccess edges.
    """
    mem_id = event.memory_id

    # Remove from memories
    new_memories = {k: v for k, v in state.memories.items() if k != mem_id}

    # Remove from tombstones
    new_tombstones = {k: v for k, v in state.tombstones.items() if k != mem_id}

    # Add to purged
    new_purged = set(state.purged) | {mem_id}

    # Remove all coaccess edges involving this memory_id
    new_edges = {}
    for a, neighs in state.coaccess_graph.edges.items():
        if a == mem_id:
            continue
        new_neighs = {b: w for b, w in neighs.items() if b != mem_id}
        if new_neighs:
            new_edges[a] = new_neighs

    return SystemState(
        memories=new_memories,
        coaccess_graph={"edges": new_edges},
        tombstones=new_tombstones,
        purged=new_purged,
        current_tick=event.tick,
        last_seq=event.seq,
    )


# ============================================================
# REPLAY FUNCTION (pure)
# ============================================================

def replay_wal(wal_events: list[WALEvent], initial_state: SystemState) -> SystemState:
    """
    Pure WAL replay. Deterministic.
    Result is identical regardless of runtime environment.

    assert replay_wal(events, empty_state) == runtime_final_state
    """
    state = initial_state
    for event in sorted(wal_events, key=lambda e: (e.tick, e.seq)):
        state = reduce_event(state, event)
    return state


def verify_replay_equivalence(
    runtime_state: SystemState,
    replay_state: SystemState,
) -> tuple[bool, list[str]]:
    """
    Returns (pass, list_of_diffs).
    Compares all derivable state.
    """
    diffs = []

    # Memory IDs must match
    runtime_ids = set(runtime_state.memories.keys())
    replay_ids = set(replay_state.memories.keys())
    if runtime_ids != replay_ids:
        diffs.append(f"memory_ids mismatch: extra={runtime_ids - replay_ids}, missing={replay_ids - runtime_ids}")

    # For each memory, compare derivable fields
    for mid in runtime_ids & replay_ids:
        rm = runtime_state.memories[mid]
        pm = replay_state.memories[mid]

        if rm["state"] != pm["state"]:
            diffs.append(f"{mid}: state {rm['state']} != {pm['state']}")

        if rm["access_count"] != pm["access_count"]:
            diffs.append(f"{mid}: access_count {rm['access_count']} != {pm['access_count']}")

        if rm.get("tombstoned_at") != pm.get("tombstoned_at"):
            diffs.append(f"{mid}: tombstoned_at mismatch")

    # Coaccess graph
    if runtime_state.coaccess_graph.edges != replay_state.coaccess_graph.edges:
        diffs.append(f"coaccess_graph mismatch")

    # Tombstones
    if runtime_state.tombstones != replay_state.tombstones:
        diffs.append(f"tombstones mismatch")

    return (len(diffs) == 0, diffs)


# ============================================================
# IMMUTABLE STATE UPDATE HELPER
# ============================================================

class SystemState:
    """
    Immutable state object. All updates return new instance.
    Enables pure reducer pattern with simple equality comparison.
    """
    def __init__(self, memories, coaccess_graph, tombstones, purged, current_tick, last_seq):
        self.memories = memories
        self.coaccess_graph = coaccess_graph
        self.tombstones = tombstones
        self.purged = purged
        self.current_tick = current_tick
        self.last_seq = last_seq

    def update_in(self, path: list, value) -> "SystemState":
        """Immutable nested update. path like ['memories', memory_id]."""
        import copy
        new_state = copy.deepcopy(self)
        target = new_state
        for key in path[:-1]:
            target = target[key]
        target[path[-1]] = value
        return new_state

    def update_coaccess_graph(self, updates) -> "SystemState":
        import copy
        new_state = copy.deepcopy(self)
        new_state.coaccess_graph = {**new_state.coaccess_graph, **updates}
        return new_state


# ============================================================
# WAL MANAGER (unchanged — already correct)
# ============================================================
#
# The WALManager class is already correct.
# It handles atomic append, checksum, rotation, instance isolation.
# Only the EVENT SCHEMA needs to change (add new event types).
#
# Changes needed:
# 1. WALEntry schema: add event_id, causal_group_id, prev_seq, payload dict
# 2. WALManager.append(): accept payload dict instead of from_state/to_state
# 3. Add EVENT_TYPES constant
#
# The append() signature changes from:
#   append(tick, type, memory_id, from_state, to_state, reason)
# To:
#   append(tick, type, memory_id, payload: dict, reason)
#
# WALManager.replay() yields WALEntry — no change needed (already yields events).
#
# ============================================================
