"""
test_runtime_replay.py — MCR v0.9.2
Verify modular runtime path (runtime/) replays correctly.
G2: runtime_state == replay(WAL)
"""
import subprocess, sys

def test_runtime_replay():
    """Run quickstart.py and verify G2 PASS."""
    result = subprocess.run(
        [sys.executable, "examples/quickstart.py"],
        capture_output=True,
        text=True,
        cwd=".",
    )
    output = result.stdout + result.stderr
    assert result.returncode == 0, f"quickstart.py failed:\n{output}"
    # G2 PASS must appear in output
    assert "G2" in output and "PASS" in output, \
        f"Expected G2 PASS in output:\n{output}"
    print("[test_runtime_replay] G2 PASS ✓")