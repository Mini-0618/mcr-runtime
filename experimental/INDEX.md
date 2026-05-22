# MCR Experimental Registry

## Purpose
Track all experimental files, their lineage, and status.

## Policy
- Every file in `experimental/` must have an entry here.
- When archived: update status, add archive path, keep for lineage.
- Never delete entries (preserve experiment history).

---

## semantic_governance_v19g.py
- **Phase**: phase_2a_semantic
- **Version**: v0.19g
- **Purpose**: semantic routing + adaptive topology + bounded governance
- **Status**: LKG (active — promoted)
- **Hash**: `637a11c907e8a889b909513522dfab8c`
- **Experiments**: p2-1 through p2-5
- **Key decisions**: bridge formation (N≥3 co-activations), contamination threshold (30%), cold bridge starvation prevention (importance-weighted promotion), pre-bridge GC (pre_max_age=50 ticks), auto_purify mechanism
- **Architecture**: semantic = routing topology layer (NOT knowledge store)

---

## layered_memory.py
- **Phase**: phase_1_baseline
- **Version**: v0.17 stable
- **Purpose**: core memory system — 4-tier (working/episodic/semantic/archive) + decay + promotion
- **Status**: CORE DEPENDENCY (DO NOT MODIFY without LKG review)
- **Path**: stable/layered_memory.py
- **Hash**: (verify before use)

---

## Runtime Physics Observers

### runtime_physics_observer.py
- **Phase**: phase_2b_observer
- **Version**: v1 (uncalibrated)
- **Purpose**: initial runtime physics observation — 10k tick run
- **Status**: SUPERSEDED by calibrated_pathology_detector.py
- **Key finding**: 4,194 pathology findings → 100% false positive (detector miscalibration)
- **Output**: run_data/ (metrics_timeline.json, pathology_findings.json)

### calibrated_pathology_detector.py
- **Phase**: phase_2b_observer
- **Version**: v2 (calibrated)
- **Purpose**: calibrated pathology detection — percentile-based, sustained-window, warmup-masked, taxonomy-classified
- **Status**: ACTIVE (current)
- **Key finding**: 0 runtime pathologies — runtime is stable
- **Output**: run_data_calibrated/ (metrics_calibrated.json, pathology_calibrated.json)

---

## Archived Experiments

### debug_decay.py
- **Archived**: archive/phase_2a_semantic/debug_decay.py
- **Date**: 2026-05-12
- **Purpose**: debug decay buffer overflow observed @ tick 50
- **Conclusion**: decay_buffer too small → fixed in v0.19f by increasing buffer size
- **Metadata**: archive/phase_2a_semantic/debug_decay.json

### debug_sem.py
- **Archived**: archive/phase_2a_semantic/debug_sem.py
- **Date**: 2026-05-12
- **Purpose**: debug semantic layer initialization failure
- **Conclusion**: world_state import path issue → fixed by patching sys.path
- **Metadata**: archive/phase_2a_semantic/debug_sem.json

### debug_pre2.py, debug_pre3.py, debug_pre4.py, debug_pre5.py
- **Archived**: archive/phase_2a_semantic/
- **Date**: 2026-05-14
- **Purpose**: pre-phase2 diagnostic scripts (pre-experiment cleanup)
- **Conclusion**: temporary diagnostic files, no significant findings
- **Metadata**: archive/phase_2a_semantic/debug_pre*.json

### debug_pre_gc.py
- **Archived**: archive/phase_2a_semantic/debug_pre_gc.py
- **Date**: 2026-05-14
- **Purpose**: GC behavior under memory pressure
- **Conclusion**: GC threshold was correct, no changes needed
- **Metadata**: archive/phase_2a_semantic/debug_pre_gc.json

---

## Semantic Schema Versions (Historical)

### semantic_schema_v15.py
- **Phase**: phase_2a_semantic (early)
- **Version**: v0.15
- **Status**: ARCHIVED

### semantic_schema_v15b.py
- **Phase**: phase_2a_semantic (early)
- **Version**: v0.15b
- **Status**: ARCHIVED

### semantic_routing.py
- **Phase**: phase_2a_semantic
- **Version**: early routing experiments
- **Status**: ARCHIVED

### semantic_abstraction_v18.py
- **Phase**: phase_2a_semantic
- **Version**: v0.18
- **Status**: ARCHIVED

---

## Chaos & Stress Tests

### chaos_experiment.py
- **Phase**: phase_2a_semantic
- **Purpose**: adversarial memory injection + retrieval storm
- **Status**: LEGACY (valid but superseded by dedicated adversarial tests in STEP 3)
- **Key finding**: system recovered from 10x memory pressure without corruption

---

## Phase 2.6 — Snapshot Release

### v0.19g_stable_runtime
- **Tag**: `v0.19g_stable_runtime`
- **Date**: 2026-05-15
- **Hash**: `637a11c907e8a889b909513522dfab8c`
- **Status**: RELEASED
- **Path**: `releases/v0.19g_stable_runtime/`
- **Purpose**: First research-grade milestone — rollback-capable, observability-calibrated, detector-trusted, lineage-established
- **Key findings at release**:
  - ZERO runtime pathologies @ 10k tick
  - Semantic = routing post-processor (0.4% direct, 22% rerank)
  - Memory bounded: W=10/E=40/S=102/A=219→300
  - Latency bounded: 1.03x–1.05x ratio
  - GC bounded: 1.00x trend
- **Known characteristics**:
  - State isolation cross-visibility (process-global transitions.jsonl)
  - Replay non-determinism (timestamp/random-based IDs)
- **Next**: STEP 2 (50k tick long-run)

---

## Next Entry Template

```markdown
### <filename>
- **Phase**: phase_2_?
- **Purpose**: 
- **Status**: ACTIVE | ARCHIVED | LKG
- **Key finding / Conclusion**: 
```
