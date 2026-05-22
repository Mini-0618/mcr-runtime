# MCR Snapshot Discipline — STEP 1 of Phase 2.6

## Purpose
Runtime recovery infrastructure for autonomous cognitive runtime experiments.

## Directory Structure

```
mcr/
├── snapshots/              # Phase snapshots (auto-generated)
│   ├── phase_1_baseline/   # Initial stable baseline
│   ├── phase_2a_semantic/  # v0.18-v0.19f semantic governance
│   ├── phase_2b_observer/  # Observability layer
│   └── ...
│
├── snapshot_v19g_pass/     # LKG — Last Known Good (MANUAL promote only)
│   ├── LKG.md             # LKG declaration + hash
│   └── semantic_governance_v19g.py
│
├── experimental/          # Active development (ALWAYS disposable)
│   ├── INDEX.md           # Experiment registry + lineage
│   └── debug_*.py        # Experiment artifacts → archive after use
│
└── archive/               # Dead experiments (read-only)
    ├── phase_0/           # Pre-semantic experiments
    ├── phase_1_baseline/
    └── phase_2a_semantic/
```

## Snapshot Policy

### When to Snapshot

| Event | Action | Automated |
|-------|--------|-----------|
| LKG promote | Full snapshot | Manual |
| Phase transition | Full snapshot | Manual |
| Major experiment start | Minimal snapshot | Manual |
| Every 10k tick run (long-run) | Data archive | Auto |
| Before risky experiment | Rollback point | Manual |

### What to Snapshot

**Full Snapshot:**
- All `.py` files in `stable/`, `experimental/`
- `docs/*.md` if present
- Runtime data directory (if present)
- Metadata: timestamp, experiment_id, phase, hash

**Minimal Snapshot (LKG Promote):**
- `semantic_governance_v19g.py` (the one that matters)
- `LKG.md` (declaration)
- `stable/layered_memory.py` (core dependency)

**Data Archive:**
- Metrics JSON files
- Pathology findings
- Transition logs
- NO code (code snapshot is separate)

## Rollback Graph

```
CURRENT (experimental/semantic_governance_v19g.py)
    ↑
    │ (manual: if catastrophic regression)
    │
snapshot_v19g_pass/
  └── LKG.md + semantic_governance_v19g.py
        ↑
        │ (older snapshots if needed)
        │
snapshots/
  ├── phase_2b_observer/
  └── ...
```

**Rollback Rules:**
1. Never rollback across phases without testing
2. Rollback always verifiable via hash comparison
3. After rollback: re-run 1k tick sanity check before resuming
4. Rollback creates new snapshot (old state preserved)

## Corruption Recovery Test

Before any LKG promote, must pass:

```
python3 recovery_test.py
  1. Corrupt memory_state.json (inject bad JSON)
  2. Load LayeredMemory → must fail gracefully
  3. Rollback to snapshot → must restore functional state
  4. Replay last 100 ticks → must match expected behavior
```

## Archive Policy

**Debug files** (`debug_*.py`) → archive after experiment:
1. Copy to `/archive/phase_N/`
2. Write `metadata.json` (experiment purpose, duration,结论)
3. Add to `INDEX.md` lineage
4. Delete from `experimental/`

**Never archive:**
- Current LKG files (they stay in `snapshot_v19g_pass/`)
- Active experiment files still in use

## Experiment Registry (INDEX.md)

Every file in `experimental/` must have an entry:

```markdown
## semantic_governance_v19g.py
- **Phase**: phase_2a_semantic
- **Version**: v0.19g
- **Purpose**: semantic routing + adaptive topology + bounded governance
- **Status**: LKG (active)
- **Hash**: 637a11c907e8a889b909513522dfab8c
- **Experiments**: p2-1 through p2-5
- **Key decisions**: bridge formation, contamination threshold, cold bridge starvation prevention
```

```markdown
## debug_decay.py
- **Phase**: phase_2a_semantic
- **Purpose**: debug decay buffer overflow @ tick 50
- **Status**: ARCHIVED → archive/phase_2a_semantic/debug_decay.json
- **Date**: 2026-05-12
- **Conclusion**: decay_buffer size was too small, fixed by increasing buffer
```

## LKG Declaration

To promote to LKG:

```bash
# 1. Verify current state passes all checks
python3 recovery_test.py
python3 long_run_benchmark.py  # 10k tick minimum

# 2. Create snapshot
cp -r experimental/semantic_governance_v19g.py snapshots/phase_2c_observer/

# 3. Promote to LKG
cp snapshots/phase_2c_observer/semantic_governance_v19g.py snapshot_v19g_pass/
# Update snapshot_v19g_pass/LKG.md with new hash

# 4. Verify
md5sum snapshot_v19g_pass/semantic_governance_v19g.py
```

## Phase Tagging

Current phases:

```
phase_0           — Pre-semantic baseline (legacy)
phase_1_baseline  — LayeredMemory without semantic (v0.17)
phase_2a_semantic — Semantic governance (v0.18 - v0.19g)
phase_2b_observer — Observability layer (p2-4, p2-5)
phase_2c_recovery — Snapshot discipline (p2-6 STEP 1)
phase_2_long_run  — Long-run equilibrium (STEP 2)
phase_2_adversarial — Adversarial robustness (STEP 3)
phase_2_concurrent — Concurrency stability (STEP 4)
phase_2_final     — Final bounded proof (p2-6 STEP 5)
```
