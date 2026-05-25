#!/bin/bash
# scripts/verify_all.sh — MCR v0.10.0rc1 local verification
set -e

cd "$(dirname "$0")/.."

echo "=== MCR v0.9.7 Verification ==="
echo ""
echo "For package build verification, run:"
echo "  bash scripts/build_check.sh"
echo ""

echo "[1/5] minimal_mcr.py"
python3 examples/minimal_mcr.py
echo ""

echo "[2/5] library_usage.py"
python3 examples/library_usage.py
echo ""

echo "[3/5] quickstart.py"
python3 examples/quickstart.py
echo ""

echo "[4/5] replay_verification_demo.py"
python3 examples/replay_verification_demo.py
echo ""

echo "[5/5] hermes_bridge_demo.py"
python3 examples/hermes_bridge_demo.py
echo ""

echo "=== pytest ==="
if ! python3 -m pytest --version >/dev/null 2>&1; then
    echo "ERROR: pytest is not installed."
    echo "Install it with:"
    echo "  python3 -m pip install pytest"
    exit 1
fi
python3 -m pytest tests/ -q

echo ""
echo "=== ALL PASS ==="
