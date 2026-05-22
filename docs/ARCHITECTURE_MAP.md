# Architecture Map — MCR v0.19f
=============================

## Core Components

```
loop.py              — Tick loop driver
memory.py            — Episodic memory store
layered_memory.py    — Layer orchestration
semantic_governance_v19f.py — Bridge governance
memory_trace.py      — Trace collection (820 lines)
event_system.py       — Event bus
config.py            — Configuration
```

## Layer Hierarchy

```
Layer 0: Event Ingestion
        ↓
Layer 1: Episodic Memory (raw events)
        ↓
Layer 2: Semantic Formation (co-occurrence)
        ↓
Layer 3: Bridge Network (episodic↔semantic)
        ↓
Layer 4: Retrieval (goal-directed query)
        ↓
Layer 5: Governance (bounded promotion/demotion)
```

## Data Flow

```
Tick → Event → Episodic → [Formation] → Semantic
                     ↓
              [Bridge Construction]
                     ↓
              [Retrieval Query]
                     ↓
              [Governance Check]
                     ↓
              [Response + Trace]
```

## Observability Stack

```
traces/          — Raw tick/retrieval/semantic/GC logs
pathology/       — Catalog of 12 known pathologies
metrics/         — Runtime metrics collector
tools/           — Snapshot diff, comparison
```

## Bounded Properties (enforced by policy)

- retrieval_budget: hard cap
- semantic_ratio: max 0.8
- active_bridges: max 150
- archive_size: unbounded (but GC tracked)
- drift: bounded by governance

## Directory Policy

- **stable/** — Only LKG version, no experiments
- **experimental/** — All unverified code, never in production
- **archive/** — Historical frozen versions, never modified
