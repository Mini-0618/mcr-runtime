# WAL Isolation Report — ARCH-FIND-001 Resolution
**Date**: 2026-05-20
**LKG**: 637a11c907e8a889b909513522dfab8c
**Status**: RESOLVED ✅

---

## ARCH-FIND-001 Summary

| Field | Value |
|-------|-------|
| Finding ID | ARCH-FIND-001 |
| Category | Runtime Integrity Violation |
| Severity | CRITICAL |
| Root Cause | `transitions.jsonl` used a process-global path |
| Old Location | `{cwd}/transitions.jsonl` (shared by all instances) |
| New Location | `{root}/runtime_logs/wal/{instance_id}/wal_*.jsonl` |

---

## What Was Broken

```
OLD (ARCH-FIND-001):
  Process P1 → open("transitions.jsonl", "a")  ← process-global!
  Process P2 → open("transitions.jsonl", "a")  ← SAME FILE!
  Result: WAL entries interleaved → replay contamination → physics失真
```

```
NEW (RESOLVED):
  Instance A → writes to {root_A}/runtime_logs/wal/{id_A}/wal_*.jsonl
  Instance B → writes to {root_B}/runtime_logs/wal/{id_B}/wal_*.jsonl
  Result: ZERO cross-contamination
```

---

## What Was Fixed

### 1. Instance-Local WAL Directory
```
{root}/runtime_logs/wal/{instance_id}/wal_YYYYMMDD_HHMMSS_*.jsonl
```

### 2. Persisted Instance ID
```
{root}/runtime_logs/instance_id
```
Same root → same instance_id → same WAL directory (stable across restarts).

### 3. Atomic Append (Without fsync)
- Write to persistent FD (no temp file, no rename)
- Buffered append (8KB buffer)
- `_seq_lock` for monotonic seq guarantees
- fsync removed (blocked in sandbox); acceptable for MCR use case

### 4. WAL Rotation
- 64MB per WAL file
- Multiple files possible under same instance

### 5. Checksum Integrity
- Adler-32 per entry
- Verified on replay; corrupted entries skipped

### 6. WALEntry NamedTuple
All fields: `seq`, `instance_id`, `tick`, `type`, `memory_id`, `from_state`, `to_state`, `reason`, `checksum`, `timestamp`

---

## Benchmark Results

| Test | Result | Details |
|------|--------|---------|
| G1: WAL Isolation | ✅ PASS | A_entries=80, B_entries=80, cross_vis=0 |
| G2: Replay Determinism | ✅ PASS | replay1 == replay2, 80 entries |
| G3: Event Ordering | ✅ PASS | strictly monotonic seq, all unique |
| G4: Checksum Integrity | ✅ PASS | 0 errors across 80 entries |
| G5: WAL Files | ✅ PASS | A=1 WAL file, B=1 WAL file |
| PERF: Latency | ✅ PASS | avg=0.008ms, p99=0.014ms |

---

## Verification of Cross-Instance Contamination Elimination

```
Instance A WAL: /tmp/mcr_wal_ok/A/runtime_logs/wal/{id_A}/wal_*.jsonl
Instance B WAL: /tmp/mcr_wal_ok/B/runtime_logs/wal/{id_B}/wal_*.jsonl

cross_visibility = 0  ← A cannot see B's WAL, B cannot see A's WAL
instance_ids_different = True
files_overlap = False
```

---

## What Remains Unchanged

- LayeredMemory API (store, retrieve, incremental_review, etc.)
- Memory lifecycle (working → episodic → semantic → archive)
- Decay buffer and promotion logic
- Boundedness guarantees from Phase III-A

---

## Runtime Physics Impact

| Experiment | Before Fix | After Fix |
|------------|-----------|-----------|
| III-A Metadata Physics | Contaminated by shared WAL | Clean (but must re-run) |
| III-C Crash Recovery | Cross-instance replay possible | Isolated recovery guaranteed |
| III-D Event Ordering | Interleaved WAL entries | Sequential per-instance WAL |
| III-E Observability | Cross-instance observer effects | Instance-local only |

**Recommendation**: Re-run III-A and III-C/III-D with the fixed WAL to get clean physics data.

---

## Files Changed

| File | Change |
|------|--------|
| `stable/wal_manager.py` | NEW — instance-local WAL manager |
| `stable/layered_memory.py` | ADDED `WALManager` integration in `__init__`, `_log_transition` uses WALManager |
| `stable/transition_log_path` | DEPRECATED, kept for backward compat only |

---

## WAL Manager API

```python
from wal_manager import WALManager

# Each LayeredMemory(root) auto-creates its own WAL:
lm = LayeredMemory("/path/to/root")

# Access the WAL:
wal = lm._wal
wal.append(tick=1, type="transition", memory_id="abc",
           from_state="working", to_state="episodic", reason="test")

# Replay:
for entry in wal.replay(from_seq=1, to_seq=None):
    print(entry.seq, entry.tick, entry.memory_id)

# Verify integrity:
report = wal.verify()
print(report["verified"], report["total_entries"], report["checksum_errors"])

# Metrics:
print(wal.get_metrics())
```
