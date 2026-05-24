# MCR Architecture

## Event-sourced runtime kernel

MCR's runtime kernel is event-sourced: every state transition is recorded as an immutable event in a Write-Ahead Log (WAL). State is derived by replaying events from initial state.

This gives three properties simultaneously:
1. **Replayability** — any past state can be reconstructed
2. **Determinism** — WAL replay from identical initial state always produces identical state
3. **Verifiability** — G2 kernel asserts `runtime_state == replay(WAL)` at checkpoints

## Core components

```
runtime/
├── wal.py              # Append-only event journal
├── state.py            # Runtime state: tiers, access history, coaccess graph
├── reducer.py          # Pure function: Event × State → State
├── engine.py           # Engine: WAL → Reducer → State orchestration
├── event_gate.py       # Validates proposals before WAL write
├── hermes_bridge.py    # Parses LLM output → EventProposal list
└── replay_verifier.py  # G2 deterministic replay checker
```

## ASCII architecture

```
User / Agent Event
       │
       ▼
  Event Gate
  (validate proposal)
       │
       ▼
      WAL
  (append-only)
       │
       ▼
   Reducer
  (pure: Event × State → State)
       │
       ▼
 Runtime State
  (current memory state)
       │
       ▼
 Replay Verifier
  (G2: runtime == replay?)
       │
       ▼
   PASS / FAIL
```

## WAL

The WAL is an append-only JSONL file. Each line is one event:

```json
{"seq": 1, "tick": 1, "type": "memory_store", "memory_id": "mem_001", "payload": {...}, "timestamp": 1234567890.123}
```

WAL invariants:
- No in-place mutation after write
- Events ordered by sequence number
- WAL path is deterministic per runtime instance

## Reducer

The reducer is a pure function:
```
reduce(state, event) → new_state
```

No side effects. Given identical (state, event) pair, always produces identical new_state.

## Runtime state

`state.py` defines `SystemState`:
- `memory`: dict of `MemoryItem` by id
- `tick`: current logical tick
- `access_history`: recent access list (capped)
- `coaccess_graph`: coaccess relationships between memory items
- `wal_length`: number of events in WAL

## Replay verifier

`replay_verifier.py` implements G2:

```
G2: runtime_state == replay(WAL)
```

Algorithm:
1. Take a snapshot of current runtime state
2. Create a fresh empty initial state
3. Replay entire WAL into the initial state
4. Compare resulting state hash to runtime state hash
5. If equal → G2 PASS. If not equal → divergence detected.

## Event gate

`event_gate.py` validates event proposals before WAL write:

- Checks event format and required fields
- Validates coaccess_group_id format
- Blocks malformed or unauthorized proposals

The event gate is the input filter; WAL is the output log.

## Hermes Bridge

`hermes_bridge.py` is an adapter that parses LLM text output into structured `EventProposal` objects:

```
LLM text output → JSON parse → EventProposal list → Event Gate → WAL → Reducer
```

This is NOT an AGI. It is an integration adapter that bridges LLM tool-use recommendations into the MCR event stream.

## Demo flow

Each demo shows a different entry point into the architecture:

| Demo | Entry point |
|------|-------------|
| minimal_mcr.py | WAL → Reducer → State → Replay (self-contained, ~200 lines) |
| quickstart.py | Full engine: Event → WAL → Reducer → State → Replay (modular) |
| replay_verification_demo.py | Replay verifier in isolation |
| hermes_bridge_demo.py | Hermes Bridge → Event Gate → WAL → Reducer |

## Why deterministic replay matters

1. **Debugging** — replay a failed run to exactly reproduce the failure
2. **Auditing** — reconstruct state history for any point in time
3. **Verification** — G2 guarantees runtime state integrity
4. **Crash recovery** — WAL replay restores exact pre-crash state
5. **Time-travel** — inspect state at any historical tick