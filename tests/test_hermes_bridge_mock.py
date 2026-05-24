"""
test_hermes_bridge_mock.py — MCR v0.9.2
Verify mock Hermes response is parsed by bridge, passes event_gate,
and results in G2 PASS.
"""
import subprocess, sys

def test_hermes_bridge_mock():
    """Run hermes_bridge_demo.py and verify PASS."""
    result = subprocess.run(
        [sys.executable, "examples/hermes_bridge_demo.py"],
        capture_output=True,
        text=True,
        cwd=".",
    )
    output = result.stdout + result.stderr
    assert result.returncode == 0, f"hermes_bridge_demo.py failed:\n{output}"
    assert "PASS" in output or "accepted" in output, \
        f"Expected PASS/accepted in output:\n{output}"
    print("[test_hermes_bridge_mock] Hermes Bridge mock PASS ✓")