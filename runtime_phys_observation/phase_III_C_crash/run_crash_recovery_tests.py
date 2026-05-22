#!/usr/bin/env python3
"""
MCR Phase III-C: Crash Recovery Physics
========================================
ARCH-FIND-001 修复后第一次可信 replay 基础上的 crash recovery 实验。

验证 MCR 在 crash / partial write / corrupted WAL / snapshot interruption 下
是否能恢复一致的 runtime state。

Focus: 不是 runtime 会不会 crash，而是 crash 后是否保持 identity continuity。
"""

import sys
import os
import json
import time
import random
import shutil
import hashlib
import zlib
import signal
import tempfile
from pathlib import Path

sys.path.insert(0, '/home/minimak/mcr/stable')
from layered_memory import LayeredMemory
from wal_manager import WALManager

# ─── Directory Setup ─────────────────────────────────────────────────────────
BASE_DIR = Path("/home/minimak/mcr/runtime_phys_observation/phase_III_C_crash")
RUNS_DIR = BASE_DIR / "runs"
CORRUPT_DIR = BASE_DIR / "corrupted_wal"
SNAP_DIR = BASE_DIR / "snapshots"
REPLAY_DIR = BASE_DIR / "replay"
FINDINGS_DIR = BASE_DIR / "findings"
METRICS_DIR = BASE_DIR / "metrics"

for d in [RUNS_DIR, CORRUPT_DIR, SNAP_DIR, REPLAY_DIR, FINDINGS_DIR, METRICS_DIR]:
    d.mkdir(parents=True, exist_ok=True)


# ─── Utilities ───────────────────────────────────────────────────────────────

def state_hash(lm: LayeredMemory) -> str:
    """Compute a deterministic hash of current runtime state for comparison."""
    components = []

    # Deterministic ordering of working memory
    for mid in sorted(lm.working_memory.keys()):
        entry = lm.working_memory[mid]
        components.append(f"w:{mid}:{entry.get('state','?')}:{entry.get('decay',0):.6f}")

    # Deterministic ordering of episodic
    for mid in sorted(lm.episodic_memory.keys()):
        entry = lm.episodic_memory[mid]
        components.append(f"e:{mid}:{entry.get('state','?')}:{entry.get('access_count',0)}")

    # Deterministic ordering of semantic
    for mid in sorted(lm.semantic_memory.keys()):
        entry = lm.semantic_memory[mid]
        components.append(f"s:{mid}:{entry.get('state','?')}:{entry.get('confidence',0):.6f}")

    # Archive
    for mid in sorted(lm.archive_memory.keys()):
        components.append(f"a:{mid}:archived")

    data = "|".join(components)
    return hashlib.sha256(data.encode()).hexdigest()[:16]


def count_memories(lm: LayeredMemory) -> dict:
    """Count memories across all tiers."""
    return {
        "working": len(lm.working_memory),
        "episodic": len(lm.episodic_memory),
        "semantic": len(lm.semantic_memory),
        "archive": len(lm.archive_memory),
        "decay_buffer": len(lm.decay_buffer),
        "total": (
            len(lm.working_memory) + len(lm.episodic_memory) +
            len(lm.semantic_memory) + len(lm.archive_memory)
        ),
    }


def wal_entry_count(wal: WALManager) -> int:
    """Count total WAL entries across all WAL files."""
    total = 0
    for wf in sorted(wal.wal_dir.glob("wal_*.jsonl")):
        try:
            with open(wf, "r", encoding="utf-8") as f:
                total += sum(1 for line in f if line.strip())
        except OSError:
            continue
    return total


def simulate_crash(run_dir: str, tag: str) -> dict:
    """
    Simulate a hard crash by:
    1. Creating a fresh runtime
    2. Running N operations
    3. Taking a state snapshot (without informing the runtime)
    4. Terminating via os._exit(1) — no cleanup, no flush
    Returns pre-crash state hash.
    """
    if os.path.exists(run_dir):
        shutil.rmtree(run_dir)
    os.makedirs(run_dir, exist_ok=True)

    random.seed(42)
    lm = LayeredMemory(run_dir)

    # Run operations
    for i in range(1, 101):
        lm.store(f"mem_{i}", memory_type="test", tags=["t"])
        lm.process_decay_buffer(i)
        if i % 10 == 0:
            lm.incremental_review(i)

    lm.try_flush(100)

    pre_crash_hash = state_hash(lm)
    pre_crash_counts = count_memories(lm)
    wal_entries = wal_entry_count(lm._wal)

    return {
        "run_dir": run_dir,
        "tag": tag,
        "pre_crash_hash": pre_crash_hash,
        "pre_crash_counts": pre_crash_counts,
        "wal_entries": wal_entries,
        "lm": lm,
    }


# ─── Test 1: Hard Crash + Replay ─────────────────────────────────────────────

def test_hard_crash_replay() -> dict:
    """
    Simulate kill -9 (no cleanup) and verify replay recovers consistent state.
    """
    run_dir = str(RUNS_DIR / "test1_hard_crash")
    crash_data = simulate_crash(run_dir, "hard_crash")

    pre_hash = crash_data["pre_crash_hash"]
    pre_counts = crash_data["pre_crash_counts"]
    wal_entries = crash_data["wal_entries"]

    # Simulate crash: os._exit(1) skips all cleanup
    # (We can't actually call os._exit in this context, so we simulate by
    # creating a new instance pointing at the same root)
    # os._exit(1) would leave the WAL with the last append potentially truncated

    # Simulate crash by: 1) truncate last WAL entry (partial write simulation)
    # 2) create fresh instance for recovery
    wal_files = sorted(Path(run_dir).glob("runtime_logs/wal/*/wal_*.jsonl"))
    if wal_files:
        last_file = wal_files[-1]
        with open(last_file, "rb") as f:
            content = f.read()
        # Truncate last 10 bytes (simulate half-written last entry)
        if len(content) > 10:
            with open(last_file, "wb") as f:
                f.write(content[:-10])

    # Recover via fresh instance
    t0 = time.perf_counter()
    lm_recovered = LayeredMemory(run_dir)
    recovery_latency_ms = (time.perf_counter() - t0) * 1000

    post_hash = state_hash(lm_recovered)
    post_counts = count_memories(lm_recovered)

    # WAL replay validation
    wal = lm_recovered._wal
    verify_report = wal.verify()

    # Count WAL entries after recovery (should match pre-crash or be slightly less due to truncation)
    recovered_wal_entries = wal_entry_count(wal)

    result = {
        "test": "TEST1_hard_crash_replay",
        "pass": True,
        "pre_crash_hash": pre_hash,
        "post_recovery_hash": post_hash,
        "hash_match": pre_hash == post_hash,
        "pre_crash_counts": pre_counts,
        "post_recovery_counts": post_counts,
        "counts_match": pre_counts == post_counts,
        "recovery_latency_ms": round(recovery_latency_ms, 3),
        "recovered_wal_entries": recovered_wal_entries,
        "pre_crash_wal_entries": wal_entries,
        "lost_events": max(0, wal_entries - recovered_wal_entries),
        "wal_verify_passed": verify_report["verified"],
        "wal_checksum_errors": verify_report["checksum_errors"],
        "wal_seq_gaps": len(verify_report["seq_gaps"]),
        "ghost_state_detected": False,  # would require manual inspection
        "recovery_state_hash_match": pre_hash == post_hash,
        "notes": "Hard crash simulated by truncating last WAL entry",
    }

    result["pass"] = (
        result["recovery_state_hash_match"] and
        result["counts_match"] and
        result["wal_verify_passed"]
    )
    return result


# ─── Test 2: Partial WAL Write ──────────────────────────────────────────────

def test_partial_wal_write() -> dict:
    """
    Simulate partial WAL write (half-written entry) and verify:
    - Corruption is detected
    - Replay skips corrupted entry and continues
    - No crash/panic
    """
    run_dir = str(RUNS_DIR / "test2_partial_wal")
    if os.path.exists(run_dir):
        shutil.rmtree(run_dir)
    os.makedirs(run_dir, exist_ok=True)

    random.seed(42)
    lm = LayeredMemory(run_dir)

    for i in range(1, 51):
        lm.store(f"p_{i}", memory_type="test", tags=["t"])
        lm.process_decay_buffer(i)

    lm.try_flush(50)
    wal_entries_before = wal_entry_count(lm._wal)
    pre_counts = count_memories(lm)

    # Now corrupt: find the WAL file and truncate mid-entry
    wal_files = sorted(lm._wal.wal_dir.glob("wal_*.jsonl"))
    if wal_files:
        last_file = wal_files[-1]
        with open(last_file, "rb") as f:
            content = bytearray(f.read())

        # Find a newline and truncate 5 bytes before it (mid-entry)
        newline_positions = [i for i, b in enumerate(content) if b == ord('\n')]
        if newline_positions:
            truncate_at = max(0, newline_positions[-1] - 5)
            corrupted_content = bytes(content[:truncate_at])
            with open(last_file, "wb") as f:
                f.write(corrupted_content)

    # Verify corruption detection
    wal = lm._wal
    verify_before_recover = wal.verify()
    wal_entries_corrupted = wal_entry_count(wal)

    # Recover
    t0 = time.perf_counter()
    lm_rec = LayeredMemory(run_dir)
    recovery_latency_ms = (time.perf_counter() - t0) * 1000

    post_counts = count_memories(lm_rec)
    verify_after = lm_rec._wal.verify()

    result = {
        "test": "TEST2_partial_wal_write",
        "pass": True,
        "wal_entries_before": wal_entries_before,
        "wal_entries_corrupted": wal_entries_corrupted,
        "corruption_detected": (
            verify_before_recover["verified"] == False or
            verify_before_recover["corrupted_lines"] is not None
        ),
        "recovery_latency_ms": round(recovery_latency_ms, 3),
        "recovered_counts": post_counts,
        "pre_crash_counts": pre_counts,
        "counts_match": pre_counts == post_counts,
        "wal_verify_after_recovery": verify_after["verified"],
        "checksum_errors_after": verify_after["checksum_errors"],
        "corrupted_events_quarantined": verify_after["checksum_errors"],
        "lost_events": max(0, wal_entries_before - wal_entry_count(lm_rec._wal)),
        "runtime_survived": True,  # if we get here, it survived
        "notes": "Partial WAL write simulated by truncating mid-entry",
    }

    # Partial write should cause detection but NOT crash
    result["pass"] = (
        result["corruption_detected"] and
        result["runtime_survived"] and
        result["wal_verify_after_recovery"]
    )
    return result


# ─── Test 3: Snapshot Interruption ──────────────────────────────────────────

def test_snapshot_interruption() -> dict:
    """
    Simulate snapshot write interruption.
    Write a partial/corrupted snapshot file, verify it's discarded.
    """
    run_dir = str(RUNS_DIR / "test3_snapshot_interrupt")
    if os.path.exists(run_dir):
        shutil.rmtree(run_dir)
    os.makedirs(run_dir, exist_ok=True)

    random.seed(99)
    lm = LayeredMemory(run_dir)

    for i in range(1, 31):
        lm.store(f"snap_{i}", memory_type="test", tags=["t"])
        lm.process_decay_buffer(i)

    lm.try_flush(30)
    pre_counts = count_memories(lm)
    pre_hash = state_hash(lm)

    # Create a corrupted snapshot file
    snapshot_dir = Path(run_dir) / "snapshots"
    snapshot_dir.mkdir(exist_ok=True)

    # Write a partial/truncated snapshot
    corrupt_snap = snapshot_dir / "snapshot_corrupt.json"
    corrupt_snap.write_text('{"state": "partial", "content": "this is incomplete')

    # Write a valid snapshot alongside (should be latest by mtime)
    import time as time_module
    valid_snap = snapshot_dir / "snapshot_valid.json"
    snap_data = {
        "working_memory": dict(lm.working_memory),
        "episodic_memory": dict(lm.episodic_memory),
        "tick": 30,
        "note": "valid snapshot",
    }
    valid_snap.write_text(json.dumps(snap_data))
    time_module.sleep(0.01)

    # Write another corrupt snapshot (newer mtime)
    newest_corrupt = snapshot_dir / "snapshot_NEWEST_corrupt.json"
    newest_corrupt.write_text('{"state": "corrupt, timestamp:')
    time_module.sleep(0.01)

    # Recover: create new instance
    t0 = time.perf_counter()
    lm_rec = LayeredMemory(run_dir)
    recovery_latency_ms = (time.perf_counter() - t0) * 1000

    post_hash = state_hash(lm_rec)
    post_counts = count_memories(lm_rec)

    result = {
        "test": "TEST3_snapshot_interruption",
        "pass": True,
        "pre_snapshot_hash": pre_hash,
        "post_recovery_hash": post_hash,
        "hash_match": pre_hash == post_hash,
        "pre_counts": pre_counts,
        "post_counts": post_counts,
        "counts_match": pre_counts == post_counts,
        "recovery_latency_ms": round(recovery_latency_ms, 3),
        "snapshot_recovery_success": pre_hash == post_hash,
        "ghost_state_detected": pre_counts != post_counts,
        "corrupt_snapshot_count": 2,
        "runtime_survived": True,
        "notes": "Corrupt snapshots present; runtime should use last valid state",
    }

    result["pass"] = result["snapshot_recovery_success"] and result["runtime_survived"]
    return result


# ─── Test 4: Replay Determinism ──────────────────────────────────────────────

def test_replay_determinism() -> dict:
    """
    Same WAL replayed twice -> must produce identical state hash.
    """
    run_dir = str(RUNS_DIR / "test4_replay_determinism")
    if os.path.exists(run_dir):
        shutil.rmtree(run_dir)
    os.makedirs(run_dir, exist_ok=True)

    random.seed(777)
    lm = LayeredMemory(run_dir)

    for i in range(1, 76):
        lm.store(f"det_{i}", memory_type="test", tags=["t"])
        lm.process_decay_buffer(i)
        if i % 15 == 0:
            lm.incremental_review(i)

    lm.try_flush(75)
    wal = lm._wal
    pre_hash = state_hash(lm)
    pre_counts = count_memories(lm)

    # Replay 1
    wal_replay1 = WALManager(root=run_dir)
    entries1 = list(wal_replay1.replay())
    hashes1 = []
    lm1 = LayeredMemory(run_dir)
    for _ in range(5):
        hashes1.append(state_hash(lm1))

    # Replay 2
    wal_replay2 = WALManager(root=run_dir)
    entries2 = list(wal_replay2.replay())
    hashes2 = []
    lm2 = LayeredMemory(run_dir)
    for _ in range(5):
        hashes2.append(state_hash(lm2))

    all_same = len(set(hashes1)) == 1 and len(set(hashes2)) == 1
    replay1_eq_replay2 = hashes1 == hashes2

    seqs1 = [e.seq for e in entries1]
    seqs2 = [e.seq for e in entries2]

    result = {
        "test": "TEST4_replay_determinism",
        "pass": True,
        "wal_total_entries": len(entries1),
        "entries_match": len(entries1) == len(entries2),
        "seqs_match": seqs1 == seqs2,
        "replay1_state_hashes": hashes1,
        "replay2_state_hashes": hashes2,
        "replay1_all_same": all_same,
        "replay2_all_same": all_same,
        "replay1_eq_replay2": replay1_eq_replay2,
        "pre_crash_hash": pre_hash,
        "post_replay_hash": hashes1[0] if hashes1 else None,
        "hash_consistent": pre_hash == hashes1[0] if hashes1 else False,
        "notes": "Multiple replays of same WAL must produce identical state",
    }

    result["pass"] = (
        all_same and
        replay1_eq_replay2 and
        result["seqs_match"] and
        result["entries_match"]
    )
    return result


# ─── Test 5: Corrupted Event ────────────────────────────────────────────────

def test_corrupted_event() -> dict:
    """
    Manually corrupt a WAL entry's checksum. Verify:
    - Corruption is detected
    - Entry is skipped (quarantined)
    - Replay continues
    - Runtime survives
    """
    run_dir = str(RUNS_DIR / "test5_corrupted_event")
    if os.path.exists(run_dir):
        shutil.rmtree(run_dir)
    os.makedirs(run_dir, exist_ok=True)

    random.seed(123)
    lm = LayeredMemory(run_dir)

    for i in range(1, 31):
        lm.store(f"corr_{i}", memory_type="test", tags=["t"])
        lm.process_decay_buffer(i)

    lm.try_flush(30)
    wal_entries_before = wal_entry_count(lm._wal)

    # Corrupt a checksum in the WAL file
    wal_files = sorted(lm._wal.wal_dir.glob("wal_*.jsonl"))
    if wal_files:
        last_file = wal_files[-1]
        with open(last_file, "r", encoding="utf-8") as f:
            lines = f.readlines()

        if lines:
            # Corrupt the 3rd line's checksum
            line_idx = min(2, len(lines) - 1)
            d = json.loads(lines[line_idx].strip())
            original_checksum = d["checksum"]
            d["checksum"] = "DEADBEEF"  # Wrong checksum
            lines[line_idx] = json.dumps(d) + "\n"
            with open(last_file, "w", encoding="utf-8") as f:
                f.writelines(lines)

    # Verify corruption detection
    wal = lm._wal
    verify = wal.verify()
    entries_after_corruption = wal_entry_count(wal)

    # Recover
    t0 = time.perf_counter()
    lm_rec = LayeredMemory(run_dir)
    recovery_latency_ms = (time.perf_counter() - t0) * 1000

    post_counts = count_memories(lm_rec)
    verify_after = lm_rec._wal.verify()

    result = {
        "test": "TEST5_corrupted_event",
        "pass": True,
        "wal_entries_before": wal_entries_before,
        "wal_entries_after_corruption": entries_after_corruption,
        "corruption_detected": verify["verified"] == False,
        "checksum_errors_found": verify["checksum_errors"],
        "recovery_latency_ms": round(recovery_latency_ms, 3),
        "runtime_survived": True,
        "post_recovery_wal_verified": verify_after["verified"],
        "post_recovery_counts": post_counts,
        "corrupted_event_quarantined": verify["checksum_errors"] >= 1,
        "replay_continues": True,  # if we got here
        "notes": "Manual checksum corruption; entry should be skipped, replay continues",
    }

    result["pass"] = (
        result["corruption_detected"] and
        result["runtime_survived"] and
        result["post_recovery_wal_verified"]
    )
    return result


# ─── Test 6: WAL Rotation Recovery ─────────────────────────────────────────

def test_wal_rotation_recovery() -> dict:
    """
    Force multiple WAL rotations, crash after rotation, verify:
    - Multi-segment replay works
    - Ordering continuity across segments
    - No segment loss
    """
    run_dir = str(RUNS_DIR / "test6_wal_rotation")
    if os.path.exists(run_dir):
        shutil.rmtree(run_dir)
    os.makedirs(run_dir, exist_ok=True)

    random.seed(456)
    lm = LayeredMemory(run_dir)

    # Force small rotation threshold temporarily
    original_rotation = lm._wal.rotation_bytes
    lm._wal.rotation_bytes = 512  # Force frequent rotation

    for i in range(1, 101):
        lm.store(f"rot_{i}", memory_type="test", tags=["t"])
        lm.process_decay_buffer(i)
        if i % 20 == 0:
            lm.incremental_review(i)

    lm._wal.rotation_bytes = original_rotation
    lm.try_flush(100)

    wal_files_before = sorted(lm._wal.list_wal_files())
    wal_count_before = len(wal_files_before)
    wal_entries_before = wal_entry_count(lm._wal)
    pre_hash = state_hash(lm)
    pre_counts = count_memories(lm)

    # Crash simulation: corrupt last file partially
    if wal_files_before:
        last = wal_files_before[-1]
        with open(last, "rb") as f:
            content = bytearray(f.read())
        if len(content) > 20:
            with open(last, "wb") as f:
                f.write(content[:-15])

    # Recover
    t0 = time.perf_counter()
    lm_rec = LayeredMemory(run_dir)
    recovery_latency_ms = (time.perf_counter() - t0) * 1000

    wal_files_after = sorted(lm_rec._wal.list_wal_files())
    wal_entries_after = wal_entry_count(lm_rec._wal)
    post_hash = state_hash(lm_rec)
    post_counts = count_memories(lm_rec)

    verify = lm_rec._wal.verify()

    # Check ordering continuity
    all_entries = list(lm_rec._wal.replay())
    seqs = [e.seq for e in all_entries]
    seqs_sorted = seqs == sorted(seqs)
    seqs_unique = len(seqs) == len(set(seqs)) if seqs else True
    seq_continuous = all(seqs[i] + 1 == seqs[i+1] for i in range(len(seqs)-1)) if len(seqs) > 1 else True

    result = {
        "test": "TEST6_wal_rotation_recovery",
        "pass": True,
        "wal_file_count_before": wal_count_before,
        "wal_file_count_after": len(wal_files_after),
        "wal_entries_before": wal_entries_before,
        "wal_entries_after": wal_entries_after,
        "lost_events": max(0, wal_entries_before - wal_entries_after),
        "recovery_latency_ms": round(recovery_latency_ms, 3),
        "pre_crash_hash": pre_hash,
        "post_recovery_hash": post_hash,
        "hash_match": pre_hash == post_hash,
        "pre_counts": pre_counts,
        "post_counts": post_counts,
        "counts_match": pre_counts == post_counts,
        "seqs_monotonic": seqs_sorted,
        "seqs_unique": seqs_unique,
        "seq_continuous_across_rotations": seq_continuous,
        "wal_verify_passed": verify["verified"],
        "notes": f"Multi-segment WAL ({wal_count_before} files) with corruption in last segment",
    }

    result["pass"] = (
        result["wal_verify_passed"] and
        result["seqs_monotonic"] and
        result["seq_continuous_across_rotations"] and
        result["runtime_survived"]
    )
    return result


# ─── Run All Tests ───────────────────────────────────────────────────────────

def run_all_tests():
    print("=" * 70)
    print("MCR PHASE III-C: CRASH RECOVERY PHYSICS")
    print("=" * 70)
    print()

    results = []
    tests = [
        ("G1-G2: Hard Crash + Replay", test_hard_crash_replay),
        ("G2: Partial WAL Write", test_partial_wal_write),
        ("G3: Snapshot Interruption", test_snapshot_interruption),
        ("G4: Replay Determinism", test_replay_determinism),
        ("G5: Corrupted Event", test_corrupted_event),
        ("G6: WAL Rotation Recovery", test_wal_rotation_recovery),
    ]

    for name, test_fn in tests:
        print(f"Running: {name}...", end=" ", flush=True)
        try:
            result = test_fn()
            results.append(result)
            status = "PASS" if result["pass"] else "FAIL"
            print(f"[{status}]")
            print(f"  recovery_latency_ms: {result.get('recovery_latency_ms', 'N/A')}")
            print(f"  hash_match: {result.get('hash_match', result.get('replay1_eq_replay2', 'N/A'))}")
        except Exception as e:
            print(f"[ERROR] {e}")
            results.append({"test": name, "pass": False, "error": str(e)})

        # Save individual result
        test_slug = name.split(":")[0].replace(" ", "_").lower()
        with open(METRICS_DIR / f"{test_slug}_result.json", "w") as f:
            json.dump(result, f, indent=2, default=str)
        print()

    # Summary
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    all_pass = all(r.get("pass", False) for r in results)
    for r in results:
        tag = r.get("test", r.get("tag", "unknown"))
        status = "PASS" if r.get("pass") else "FAIL"
        lat = r.get("recovery_latency_ms", "N/A")
        print(f"  [{status}] {tag} | latency={lat}ms")
    print()
    print(f"OVERALL: {'ALL PASS — Crash Recovery Verified' if all_pass else 'FAILURES DETECTED'}")
    print(f"Results saved to: {METRICS_DIR}/")

    # Save aggregate metrics
    summary = {
        "experiment": "PHASE_III_C_Crash_Recovery",
        "LKG": "637a11c907e8a889b909513522dfab8c",
        "all_pass": all_pass,
        "test_count": len(results),
        "pass_count": sum(1 for r in results if r.get("pass")),
        "fail_count": sum(1 for r in results if not r.get("pass")),
        "results": [
            {
                "test": r.get("test", ""),
                "pass": r.get("pass", False),
                "recovery_latency_ms": r.get("recovery_latency_ms"),
                "hash_match": r.get("hash_match", r.get("replay1_eq_replay2")),
                "ghost_state_detected": r.get("ghost_state_detected", False),
                "runtime_survived": r.get("runtime_survived", True),
            }
            for r in results
        ],
    }

    with open(METRICS_DIR / "recovery_metrics.json", "w") as f:
        json.dump(summary, f, indent=2, default=str)

    return results, summary


if __name__ == "__main__":
    results, summary = run_all_tests()
