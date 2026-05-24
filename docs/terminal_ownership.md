# Terminal Ownership Map — MCR Runtime
========================================

**Version:** v1.0
**Effective:** Phase 2.6
**Status:** FROZEN

---

## Ownership Map

```
SYSTEM TERMINAL (L1 Orchestrator)
├── Owns: D:\AI\RUNTIME\
├── Owns: D:\AI\DOCS\RUNTIME_POLICY.md
├── Owns: D:\AI\DOCS\TERMINAL_BOUNDARY.md
├── Owns: D:\AI\DOCS\cross_terminal_protocol.md
├── Owns: D:\AI\START\
├── Owns: D:\AI\LOCKS\
├── Owns: BENCHMARKS/REGISTRY/
├── Co-owns: observability/ (structure)
└── Reads: All other terminals

MCR TERMINAL (L1 Leaf)
├── Owns: ./stable/
├── Owns: ./experimental/
├── Owns: ./archive/
├── Owns: ./logs/
├── Owns: ./integration/
├── Owns: ./observability/pathology/
├── Owns: ./observability/metrics/
├── Owns: BENCHMARKS/MCR/
├── Writes: observability/traces/
└── Reads: RUNTIME_POLICY.md, TERMINAL_BOUNDARY.md

KNOWLEDGE TERMINAL (L1 Leaf)
├── Owns: D:\AI\KNOWLEDGE\ (all subdirs)
├── Owns: INGESTION_PIPELINE.md
└── Reads: RUNTIME_POLICY.md, TERMINAL_BOUNDARY.md

UI TERMINAL (L1 Leaf)
├── Owns: D:\AI\workflows\
├── Owns: D:\AI\MEDIA\
├── Owns: D:\AI\ComfyUI\models\
├── Owns: BENCHMARKS/COMFYUI/
└── Reads: RUNTIME_POLICY.md, TERMINAL_BOUNDARY.md
```

---

## Escalation Graph

```
                    ┌─────────────┐
                    │   SYSTEM    │
                    │  (L1 Orch)  │
                    └──────┬──────┘
                           │
          ┌────────────────┼────────────────┐
          │                │                │
    ┌─────▼─────┐    ┌─────▼─────┐    ┌────▼────┐
    │    MCR    │    │ KNOWLEDGE │    │   UI    │
    │  (L1 Leaf)│    │ (L1 Leaf) │    │(L1 Leaf)│
    └─────┬─────┘    └─────┬─────┘    └────┬────┘
          │                │                │
          └────────────────┴────────────────┘
                           │
                    (Escalation to SYSTEM
                     on conflict/ambiguity)
```

---

## Forbidden Patterns

```
❌ MCR modifies RUNTIME_POLICY.md
❌ SYSTEM modifies mcr/stable/
❌ KNOWLEDGE modifies MCR retrieval physics
❌ UI touches mcr/observability/traces/
❌ MCR touches ComfyUI workflows
❌ SYSTEM runs MCR benchmarks directly
❌ Any terminal recursive self-orchestration
❌ Cross-terminal direct modification
```

---

## Violation Response

| Violation | Response | Timeframe |
|-----------|----------|-----------|
| Cross-modification | SYSTEM reverts | Immediate |
| Duplicate patch | SYSTEM arbitrates | < 1h |
| Recursive governance | SYSTEM breaks | Immediate |
| Role overlap | SYSTEM resolves | < 24h |
| Ownership ambiguity | Clarify + update | < 48h |

---

*FROZEN v1.0*
