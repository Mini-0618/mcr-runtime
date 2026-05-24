# Getting Started

## Requirements

- Python 3.10+
- Git
- No API key required
- No external LLM required
- No database required

## Clone

Use HTTPS clone for the lowest-friction external setup:

`ash
git clone https://github.com/Mini-0618/mcr-runtime.git
cd mcr-runtime
`

## Run the minimal demo

`ash
python3 examples/minimal_mcr.py
`

## Expected output

The minimal demo should end with:

`	ext
Result: PASS
`

This means replay verification succeeded: the runtime state can be reconstructed from the WAL.

## Run all demos

`ash
python3 examples/quickstart.py
python3 examples/replay_verification_demo.py
python3 examples/hermes_bridge_demo.py
`

## Run full verification

`ash
python3 -m pip install pytest
bash scripts/verify_all.sh
`

pytest is only required for the full verification suite. The minimal demo does not require it.

## Troubleshooting

### Permission denied publickey

Use HTTPS clone instead of SSH:

`ash
git clone https://github.com/Mini-0618/mcr-runtime.git
`

### No module named pytest

Install pytest before running full verification:

`ash
python3 -m pip install pytest
`

### python3 not found

Install Python 3, or try:

`ash
python examples/minimal_mcr.py
`

### Demo does not show PASS

Open an issue with:

- operating system
- Python version
- command used
- full terminal output
