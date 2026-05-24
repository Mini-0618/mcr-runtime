# MCR Project Overview

## 1. What is MCR?

MCR, or Memory-Augmented Cognitive Runtime, is a replayable memory runtime for long-running AI agents. It focuses on runtime state verification rather than model training, chatbot behavior, or autonomous agent claims.

## 2. Why does it exist?

Long-running agents need more than a prompt history. Their memory state changes over time, and those changes need to be traceable, recoverable, and testable. Without a runtime layer, memory state can drift, grow without bounds, or become unrecoverable after a crash.

## 3. Core problem

The core problem is long-running agent memory state:

- memory can grow without a lifecycle
- retrieval behavior can drift over time
- state changes may not be attributable
- crash recovery may produce unverifiable state
- demos may work once but fail to prove replayability

## 4. Core idea

MCR uses an event-sourced architecture:

`	ext
Event -> WAL -> Reducer -> Runtime State -> Replay Verification
`

Every accepted state transition is represented as an event, written to a write-ahead log, reduced into runtime state, and checked through deterministic replay.

## 5. System architecture

The current runtime consists of:

-
untime/event_gate.py for event validation
-
untime/wal.py for append-only event storage
-
untime/reducer.py for pure state transitions
-
untime/state.py for runtime state
-
untime/engine.py for runtime orchestration
-
untime/replay_verifier.py for replay verification
-
untime/hermes_bridge.py for mock LLM proposal parsing

## 6. Runtime flow

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

## 7. What can it be used for?

MCR can be used to study:

- replayable agent memory state
- event-sourced memory lifecycle tracking
- deterministic replay verification
- mock LLM proposal routing through a validation layer
- regression-protected runtime demos

## 8. What it is not

MCR is not:

- AGI
- a production-ready agent framework
- a chatbot framework
- a model training system
- a replacement for a database

## 9. Current status

Current release: v0.9.3. The project is a research runtime artifact with demos, regression tests, and an external onboarding path.

## 10. Next milestones

Near-term milestones:

- improve documentation clarity
- strengthen external validation flow
- keep demos stable
- keep replay verification regression-protected
- document known limitations clearly
