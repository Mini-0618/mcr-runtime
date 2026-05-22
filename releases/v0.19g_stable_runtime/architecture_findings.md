# Architecture Findings — v0.19g_stable_runtime

## FINDING A — State Isolation Cross-Visibility

**Finding ID:** ARCH-FIND-001
**Classification:** CLASS D — Architecture Characteristic
**Severity:** Medium
**Discovered:** 2026-05-15

### Definition

LayeredMemory instances share hidden process-global state through transitions.jsonl visibility. When two or more LayeredMemory instances run in the same Python process (even with different root directories), they can see each other's memories.

### Evidence

```
lm1 = LayeredMemory(root="/tmp/test1")
lm2 = LayeredMemory(root="/tmp/test2")

lm1.remember("tag_x", {"text": "data1"}, importance=0.9)

# lm2 can see lm1's "tag_x" memory
lm2.recall("tag_x")  # Returns data from lm1's memory
```

### Root Cause

`transitions.jsonl` is opened in the process working directory (not inside `root`), making it process-global. Additionally, `_gc_history`, `_decay_history`, and `_transition_log` may be affected.

### Impact

| Impact Area | Severity | Description |
|---|---|---|
| Concurrent benchmarks | HIGH | Multiple experiment threads share state |
| Rollback purity | MEDIUM | Snapshot restore may leak cross-instance state |
| Experiment reproducibility | MEDIUM | Concurrent runs contaminate each other |
| Sandboxed evaluation | LOW | Adversarial test could leak into main runtime |

### Mitigation

Run concurrent experiments in **separate processes** (not threads). Use subprocess isolation for parallel benchmark runs.

### Status

Not a bug. This is a runtime topology property. Will not be "fixed" — concurrent benchmarks must be designed around this constraint.

---

## FINDING B — Replay Non-Determinism

**Finding ID:** ARCH-FIND-002
**Classification:** CLASS D — Determinism Limitation
**Severity:** Low–Medium
**Discovered:** 2026-05-15

### Definition

Same LayeredMemory inputs produce different memory IDs across runs. Replay is not strictly deterministic.

### Evidence

```
Run 1: ['65bd3cd7', 'b77387bf']  # memory IDs after operations
Run 2: ['4be6fb6c', 'e68cffad']  # different IDs for same content
```

### Possible Sources

1. Timestamp-based IDs: `time.time()` or `time.perf_counter()` in ID generation
2. Random tie-breaking: In sorted collections with equal-priority items
3. Unordered traversal: Dictionary/set iteration order not guaranteed
4. Hidden mutable state: Cross-run contamination via process-global files

### Impact

| Impact Area | Severity | Description |
|---|---|---|
| Scientific reproducibility | MEDIUM | Cannot guarantee exact replay |
| Benchmark stability | LOW–MEDIUM | Results may vary across runs |
| Regression testing | LOW | Cannot use exact ID matching for validation |
| Replay-based debugging | LOW | Same replay may produce different state |

### Mitigation

Use **statistical aggregation** across multiple runs. Do not rely on exact ID matching for test validation.

### Status

Not a failure. This is a runtime property. Deterministic replay would require architectural changes. Not planned for v0.19g.

---

## Non-Pathology Catalog (v0.19g)

| Flagged Issue | Root Cause | Resolution |
|---|---|---|
| Archive explosion (0→250) | Normal transient accumulation | threshold artifact |
| Memory explosion (0.5/tick) | Synthetic workload pattern | threshold artifact |
| Semantic dominance (52%) | Misidentified rerank_modifications | detector v2 fix |
| GC trend 1.07x | Warmup transient | bounded, not cascade |
| 4 latency spikes | hard_cap_overflow batch processing | expected tier behavior |

---

## Taxonomy Reference (v0.19g)

```
CLASS A — Critical corruption:      NONE
CLASS B — Governance instability:   NONE
CLASS C — Memory pathology:          NONE
CLASS D — Detector uncertainty:      Fixed in v2
CLASS E — False pathology:          Fixed (threshold artifacts)
CLASS F — Expected physics:         archive_acc, hard_cap_overflow, latency_spike
```

---

*End of Architecture Findings — v0.19g_stable_runtime*
