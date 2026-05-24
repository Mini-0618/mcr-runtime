# MCR Project Overview

## 1. What is MCR?

MCR (Memory-Augmented Cognitive Runtime) is a replayable memory runtime for long-running AI agents. It implements an event-sourced kernel with deterministic replay verification.

Core loop:
```
Event → WAL → Reducer → Runtime State → Replay Verification
```

## 2. Why does it exist?

Long-running AI agents face fundamental problems that standard memory designs don't address:

- **Memory explosion**: flat-list memory grows unbounded, retrieval slows over time
- **Retrieval drift**: retrieval quality degrades as context window fills
- **State unrecoverability**: crashes lose in-progress state with no verification
- **Unobservable lifecycle**: no visibility into what was evicted, when, and why
- **No replay guarantee**: no way to verify that reconstructed state is correct

MCR provides a bounded-retrieval substrate with full state replayability.

## 3. Core problem

Standard memory stores grow with agent lifetime. Vector DB + RAG optimizes for recall quality, not retrieval speed. Latency has no upper bound.

MCR's bounded retrieval theorem: given fixed W (working cap), CAP (episodic cap), K (retrieval candidates), retrieval complexity is O(W+CAP+K) — independent of agent lifetime T.

## 4. Core idea

Every state transition (store/evict/promote/archive) is logged to a Write-Ahead Log. The G2 deterministic replay kernel can reconstruct any past state by replaying WAL events from initial state.

If runtime state ≠ replayed state at any checkpoint, the system detects the divergence.

## 5. System architecture

```
runtime/
├── wal.py              # Write-Ahead Log — append-only event journal
├── state.py            # Runtime state: memory tiers, access history, coaccess graph
├── reducer.py          # Pure function: Event + State → State
├── engine.py           # Runtime engine: orchestrates WAL → Reducer → State
├── event_gate.py       # Validates event proposals before WAL write
├── hermes_bridge.py    # Parses LLM output → EventProposal list
└── replay_verifier.py  # G2: verifies runtime_state == replay(WAL)
```

## 6. Runtime flow

1. **Event proposal** — an event (store/access/archive/purge) is proposed
2. **Event gate** — validates the proposal (format, authorization)
3. **WAL write** — event is appended to WAL before applying to state
4. **Reducer** — applies event to current state (pure function, no side effects)
5. **State update** — runtime state reflects the event
6. **Replay verification** — periodically, WAL is replayed from initial state and compared to runtime state (G2)

## 7. What can it be used for?

- Bounded-retrieval memory backend for AI agents
- Crash-recovery substrate for long-running agent services
- Deterministic state replay for debugging / auditing
- Research prototype for event-sourced agent memory

## 8. What it is not

- NOT AGI
- NOT a production-ready agent framework
- NOT a chatbot framework
- NOT a model training system
- NOT a vector DB / semantic search system

## 9. Current status

- **Release:** v0.9.3 (onboarding hotfix)
- **Status:** Research runtime artifact / demo-ready / regression-protected
- **Demos:** 4 independent demos, all pass
- **Tests:** 8 regression tests, all pass
- **CI:** GitHub Actions on push/PR
- **External users:** Actively seeking first external trial feedback

## 10. Next milestones

1. **External User Trial** — collect first real user feedback
2. **Runtime Physics** — WAL compaction, tombstone lifecycle, time-travel debugging
3. **Observability** — OpenTelemetry integration, structured logging
4. **Edge Validation** — verify knowledge graph edges in docs/KNOWLEDGE/

Not in scope for v0.9.x: agent evolution, self-reinforcement, semantic emergence, AGI narratives.

## Key invariants

- **G2 Determinism:** `runtime_state == replay(WAL)` must hold at all checkpoints
- **Bounded retrieval:** O(W+CAP+K) complexity, independent of agent lifetime
- **WAL isolation:** WAL is append-only; no in-place mutation after write
- **No AGI claims:** MCR is a runtime substrate, not an intelligent agent