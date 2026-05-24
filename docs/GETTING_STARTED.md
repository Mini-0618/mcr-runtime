# Getting Started

## Requirements

- Python 3.10+
- Git
- No API key required
- No external LLM required
- No database required

## Clone

```bash
git clone https://github.com/Mini-0618/mcr-runtime.git
cd mcr-runtime
```

## Run the minimal demo

```bash
python3 examples/minimal_mcr.py
```

**Expected output:** Look for `Result: PASS` in the output. This means replay verification succeeded — the runtime state matches what you get by replaying all events from the WAL.

## Run all demos

Demos are independent and can be run in any order:

```bash
# Demo 1: self-contained concept demo (~1 second)
python3 examples/minimal_mcr.py

# Demo 2: modular runtime demo (~1 second)
python3 examples/quickstart.py

# Demo 3: replay hash verification (~1 second)
python3 examples/replay_verification_demo.py

# Demo 4: mock LLM bridge demo (~1 second)
python3 examples/hermes_bridge_demo.py
```

## Run full verification

```bash
# Install pytest if not present
python3 -m pip install pytest

# Run all demos + tests
bash scripts/verify_all.sh
```

**Note:** The minimal demo (`minimal_mcr.py`) runs without pytest. Only install pytest for the full test suite.

## Troubleshooting

### `Permission denied (publickey)` when cloning

You used SSH clone but have no GitHub SSH key configured.

**Fix:** Use HTTPS clone:

```bash
git clone https://github.com/Mini-0618/mcr-runtime.git
```

### `No module named pytest`

You're running the full test suite but pytest is not installed.

**Fix:**

```bash
python3 -m pip install pytest
bash scripts/verify_all.sh
```

### `python3: command not found`

Python 3 is not installed, or the command is `python` instead of `python3`.

**Check:**

```bash
python --version
python3 --version
```

### Demo runs but I don't see `Result: PASS`

If the output shows a hash mismatch or `FAIL`, please open an issue:
https://github.com/Mini-0618/mcr-runtime/issues

Include:
- OS
- Python version (`python3 --version`)
- The full terminal output