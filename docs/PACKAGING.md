# Packaging and Installation

## Current Status

MCR is currently an **installable research runtime package prototype**.
It is not yet published to PyPI.

---

## Recommended Installation (venv)

Use a virtual environment to avoid system-wide package conflicts:

```bash
git clone https://github.com/Mini-0618/mcr-runtime.git
cd mcr-runtime
python3 -m venv .venv
source .venv/bin/activate          # Linux/macOS
# .\.venv\\Scripts\\Activate.ps1   # Windows PowerShell
python3 -m pip install -U pip
python3 -m pip install -e ".[dev]"
```

### Verify installation

```bash
bash scripts/verify_all.sh
```

### Build locally

```bash
bash scripts/build_check.sh
```

---

## Import Example

```python
from runtime.engine import MCRRuntimeEngine
from runtime.wal import WAL, Event
from runtime.reducer import DeterministicReducer
from runtime.replay_verifier import ReplayVerifier
from runtime.state import SystemState
from runtime.event_gate import EventGate
from runtime.hermes_bridge import HermesBridge
```

---

## Minimal Demo (No Install Required)

Clone and run directly without installation:

```bash
git clone https://github.com/Mini-0618/mcr-runtime.git
cd mcr-runtime
python3 examples/minimal_mcr.py
```

---

## Current Namespace

Current public module namespace is `runtime`.
This is a generic name that may conflict with other packages.

**Known limitation:** Future v1.x may expose `mcr_runtime` as a stable namespace. v0.9.x keeps `runtime` for compatibility.

---

## PyPI Status

MCR is **not published to PyPI yet**.

Do **not** run:

```bash
pip install mcr-runtime
```

until an official PyPI release is explicitly announced.

---

## Package Structure

```
mcr-runtime/
├── runtime/          # Public Python package
│   ├── __init__.py    # Public API exports
│   ├── engine.py      # MCRRuntimeEngine
│   ├── wal.py        # WAL + Event
│   ├── state.py      # SystemState
│   ├── reducer.py     # DeterministicReducer
│   ├── replay_verifier.py  # ReplayVerifier
│   ├── event_gate.py # EventGate
│   └── hermes_bridge.py  # HermesBridge
├── examples/          # Demo scripts (not part of package)
├── tests/             # Test suite
├── scripts/           # Verification scripts
├── pyproject.toml     # Package metadata
├── LICENSE            # MIT License
└── README.md          # Project documentation
```

---

## CI / Build Verification

The project uses GitHub Actions to verify builds on Python 3.10, 3.11, and 3.12.

See `.github/workflows/python-tests.yml` for the full CI pipeline.
