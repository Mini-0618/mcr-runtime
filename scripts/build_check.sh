#!/usr/bin/env bash
# scripts/build_check.sh — MCR v0.10.0rc1 build verification
set -euo pipefail

cd "$(dirname "$0")/.."

echo "=== MCR v0.9.7 Build Check ==="
echo ""

# Use venv to avoid system package conflicts
VENV_DIR="${VENV_DIR:-/tmp/mcr-build-venv}"

echo "[1/4] Cleaning old artifacts..."
rm -rf dist/ build/ *.egg-info/
echo "  done"

echo "[2/4] Setting up venv..."
rm -rf "$VENV_DIR"
/usr/bin/python3 -m venv "$VENV_DIR"
# shellcheck source=/dev/null
source "$VENV_DIR/bin/activate"
python3 -m pip install -U pip -q
echo "  done"

echo "[3/4] Installing build tools..."
pip install -q build
echo "  done"

echo "[4/4] Building wheel..."
python3 -m build
echo ""
ls -lh dist/
echo "  wheel built OK"

echo ""
echo "[smoke] Installing wheel..."
pip install -q --force-reinstall dist/*.whl
echo "  wheel installed OK"

echo ""
echo "[smoke] Importing runtime from wheel..."
python3 -c "import runtime; import runtime.engine; import runtime.wal; import runtime.replay_verifier; print('  wheel import PASS')"

echo ""
echo "=== BUILD CHECK PASSED ==="
