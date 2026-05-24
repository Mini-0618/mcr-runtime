# MCR Architecture

MCR is built around a small event-sourced runtime kernel. The architecture is intentionally narrow: validate events, append them to a WAL, reduce them into state, and verify replay.

## Architecture diagram

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

## 1. Event-sourced runtime kernel

The runtime does not treat state as an untraceable mutable object. Accepted events become the historical source of truth. State is derived by applying those events.

This matters because long-running agents can fail in ways that are hard to diagnose from a final snapshot. Event sourcing gives the runtime a history that can be replayed and inspected.

## 2. Event Gate

File: `runtime/event_gate.py`

The EventGate validates event proposals before they enter the state transition path. It is responsible for rejecting malformed or forbidden inputs. This keeps LLM-generated proposals outside the trusted core until they pass validation.

## 3. WAL

File: `runtime/wal.py`

The write-ahead log stores accepted events. In MCR, the WAL is the source of truth for replay. Runtime state should be reconstructable from the WAL.

## 4. Reducer

File: `runtime/reducer.py`

The reducer applies accepted events to runtime state. It is the state transition layer. The design goal is that a given event sequence produces the same state during replay.

## 5. Runtime state

File: `runtime/state.py`

Runtime state contains the derived memory state. It also supports equality and hashing behavior used by replay verification.

## 6. Runtime engine

File: `runtime/engine.py`

The engine coordinates event acceptance and state transition. It is the wrapper that connects EventGate, WAL, Reducer, State, and ReplayVerifier.

## 7. Replay verifier

File: `runtime/replay_verifier.py`

The ReplayVerifier checks whether the WAL reconstructs the expected state. It is the main mechanism for proving replay consistency.

## 8. Hermes Bridge

File: `runtime/hermes_bridge.py`

The HermesBridge is a mock LLM bridge. It parses LLM-like output into event proposals. It is not a state authority. Its output must still pass EventGate validation.

## 9. Demo flow

```text
examples/minimal_mcr.py
        |
        v
create events
        |
        v
write WAL
        |
        v
reduce state
        |
        v
replay WAL
        |
        v
compare state hashes
        |
        v
Result: PASS
```

## Trust boundaries

MCR separates proposal generation from state authority:

| Layer | Trusted to mutate state? | Role |
| --- | --- | --- |
| HermesBridge / LLM text | No | Produces candidate proposals |
| EventGate | No direct mutation | Validates proposals |
| WAL | Records accepted events | Source of truth |
| Reducer | Yes, through events | Applies state transitions |
| ReplayVerifier | No mutation | Checks reconstructability |

This boundary is the main safety property of the current architecture. LLM-like output is treated as input, not as runtime authority.

## Failure model

MCR is designed to make several failures visible:

- malformed proposal rejected by EventGate
- corrupted or changed WAL detected by replay/hash checks
- reducer mismatch exposed by replay verification
- missing demo dependency surfaced by verification script
- state drift exposed by hash/equality mismatch

It does not claim to prevent every possible failure. It gives the runtime a way to detect and localize important classes of state inconsistency.

## 10. Why deterministic replay matters

Deterministic replay gives the runtime an integrity check. If replay cannot reconstruct the same state, the runtime has evidence of drift, corruption, unsupported mutation, or nondeterministic behavior.

For long-running agents, this matters more than a single successful tool call. The runtime must be able to explain and recover its memory state over time.
