"""
test_no_token_leak.py — MCR v0.9.2
Verify repository contains no GitHub tokens (ghp_ or github_pat_).
"""
import subprocess, sys, re

def test_no_token_leak():
    """grep all tracked files for GitHub token patterns."""
    # Check for ghp_ classic tokens
    r1 = subprocess.run(
        ["git", "grep", "-E", "ghp_[a-zA-Z0-9]{36}"],
        capture_output=True, text=True, cwd="/home/minimak/mcr"
    )
    # Check for github_pat_ PATs
    r2 = subprocess.run(
        ["git", "grep", "-E", "github_pat_[a-zA-Z0-9_]{20,}"],
        capture_output=True, text=True, cwd="/home/minimak/mcr"
    )
    # Filter out false positives (this test file itself should be clean)
    leaks_ghp = [l for l in r1.stdout.splitlines() if "ghp_" in l and "test_no_token_leak" not in l]
    leaks_pat = [l for l in r2.stdout.splitlines() if "github_pat_" in l and "test_no_token_leak" not in l]

    assert len(leaks_ghp) == 0, f"ghp_ token found:\n" + "\n".join(leaks_ghp)
    assert len(leaks_pat) == 0, f"github_pat_ token found:\n" + "\n".join(leaks_pat)
    print("[test_no_token_leak] No tokens found ✓")