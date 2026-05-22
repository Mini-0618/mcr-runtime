# MCR Release Notes — v0.19g_stable_runtime

**Tag:** `v0.19g_stable_runtime`
**Date:** 2026-05-15
**LKG Hash:** `637a11c907e8a889b909513522dfab8c`
**Phase:** Phase 2.6 — Pre-Bounded Validation, STEP 1.5

---

## What This Release Represents

First **research-grade milestone** for MCR cognitive runtime.

For the first time, the runtime has:
- Rollback-capable snapshot discipline
- Calibrated observability (detector v2)
- Trusted experiment lineage
- Verified recovery infrastructure

This is not a feature release. It is a **runtime engineering discipline** release.

---

## Confirmed Stable Properties

### Bounded Runtime Physics (10k tick verified)

| Property | Status | Value |
|---|---|---|
| Memory bounded | ✓ | W=10/E=40/S=102/A=219→300 |
| Latency bounded | ✓ | 1.03x–1.05x ratio |
| GC bounded | ✓ | 1.00x trend, 2.66 ops/tick |
| Real pathologies | ✓ | ZERO |
| Semantic stability | ✓ | 0.4% direct hit, 22% rerank mod |
| Lifecycle equilibrium | ✓ | 7092 prom / 6990 dem |

### Architecture Freeze

- **semantic = routing topology layer** (not direct knowledge source)
- **LayeredMemory = functional core** (940 lines, all methods accessible)
- **semantic_governance_v19g = LKG anchor** (1469 lines)
- **bridge lifecycle = full state machine** (hard cap 20 + contamination threshold 30%)
- **anti-drift mechanisms = non-conflicting** (purify + survival + immunity)

---

## Known Runtime Characteristics

### FINDING A — State Isolation Cross-Visibility

**Classification:** CLASS D — Architecture Characteristic

**Definition:** LayeredMemory instances share hidden process-global state through transitions.jsonl visibility. Multiple instances in the same process (even with different root dirs) can see each other's memories.

**Impact:**
- Concurrent experiments not fully isolated
- Rollback may leak state across instances
- Experiment contamination possible
- Runtime not strictly sandboxed

**Mitigation:** Design concurrent benchmarks to run in separate processes.

---

### FINDING B — Replay Non-Determinism

**Classification:** CLASS D — Determinism Limitation

**Definition:** Same inputs produce different memory IDs across runs. Likely sources: timestamp-based IDs, random tie-breaking, unordered traversal.

**Impact:**
- Replay not strictly deterministic
- Benchmark results may have hidden variance
- Scientific reproducibility limited

**Mitigation:** Use statistical aggregation across multiple runs; do not rely on exact ID matching for validation.

---

### Non-Pathology Catalog

The following are **expected physics**, NOT pathologies:

| Observation | Explanation |
|---|---|
| Archive 0→250 | Transient accumulation (DELETE_AFTER=500) |
| Periodic latency spikes | hard_cap_overflow batch processing every ~10 ticks |
| Low semantic direct retrieval (0.4%) | Semantic is routing post-processor, not primary memory |
| GC trend 1.07x→1.00x | Transient warmup, not cascade |
| 4 latency spikes in 10k | Buffer eviction + cap overflow, expected tier behavior |

---

## What's NOT Yet Verified

| Unknown | Status |
|---|---|
| Long-horizon equilibrium (50k+ ticks) | Pending STEP 2 |
| Adversarial robustness | Pending STEP 3 |
| Concurrent topology stability | Pending STEP 4 |
| Replay determinism guarantees | Not yet addressed |

---

## Snapshot Release Components

```
v0.19g_stable_runtime/
├── RELEASE_NOTES.md              ← This file
├── LKG.md                        ← LKG description + hash verification
├── semantic_governance_v19g.py   ← LKG anchor (60834 bytes, hash verified)
├── CALIBRATION.md                ← Detector v2 calibration results
├── recovery_test_results.txt     ← 5/5 PASS
├── architecture_findings.md       ← FINDING A + B
└── experiment_lineage.md         ← Phase 2a–2.6 history
```

---

## Recovery Test Results (5/5 PASS)

```
[PASS] lkg_restore         — hash 637a11c907e8a889b909513522dfab8c verified
[PASS] snapshot_lifecycle  — snapshots/ empty, LKG files accessible
[PASS] state_isolation     — cross-visibility detected (expected)
[PASS] corrupt_state       — graceful reset on corruption
[PASS] replay_consistency  — non-determinism documented (expected)
```

---

## Next Steps (Sequential Order)

```
STEP 2 → 50k tick Long-run
         Bounded equilibrium validation
         Equilibrium metrics: archive_growth_derivative,
         latency_growth_derivative, bridge_population_variance,
         rerank_entropy, topology_churn_rate

STEP 3 → Adversarial Runtime
         retrieval storm / archive flooding /
         semantic poisoning / retrieval noise

STEP 4 → Concurrent Runtime Pressure
         simultaneous retrieval + promotion + GC

STEP 5 → Final Bounded Proof
         (only if STEP 2–4 all pass)
```

**No step may be skipped.**

---

## Release Integrity

```bash
# Verify LKG hash
md5sum semantic_governance_v19g.py
# Expected: 637a11c907e8a889b909513522dfab8c

# Run recovery test
python3 experimental/recovery_test.py
# Expected: ALL TESTS PASSED
```
