"""
test_library_usage.py — MCR v0.9.4
Verify examples/library_usage.py runs successfully.
"""
import subprocess, sys


def test_library_usage():
    """Run library_usage.py and verify it outputs PASS."""
    result = subprocess.run(
        [sys.executable, "examples/library_usage.py"],
        capture_output=True,
        text=True,
        cwd="."
    )
    assert result.returncode == 0, f"library_usage.py failed with code {result.returncode}\n{result.stderr}"
    assert "PASS" in result.stdout, f"No PASS in output:\n{result.stdout}"
    assert "Replay verification" in result.stdout, f"No replay verification in output:\n{result.stdout}"