# MCR Project Overview

MCR, or Memory-Augmented Cognitive Runtime, is a replayable memory runtime for long-running AI agents. It is designed as a research runtime artifact: small enough to inspect, deterministic enough to test, and explicit enough to show how memory state changes over time.

## What is MCR?

MCR is an event-sourced runtime kernel for agent memory state. It accepts structured events, validates them, writes them to a WAL, reduces them into runtime state, and verifies whether replay reconstructs the same state.

The central invariant is:

```text
runtime_state == replay(WAL)
```

This is the main difference between MCR and a normal demo script. MCR is not only interested in what state exists now. It is interested in whether that state can be reconstructed from a traceable history.

## Why does it exist?

Long-running agents accumulate state. That state may include memory items, access history, tier transitions, archive/purge events, and tool-driven updates. Without a runtime layer, it becomes hard to answer basic questions:

- Why does this memory exist?
- When did it change?
- Can the state be recovered after a crash?
- Did replay produce the same result?
- Did the LLM directly mutate state without validation?

MCR exists to make those questions testable.

## Core problem

The core problem is not only memory retrieval. It is memory state governance over time.

MCR focuses on:

- memory lifecycle traceability
- replayable state transitions
- event validation before state mutation
- crash recovery verification
- bounded demos that can be tested by external users

## Core idea

MCR uses a small event-sourced pipeline:

```text
Event -> EventGate -> WAL -> Reducer -> Runtime State -> ReplayVerifier
```

Each layer has a narrow responsibility. The LLM or bridge layer can propose events, but it does not own state. The runtime owns state transitions.

## System architecture

The main files are:

| File | Responsibility |
| --- | --- |
| `runtime/event_gate.py` | Validates proposals and rejects malformed events |
| `runtime/wal.py` | Stores accepted events as the source of truth |
| `runtime/reducer.py` | Applies event transitions to state |
| `runtime/state.py` | Holds runtime state and equality/hash logic |
| `runtime/engine.py` | Coordinates the runtime pipeline |
| `runtime/replay_verifier.py` | Replays WAL and checks state equivalence |
| `runtime/hermes_bridge.py` | Parses mock LLM output into event proposals |

## Runtime flow

```text
User / Agent Event
        |
        v
Event Gate
        |
        v
WAL
        |
        v
Reducer
        |
        v
Runtime State
        |
        v
Replay Verifier
        |
        v
PASS / FAIL
```

## What can it be used for?

MCR can be used for:

- learning event sourcing in an agent-memory context
- testing replayable memory state designs
- demonstrating WAL-based recovery
- evaluating event validation boundaries
- building small deterministic runtime experiments
- comparing snapshot-style state with replayable state

## What it is not

MCR is not:

- AGI
- an autonomous agent product
- a production-ready framework
- a chatbot framework
- a training system
- a complete memory database

## Current status

Current release: v0.9.3.

The project is demo-ready and regression-protected. It includes four demos, a verification script, GitHub Actions coverage, release notes, and onboarding documentation.

## Verification summary

The repository verifies:

- G2 replay determinism
- EventGate validation behavior
- HermesBridge proposal parsing
- full bridge/gate/WAL/reducer/replay integration
- archive and purge behavior
- replay hash integrity
- token leak regression checks

## Next milestones

Near-term milestones:

- improve external validation notes
- keep demo output stable
- expand known limitations
- improve replay mismatch diagnostics
- preserve the narrow runtime scope
