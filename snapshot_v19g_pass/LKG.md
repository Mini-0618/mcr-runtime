# LKG — Last Known Good
# v0.19g — Anti-Drift Governance (PASS 7/7)
# Created: 2026-05-14

## FILE ID
- File: semantic_governance_v19g.py
- Hash: 637a11c907e8a889b909513522dfab8c
- Size: 60834 bytes / 1469 lines
- Modified: 2026-05-14 17:41:30

## BENCHMARK BASELINE (v0.19g 7/7 PASS)
```
Exp 1: Anti-Drift Trend Detection     — PASS
Exp 2: Auto-Decontamination          — PASS
Exp 3: Bridge Importance Stratific.  — PASS
Exp 4: Bridge Starvation Prevention   — PASS
Exp 5: Pre-Formation GC              — PASS
Exp 6: Episodic Reconstruction       — PASS
Exp 7: Full Anti-Drift Integration   — PASS
```

## CONFIG (frozen)
```python
GCConfig(
    inactive_threshold=200,
    collapse_threshold=0.01,
    max_active=5,
    drift_rate_window=50,
    drift_rate_threshold=0.01,
    auto_purify=True,
    pre_max_age=20,
    gc_interval=1,
    drift_rate=0.010,
    importance="medium"
)
BoundaryConfig(
    max_bridge_size=20,
    contamination_threshold=0.30
)
ValidationConfig(
    min_occurrences=2,
    negative_weight=0.3
)
BudgetConfig(
    max_active=5,
    dormant_max=20
)
ReinforcementConfig(
    decay_factor=0.97,
    reinforce_boost=0.20,
    weak_threshold=0.20
)
```

## BRIDGE IMPORTANCE DECAY RATES
```python
CRITICAL: 0.15  # ~500 ticks to collapse
HIGH:     0.30
MEDIUM:   0.50
LOW:      0.70  # ~267 ticks to collapse
```

## KNOWN LIMITATIONS (unresolved)
1. N=3 threshold unverified (theoretical, not empirical)
2. GC O(n²) redundancy merge at scale (10000 bridges → 100M comparisons)
3. Graceful degradation: strength ≠ importance (budget_exceeded sorting may archive critical bridges)
4. v0.19d Exp 3-4 incomplete (crash at line 461, not reached)

## ROLLBACK COMMAND
```bash
# If v0.19g is broken, rollback to this snapshot:
cp ./snapshot_v19g_pass/semantic_governance_v19g.py ./semantic_governance_v19g.py

# Verify hash after rollback:
md5sum /home/minimax/mcr/semantic_governance_v19g.py
# Expected: 637a11c907e8a889b909513522dfab8c
```

## SNAPSHOT POLICY
- Created on: benchmark PASS (7/7)
- Rollback trigger: any v0.19h/v0.20 FAIL
- Rollback decision: manual (human approval required)

## NEXT PHASE
Phase 2 — Runtime Stabilization
1. Long-run benchmark (1w+ tick)
2. Real integration (no mocks)
3. Observability
4. Bounded property verification
