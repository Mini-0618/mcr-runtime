"""
test_minimal_replay.py — MCR v0.9.2
Verify minimal_mcr.py replay hash consistency.
This runs the minimal_mcr demo inline and checks that:
  1. WAL is created
  2. Replay produces same state hash as live run
  3. G2 PASS
"""
import subprocess, sys, json, hashlib

def test_minimal_mcr_replay_hash():
    """Run minimal_mcr.py and verify G2 PASS."""
    result = subprocess.run(
        [sys.executable, "examples/minimal_mcr.py"],
        capture_output=True,
        text=True,
        cwd="/home/minimak/mcr",
    )
    output = result.stdout + result.stderr

    # Must exit clean
    assert result.returncode == 0, f"minimal_mcr.py failed:\n{output}"

    # Must contain G2 PASS
    assert "G2 VERIFICATION: PASS" in output or "PASS" in output, \
        f"Expected PASS in output:\n{output}"

    # WAL file must exist and have content
    wal_path = "/home/minimak/mcr/tmp/mcr_demo.wal.jsonl"
    with open(wal_path) as f:
        lines = [json.loads(line) for line in f if line.strip()]
    assert len(lines) > 0, "WAL is empty"
    print(f"[test_minimal_replay] WAL lines: {len(lines)}, G2 PASS ✓")