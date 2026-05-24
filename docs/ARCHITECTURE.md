# MCR Architecture

## 1. Event-sourced runtime kernel

MCR uses an event-sourced runtime kernel. State is not treated as an opaque snapshot. Instead, accepted events are written to a WAL and reduced into runtime state. The same WAL can be replayed to verify state reconstruction.

## 2. WAL


untime/wal.py provides the write-ahead log. It is the single source of truth for accepted runtime events.

## 3. Reducer


untime/reducer.py applies events to runtime state. The reducer is intended to be a pure state transition layer: given the same prior state and event sequence, replay should produce the same result.

## 4. Runtime state


untime/state.py defines the runtime state container. State is derived from accepted events rather than directly mutated by an LLM.

## 5. Replay verifier


untime/replay_verifier.py checks whether replaying the WAL reconstructs the expected runtime state. This is the G2 verification path.

## 6. Event gate


untime/event_gate.py validates incoming event proposals before they enter the WAL/reducer path. This keeps malformed or forbidden proposals outside the state transition path.

## 7. Hermes Bridge


untime/hermes_bridge.py demonstrates how LLM-like text can be parsed into structured proposals. It is a bridge layer, not a state authority. Hermes/LLM output must still pass the event gate.

## 8. Demo flow

`	ext
User / Agent Event
        ↓
Event Gate
        ↓
WAL
        ↓
Reducer
        ↓
Runtime State
        ↓
Replay Verifier
        ↓
PASS / FAIL
`

The demos in examples/ show this flow at different levels:

- examples/minimal_mcr.py: self-contained concept demo
- examples/quickstart.py: modular runtime demo
- examples/replay_verification_demo.py: replay hash verification
- examples/hermes_bridge_demo.py: mock LLM bridge demo

## 9. Why deterministic replay matters

Deterministic replay gives the runtime a way to verify whether memory state can be recovered from the event log. This matters for long-running agents because state drift, crashes, and memory lifecycle changes need to be auditable rather than inferred from a final snapshot.
