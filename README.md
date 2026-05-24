# MCR — Memory-Augmented Cognitive Runtime

A replayable memory runtime for long-running AI agents.

> Current release: **v0.9.3**
> Status: **Research runtime artifact / demo-ready / regression-protected**
> GitHub: <https://github.com/Mini-0618/mcr-runtime>

## Why MCR Exists

Long-running AI agents eventually run into runtime-state problems that are not solved by a larger prompt window or a simple vector store:

- memory explosion
- retrieval drift
- state unrecoverability
- untraceable memory lifecycle changes
- crash recovery that cannot be verified

MCR addresses these problems with an event-sourced runtime kernel: **WAL + reducer + replay verifier**. Agent memory state is recorded, replayable, and verifiable.

## Quickstart for External Users

`ash
git clone https://github.com/Mini-0618/mcr-runtime.git
cd mcr-runtime
python3 examples/minimal_mcr.py
`

Expected success indicator:

`	ext
Result: PASS
`

The minimal demo requires no API key, no external LLM, no database, and no pytest.

## Full Verification

`ash
python3 -m pip install pytest
bash scripts/verify_all.sh
`

pytest is only required for the full verification suite. The minimal demo runs with the Python standard library.

## Demo Matrix

| Demo | Purpose |
| --- | --- |
| examples/minimal_mcr.py | 200-line self-contained concept demo |
| examples/quickstart.py | Modular runtime demo |
| examples/replay_verification_demo.py | Replay hash verification |
| examples/hermes_bridge_demo.py | Mock LLM bridge demo |

## Core Runtime Flow

`	ext
User / Agent Event
        ↓
Event Gate
        ↓
WAL
        ↓
Reducer
        ↓
Runtime State
        ↓
Replay Verifier
        ↓
PASS / FAIL
`

## What MCR Is / Is Not

MCR is not:

- AGI
- a production-ready agent framework
- a chatbot framework
- a model training system

MCR is:

- a replayable memory runtime
- an event-sourced agent memory substrate
- a research artifact for long-running agent state verification

## Documentation

| Document | Purpose |
| --- | --- |
| docs/PROJECT_OVERVIEW.md | Full project overview |
| docs/GETTING_STARTED.md | First-time user guide |
| docs/ARCHITECTURE.md | Runtime architecture |
| docs/DEMO_WALKTHROUGH.md | Demo explanation |
| docs/EXTERNAL_VALIDATION.md | External feedback process |
| docs/KNOWN_ISSUES.md | Current limitations |
| docs/ROADMAP.md | Project roadmap |
| docs/FAQ.md | Common questions |
| CHANGELOG.md | Version history |
| docs/RELEASES.md | Release notes |

## Repository Layout

`	ext
runtime/                 Core runtime kernel
  wal.py                 Write-ahead log
  state.py               Runtime state container
  reducer.py             Pure state transition logic
  engine.py              Runtime engine wrapper
  event_gate.py          Event validation layer
  hermes_bridge.py       Mock LLM proposal bridge
  replay_verifier.py     Replay verification

examples/                User-facing demos
docs/                    Project documentation
tests/                   Regression tests
scripts/verify_all.sh    Full demo + test verification
`

## Current Status

v0.9.3 is intended as an external onboarding release. It is demo-ready and regression-protected, but it is still a research runtime artifact. Use it to study replayable agent memory state, not as a production agent framework.
