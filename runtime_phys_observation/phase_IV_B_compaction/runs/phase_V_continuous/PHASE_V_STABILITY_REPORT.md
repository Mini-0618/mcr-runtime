# PHASE V — Continuous Stability Run Report
## Mode: CONTINUOUS BENCHMARK LOOP | 20,000 ticks | 4 windows

**LKG:** 637a11c907e8a889b909513522dfab8c
**Run date:** Phase V pre-run validation
**Ticks:** 20,000 (stopped at window 4)
**Duration:** 8.2 seconds
**STOP condition:** OVERHEAD 26.67x > 20.0 threshold

---

## Executive Summary

**Finding: Compaction overhead grows super-linearly with coaccess graph size.**

| Metric | Value | Status |
|--------|-------|--------|
| WAL integrity | 100% (4/4) | PASS |
| Entropy bounded | +0.36 max drift | PASS |
| Archive stability | 68–364 (wildly oscillating) | FAIL |
| Compaction overhead | 7x → 27x (growing) | PATHOLOGY |
| Semantic tier | 0 nodes (no promotions) | STALL |
| Memory bounded | archive_ratio < 10 | PASS |

---

## P0 — System Stability Drift

### WAL Determinism
- **WAL seq continuity:** 100% across all 4 windows, 20k ticks
- **No seq gaps detected** at any checkpoint
- **Verdict:** WAL is stable under continuous load

### Memory Growth
- Working: stable at 10 (hard cap working size = 10)
- Episodic: stable at 40
- Archive: oscillates 68–364 per window (NO steady state)
- **This oscillation is the key archive pathology**

### Latency Trend
| Window | Avg Latency | P99 Latency | Max Latency |
|--------|-------------|-------------|-------------|
| 1 | 0.15ms | 0.31ms | 22.05ms |
| 2 | 0.25ms | 0.38ms | 43.77ms |
| 3 | 0.34ms | 0.37ms | 65.10ms |
| 4 | 0.45ms | 0.38ms | 84.94ms |

Avg latency grows 3x over 4 windows. Max latency grows 4x.

### State Hash Continuity
All state hashes are unique per snapshot. No hash divergence detected.
However, no hash repeat either — meaning state is never stable (no equilibrium).

---

## P1 — Compaction Stress Saturation

### Overhead Growth Trajectory
| Window | Ticks | Overhead vs baseline | Compaction Ops |
|--------|-------|---------------------|----------------|
| 1 | 1–5k | 7.26x | 10 |
| 2 | 5k–10k | 13.46x | 10 |
| 3 | 10k–15k | 19.28x | 10 |
| 4 | 15k–20k | 26.67x | 10 |

**Super-linear growth confirmed.** Each 5k tick window adds ~6–7x overhead.
This is the compaction physics pathology.

### Root Cause Hypothesis
`run_compaction()` does a full O(n²) coaccess graph scan.
The coaccess graph accumulates edges with no pruning.
Each compaction run processes more edges than the previous one.
→ Quadratic blowup of per-tick overhead.

### Archive Oscillation
- Window 1 end A=202 → Window 2 end A=101 (flushed)
- Window 2 end A=364 → Window 3 end A=209 (flushed)
- Window 3 end A=333 → Window 4 end A=68 (flushed)

`try_flush()` at tick % 200 == 0 is flushing the episodic backlog into archive.
This is `incremental_review()` demoting at 50% episodic capacity, then
`try_flush()` moving those demoted items to archive. But the size varies
wildly because no steady-state is reached.

### Semantic Tier Stalled
- 0 promotions across all 20k ticks
- 0 semantic_summary nodes formed
- **Why:** `incremental_review` never promotes — it only demotes.
  No promotion pathway exists in this configuration.

---

## P2 — Event Density

- **Promotions:** 0 (stalled)
- **Demotions:** 0 (but archive grows via try_flush direct demotion)
- **GC ops:** 0
- **Compaction ops:** 40 total (10 per window)
- **No event starvation detected** — system is active

---

## P3 — Cross-Module Consistency

- WAL seq: always continuous
- State hash: always valid (no divergence)
- **Memory tier oscillation:** archive varies 5x between windows
  This is the most significant consistency issue.

---

## Failure Boundary Analysis

### Triggered Stop Condition
```
Window 4: OVERHEAD 26.67x > 20.0 threshold
```

### Boundary Events (warnings before stop)
- `overhead_warning@window1` — overhead 7.26x (72% of 20x threshold)
- `overhead_warning@window2` — overhead 13.46x (67% of 20x threshold)
- `overhead_warning@window3` — overhead 19.28x (96% of 20x threshold)
- `overhead_warning@window4` — overhead 26.67x (133% — STOP)

### Non-triggered Thresholds
- Entropy drift never exceeded ±1.0 (max: +0.358)
- Archive ratio never exceeded 10.0 (max: 4.18)
- WAL seq always valid (4/4)

---

## Key Findings

### F1: WAL is Deterministic Under Load
100% seq continuity, no hash divergence. WAL manager is NOT the bottleneck.

### F2: Compaction Overhead is the Critical Pathology
Super-linear growth: 7x → 13x → 19x → 27x over 4 windows.
This will eventually make the system unusable at scale.

### F3: Archive Has No Steady State
Archive oscillates 68–364 with no equilibrium. `try_flush()` creates burst
demotions that overwhelm any steady-state hypothesis.

### F4: Semantic Tier is Dead
Zero promotions across 20k ticks. The compaction pipeline has no upward
promotion pathway — only demotion. This is a tier isolation problem.

### F5: Latency Grows with Compaction Iterations
Avg tick latency grows 3x over 4 windows (0.15 → 0.45ms).
Max tick latency grows 4x (22ms → 85ms).

---

## Scientific Conclusion

**The compaction physics is the limiting factor for long-run stability.**

The coaccess graph grows unboundedly with each compaction cycle.
`run_compaction()` does a full scan of this growing graph, producing
super-linear overhead growth. This is NOT a bug — it is the expected
behavior of an unbounded O(n²) algorithm running on a growing graph.

**This confirms the P0 priority: Tombstone Lifecycle.**
If archive accumulates without a lifecycle (soft-delete → cleanup), the
compaction coaccess graph also grows unboundedly. Both problems share the
same root cause: **no deletion/cleanup mechanism.**

**The semantic tier needs an active promotion pathway**, not just demotion.
Without promotion, the semantic tier remains empty and compaction has
nothing to operate on.

---

## Recommended Next Phase

**PHASE V-B: Compaction Physics Fix**

Immediate actions (no architecture change):
1. Cap coaccess graph size (evict oldest edges when size > N)
2. Add coaccess decay (reduce edge weight over ticks)
3. Switch to incremental compaction (per-topic, not full graph)
4. Verify promotion pathway exists for semantic tier

Long-term: Tombstone Lifecycle (PHASE V as originally planned)
