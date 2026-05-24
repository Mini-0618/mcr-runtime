# Packaging and Installation

## Current Status

MCR is currently an **installable research runtime package prototype**.
It is not yet published to PyPI.

---

## Developer Installation

```bash
git clone https://github.com/Mini-0618/mcr-runtime.git
cd mcr-runtime
python3 -m pip install -e ".[dev]"
```

### Verify installation

```bash
python3 examples/library_usage.py
python3 -m pytest -q
bash scripts/verify_all.sh
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

## Known Limitation

Current public module namespace is `runtime`.
This may conflict with other packages that use a generic `runtime` name.

Future versions may expose `mcr_runtime` as a stable, unambiguous namespace.

---

## Not on PyPI Yet

Do **not** run:

```bash
pip install mcr-runtime
```

until a PyPI release is explicitly announced.

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
├── pyproject.toml     # Package metadata
└── LICENSE            # MIT License
```