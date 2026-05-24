# Getting Started

This guide is for first-time users who want to run MCR locally and verify that replay works.

## Requirements

- Python 3.10+
- Git
- No API key required
- No external LLM required
- No database required

## Clone

Use HTTPS clone for the lowest-friction external setup:

```bash
git clone https://github.com/Mini-0618/mcr-runtime.git
cd mcr-runtime
```

## Run the minimal demo

```bash
python3 examples/minimal_mcr.py
```

## Expected output

The minimal demo should end with:

```text
Result: PASS
```

This means replay verification succeeded. The runtime state can be reconstructed from the WAL.

## Run all demos

```bash
python3 examples/quickstart.py
python3 examples/replay_verification_demo.py
python3 examples/hermes_bridge_demo.py
```

## Run full verification

```bash
python3 -m pip install pytest
bash scripts/verify_all.sh
```

Expected result:

```text
=== ALL PASS ===
```

## What to inspect after running

After the minimal demo, inspect:

- the printed runtime state
- the runtime state hash
- the replay state hash
- the final PASS result

The important point is not the specific memory item. The important point is that replay reconstructs the same state.

## Troubleshooting

### Permission denied publickey

Use HTTPS clone instead of SSH:

```bash
git clone https://github.com/Mini-0618/mcr-runtime.git
```

### No module named pytest

Install pytest before running full verification:

```bash
python3 -m pip install pytest
```

### python3 not found

Install Python 3, or try:

```bash
python examples/minimal_mcr.py
```

### Demo does not show PASS

Open an issue with:

- operating system
- Python version
- command used
- full terminal output
