# Roadmap — MCR

## v0.9.x (current)

- [x] Event-sourced runtime kernel (WAL + reducer + replay verifier)
- [x] Deterministic replay verification (G2)
- [x] Hermes Bridge v0.1 (LLM integration adapter)
- [x] Quickstart demo
- [x] Replay verification demo
- [ ] Branch protection on master
- [ ] CI regression tests (pytest)
- [ ] Replay verifier hardening (error messages, edge cases)

## v0.10

- [ ] Stable package layout (public API surface)
- [ ] pytest regression suite (full event type + state transition coverage)
- [ ] WAL integrity verification (fast hash path)
- [ ] Deterministic replay benchmark (compare replay speed vs WAL length)
- [ ] Tombstone lifecycle G3 fix

## v0.11

- [ ] Real agent workload integration (non-synthetic benchmark)
- [ ] Hermes Bridge v0.2 (production LLM integration)
- [ ] Access history cap + goal relevance caching (Phase I optimization)

---

## What This Project Is NOT

This project does not include and will not add:

- AGI capabilities
- Autonomous self-evolution
- Cognitive awakening
- Unlimited context windows
- Real-time learning from production data

---

## What This Project IS

A bounded-latency memory runtime for long-running AI agents.

Built around:
- Event sourcing (WAL-first, deterministic replay)
- Bounded retrieval (O(W+CAP+K), independent of agent lifetime)
- Observable lifecycle (every state transition is logged)
- LLM integration via validated event proposals only