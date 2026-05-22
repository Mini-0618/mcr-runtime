# MCR — Memory-Augmented Cognitive Runtime

A bounded, observable, persistent cognitive runtime for long-horizon AI agent loops.

---

## What is MCR?

MCR is a research platform studying how AI agents maintain bounded, stable memory over thousands of operational ticks. It is NOT a general-purpose agent framework — it is a runtime system with hard boundedness guarantees.

**Core problem MCR solves:** Memory explosion, retrieval drift, and cognitive degradation in long-running AI loops.

---

## Architecture

```
Layered Memory
├── episodic    — raw interaction records, time-stamped
├── semantic    — promoted, abstracted, time-independent
└── archive     — decayed, tombstoned, compacted

Bounded Retrieval
├── access_history capped @ N
├── goal_relevance cached
└── retrieval_count <= 20/tick

Runtime Properties
├── memory decay (edge decay = 0.995)
├── persistence batching (flush_interval = 10)
├── incremental compaction
└── full lifecycle observability (memory_trace.py)
```

---

## Benchmark

| Property | Bound | Status |
|----------|-------|--------|
| retrieval_count | <= 20/tick | VERIFIED |
| semantic_ratio | < 0.8 | VERIFIED |
| active_bridges | <= 150 | VERIFIED |
| latency | < 500ms | VERIFIED |
| drift | Bounded | VERIFIED |

---

## Current Status

- **v0.9** — Observability layer (memory_trace.py, 800+ lines)
- **Phase VII** — Tombstone Lifecycle (G1/G4 PASS, G2/G3 WIP)
- **LKG** — snapshot_v19g_pass (hash: 637a11c907e8a889b909513522dfab8c)
- **Mode** — Maintenance / Iterative hardening

---

## Roadmap

| Phase | Status |
|-------|--------|
| Core Loop | ✅ Done |
| Bounded Governance | ✅ Done |
| Observability | ✅ Done |
| Tombstone Lifecycle | 🔄 WIP |
| Retrieval Scaling (P0) | 🔄 WIP |
| Semantic Consolidation | 🔄 WIP |
| Bounded Cognition Policy | 🔄 WIP |
| Agent Integration | 🔜 Next |

---

## Tech Stack

Python 3 / Pure stdlib core / No external AI APIs required

---

## License

MIT
