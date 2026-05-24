#!/bin/bash
# scripts/verify_all.sh — MCR v0.9.2 local verification
set -e

cd "$(dirname "$0")/.."

echo "=== MCR v0.9.2 Verification ==="
echo ""

echo "[1/4] minimal_mcr.py"
python3 examples/minimal_mcr.py
echo ""

echo "[2/4] quickstart.py"
python3 examples/quickstart.py
echo ""

echo "[3/4] replay_verification_demo.py"
python3 examples/replay_verification_demo.py
echo ""

echo "[4/4] hermes_bridge_demo.py"
python3 examples/hermes_bridge_demo.py
echo ""

echo "=== pytest ==="
if ! /usr/bin/python3 -m pytest --version >/dev/null 2>&1; then
    echo "ERROR: pytest is not installed."
    echo "Install it with:"
    echo "  python3 -m pip install pytest"
    exit 1
fi
/usr/bin/python3 -m pytest tests/ -q

echo ""
echo "=== ALL PASS ==="